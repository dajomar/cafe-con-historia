import os
import sys
import json
import requests
import pathlib
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from slack_sdk import WebClient

BASE_DIR = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "utils"))

from errores import (
    ErrorInfraestructura,
    ErrorContenido,
    verificar_token_facebook,
    verificar_error_facebook,
    notificar_infra,
    notificar_error_contenido,
    notificar_canal
)

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv(BASE_DIR / ".env")

SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
SLACK_TOKEN     = os.getenv("SLACK_TOKEN")
CANAL_CONTENIDO = os.getenv("SLACK_CHANNEL", "#contenido")
FB_PAGE_TOKEN   = os.getenv("FB_PAGE_TOKEN")
FB_PAGE_ID      = os.getenv("FB_PAGE_ID")
OLLAMA_URL      = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434") + "/api/generate"
MODELO          = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

MAX_INTENTOS    = 3
SCORE_MINIMO    = 7

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# ESTÁNDARES PARA EL POST DE FACEBOOK
# ============================================================

ESTANDARES_FB = """
1. HOOK — La primera línea es impactante y genera curiosidad inmediata.
2. LONGITUD — Entre 400 y 600 palabras. Ni muy corto ni muy largo para Facebook.
3. EMOJIS — Entre 3 y 7 emojis relevantes y coherentes con el tono del tema.
4. PREGUNTA FINAL — Termina con una pregunta que invite a comentar.
5. HASHTAGS — Incluye entre 3 y 5 hashtags relevantes al final.
6. TONO — Conversacional y cercano, como hablarle a un amigo. No académico.
7. INTEGRIDAD — No contiene frases de rechazo, disculpas ni meta-comentarios.
"""

# ============================================================
# PASO 1 — Obtener contenido aprobado
# ============================================================

def obtener_contenido_aprobado():
    print("Buscando contenido aprobado para publicar...")
    resultado = supabase.table("contenido")\
        .select("*, temas(pregunta, categoria)")\
        .eq("aprobado", True)\
        .is_("contenido_facebook", "null")\
        .order("fecha_generacion", desc=True)\
        .limit(1)\
        .execute()

    if not resultado.data:
        print("No hay contenido aprobado pendiente de publicar.")
        return None

    contenido = resultado.data[0]
    print(f"Contenido encontrado: {contenido['temas']['pregunta']}")
    return contenido

# ============================================================
# PASO 2 — Adaptar para Facebook
# ============================================================

def adaptar_para_facebook(pregunta, contenido_largo, categoria):
    print("Adaptando contenido para Facebook...")

    prompt = f"""Eres el community manager experto de "Café con Historia", canal educativo en Facebook.
Tu enfoque es: "La historia explica el presente".

Adapta este contenido para Facebook:
PREGUNTA: {pregunta}
CATEGORÍA: {categoria}

CONTENIDO ORIGINAL:
{contenido_largo}

ESTÁNDARES QUE DEBE CUMPLIR:
{ESTANDARES_FB}

Responde SOLO con el texto del post listo para publicar, sin explicaciones ni meta-comentarios."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        post = data.get("response", "").strip()
        print(f"Post generado: {len(post)} caracteres")
        return post
    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al adaptar contenido para Facebook")
    except Exception as e:
        raise ErrorContenido(f"Error adaptando contenido: {e}")

# ============================================================
# PASO 3 — Evaluar post de Facebook
# ============================================================

def evaluar_post_facebook(pregunta, post_texto):
    print("Evaluando post de Facebook...")

    prompt = f"""Eres un editor crítico del canal "Café con Historia".
Evalúa si este post de Facebook cumple los estándares de calidad.

PREGUNTA DEL TEMA: {pregunta}

POST A EVALUAR:
{post_texto}

ESTÁNDARES:
{ESTANDARES_FB}

Responde ÚNICAMENTE con un objeto JSON con este formato exacto:
{{
  "score": <número del 1 al 10>,
  "aprobado": <true o false>,
  "evaluacion": {{
    "hook": <número del 1 al 10>,
    "longitud": <número del 1 al 10>,
    "emojis": <número del 1 al 10>,
    "pregunta_final": <número del 1 al 10>,
    "hashtags": <número del 1 al 10>,
    "tono": <número del 1 al 10>,
    "integridad": <número del 1 al 10>
  }},
  "razon_rechazo": "<explicación si no aprueba, vacío si aprueba>",
  "sugerencias": "<qué mejorar si no aprueba>"
}}

Score mínimo para aprobar: {SCORE_MINIMO}/10.
Responde SOLO con el JSON."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        texto = data.get("response", "").strip()

        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            return json.loads(texto[inicio:fin])
        raise ErrorContenido("Llama no respondió con JSON válido en evaluación")
    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al evaluar post de Facebook")
    except json.JSONDecodeError as e:
        raise ErrorContenido(f"Error parseando evaluación: {e}")

# ============================================================
# PASO 4 — Publicar en Facebook
# ============================================================

def publicar_facebook(texto, imagen_path=None):
    print("Publicando en Facebook...")

    # Verificar token antes de publicar
    verificar_token_facebook()

    try:
        if imagen_path and pathlib.Path(imagen_path).exists():
            # Publicar con imagen usando el endpoint /photos
            print(f"Publicando con imagen: {imagen_path}")
            url = f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/photos"
            with open(imagen_path, "rb") as f:
                respuesta = requests.post(
                    url,
                    files={"source": f},
                    data={
                        "message":      texto,
                        "access_token": FB_PAGE_TOKEN,
                        "privacy":      '{"value": "EVERYONE"}'
                    },
                    timeout=60
                )
        else:
            # Publicar solo texto usando el endpoint /feed
            if imagen_path:
                print(f"Imagen no encontrada en {imagen_path} — publicando sin imagen")
            url = f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/feed"
            respuesta = requests.post(
                url,
                data={
                    "message":      texto,
                    "access_token": FB_PAGE_TOKEN,
                    "privacy":      '{"value": "EVERYONE"}'
                },
                timeout=30
            )

        data = respuesta.json()

        if "id" in data:
            modo = "con imagen" if imagen_path else "sin imagen"
            print(f"✓ Publicado {modo} — Post ID: {data['id']}")
            return data["id"]

        # Detectar si es error de infraestructura o contenido
        if "error" in data:
            verificar_error_facebook(data["error"])

        raise ErrorContenido(f"Error desconocido de Facebook: {data}")

    except requests.ConnectionError:
        raise ErrorInfraestructura("Sin conexión a internet al publicar en Facebook")
    except (ErrorInfraestructura, ErrorContenido):
        raise
    except Exception as e:
        raise ErrorContenido(f"Error publicando en Facebook: {e}")

# ============================================================
# PASO 5 — Guardar y notificar
# ============================================================

def guardar_publicacion(contenido_id, post_facebook):
    supabase.table("contenido").update({
        "contenido_facebook": post_facebook,
    }).eq("id", contenido_id).execute()
    print("✓ Publicación guardada en Supabase")

def notificar_publicado(pregunta, post_facebook, fb_post_id, score, evaluacion):
    mensaje = f"""📢 *Publicado en Facebook*
*{pregunta}*

{post_facebook}

---
📊 *Score del post: {score}/10*
• Hook: {evaluacion.get('hook', 'N/A')}/10
• Emojis: {evaluacion.get('emojis', 'N/A')}/10
• Tono: {evaluacion.get('tono', 'N/A')}/10
• Pregunta final: {evaluacion.get('pregunta_final', 'N/A')}/10

🔗 Post ID: `{fb_post_id}`
_Publicado: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"""

    notificar_canal(CANAL_CONTENIDO, mensaje)

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente 3 (Publicador)")
    print("=" * 50)

    contenido = obtener_contenido_aprobado()
    if not contenido:
        return

    pregunta        = contenido["temas"]["pregunta"]
    categoria       = contenido["temas"]["categoria"]
    contenido_id    = contenido["id"]
    contenido_largo = contenido["contenido_slack"]
    imagen_path     = contenido.get("imagen_url")

    intento      = 1
    ultima_razon = ""
    post_actual  = None

    while intento <= MAX_INTENTOS:
        print(f"\n--- Intento {intento}/{MAX_INTENTOS} ---")

        try:
            # Adaptar para Facebook
            post_actual = adaptar_para_facebook(pregunta, contenido_largo, categoria)

            # Evaluar el post
            evaluacion = evaluar_post_facebook(pregunta, post_actual)
            score      = evaluacion.get("score", 0)
            aprobado   = evaluacion.get("aprobado", False) and score >= SCORE_MINIMO
            detalles   = evaluacion.get("evaluacion", {})
            ultima_razon = evaluacion.get("razon_rechazo", "")

            print(f"Score post Facebook: {score}/10 | Aprobado: {aprobado}")

            if aprobado:
                # Publicar (con imagen si está disponible)
                fb_post_id = publicar_facebook(post_actual, imagen_path)

                # Guardar y notificar
                guardar_publicacion(contenido_id, post_actual)
                notificar_publicado(pregunta, post_actual, fb_post_id, score, detalles)
                print(f"\n✓ Publicado exitosamente en intento {intento}")
                return

            print(f"Post rechazado: {ultima_razon}")

        except ErrorInfraestructura:
            # Relanzar para que main.py lo capture y detenga el pipeline
            raise

        except ErrorContenido as e:
            print(f"Error de contenido en intento {intento}: {e}")
            ultima_razon = str(e)

        intento += 1

    # Agotó los intentos
    notificar_error_contenido("Agente 3 — Publicador", pregunta, ultima_razon, MAX_INTENTOS)
    print(f"\n✗ No se pudo publicar después de {MAX_INTENTOS} intentos")

if __name__ == "__main__":
    correr_agente()