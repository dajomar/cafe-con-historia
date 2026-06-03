import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv("D:\\proyectos\\cafe-con-historia\\.env")

SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY")
SLACK_TOKEN   = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#contenido")
SLACK_ERRORES = "#errores"
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_PAGE_ID    = os.getenv("FB_PAGE_ID")
OLLAMA_URL    = "http://localhost:11434/api/generate"
MODELO        = "llama3.1"

MAX_INTENTOS  = 3
SCORE_MINIMO  = 7

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# ESTÁNDARES PARA EL POST DE FACEBOOK
# ============================================================

ESTANDARES_FB = """
1. HOOK — La primera línea es impactante y genera curiosidad inmediata.
2. LONGITUD — Entre 100 y 200 palabras. Ni muy corto ni muy largo para Facebook.
3. EMOJIS — Entre 3 y 7 emojis relevantes y coherentes con el tono del tema.
4. PREGUNTA FINAL — Termina con una pregunta que invite a comentar.
5. HASHTAGS — Incluye entre 3 y 5 hashtags relevantes al final.
6. TONO — Conversacional y cercano, como hablarle a un amigo. No académico.
7. INTEGRIDAD — No contiene frases de rechazo, disculpas ni meta-comentarios.
"""

# ============================================================
# PASO 1 — Obtener contenido aprobado listo para publicar
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
    print(f"Contenido aprobado encontrado: {contenido['temas']['pregunta']}")
    return contenido

# ============================================================
# PASO 2 — Adaptar para Facebook con Llama
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

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False
    }

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        post = data.get("response", "").strip()
        print(f"Post generado: {len(post)} caracteres")
        return post
    except Exception as e:
        print(f"Error adaptando: {e}")
        return None

# ============================================================
# PASO 3 — Evaluar el post de Facebook
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

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False
    }

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        texto = data.get("response", "").strip()

        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            evaluacion = json.loads(texto[inicio:fin])
            return evaluacion
        return None
    except Exception as e:
        print(f"Error evaluando post: {e}")
        return None

# ============================================================
# PASO 4 — Publicar en Facebook
# ============================================================

def publicar_facebook(texto):
    print("Publicando en Facebook...")
    url = f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/feed"
    payload = {
        "message": texto,
        "access_token": FB_PAGE_TOKEN
    }
    try:
        respuesta = requests.post(url, data=payload, timeout=30)
        data = respuesta.json()
        if "id" in data:
            print(f"✓ Publicado — Post ID: {data['id']}")
            return data["id"]
        else:
            print(f"Error Facebook: {data}")
            return None
    except Exception as e:
        print(f"Error publicando: {e}")
        return None

# ============================================================
# PASO 5 — Guardar y notificar
# ============================================================

def guardar_publicacion(contenido_id, post_facebook, fb_post_id, score):
    supabase.table("contenido").update({
        "contenido_facebook": post_facebook,
    }).eq("id", contenido_id).execute()
    print(f"✓ Publicación guardada en Supabase")

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

    slack.chat_postMessage(channel=SLACK_CHANNEL, text=mensaje, mrkdwn=True)

def notificar_error_publicacion(pregunta, razon):
    mensaje = f"""🚨 *Error al publicar en Facebook*
*{pregunta}*

El post no pasó la evaluación de calidad después de {MAX_INTENTOS} intentos.
Razón: {razon}

_Revisión manual requerida._"""

    slack.chat_postMessage(channel=SLACK_ERRORES, text=mensaje, mrkdwn=True)

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente 3 (Publicador)")
    print("=" * 50)

    # Paso 1 — Obtener contenido aprobado
    contenido = obtener_contenido_aprobado()
    if not contenido:
        return

    pregunta       = contenido["temas"]["pregunta"]
    categoria      = contenido["temas"]["categoria"]
    contenido_id   = contenido["id"]
    contenido_largo = contenido["contenido_slack"]

    intento = 1
    ultima_razon = ""
    post_actual = None

    while intento <= MAX_INTENTOS:
        print(f"\n--- Intento {intento}/{MAX_INTENTOS} ---")

        # Paso 2 — Adaptar para Facebook
        post_actual = adaptar_para_facebook(pregunta, contenido_largo, categoria)
        if not post_actual:
            intento += 1
            continue

        # Paso 3 — Evaluar el post
        evaluacion = evaluar_post_facebook(pregunta, post_actual)
        if not evaluacion:
            intento += 1
            continue

        score    = evaluacion.get("score", 0)
        aprobado = evaluacion.get("aprobado", False) and score >= SCORE_MINIMO
        detalles = evaluacion.get("evaluacion", {})
        ultima_razon = evaluacion.get("razon_rechazo", "")

        print(f"Score post Facebook: {score}/10 | Aprobado: {aprobado}")

        if aprobado:
            # Paso 4 — Publicar
            fb_post_id = publicar_facebook(post_actual)
            if not fb_post_id:
                intento += 1
                continue

            # Paso 5 — Guardar y notificar
            guardar_publicacion(contenido_id, post_actual, fb_post_id, score)
            notificar_publicado(pregunta, post_actual, fb_post_id, score, detalles)
            print(f"\n✓ Publicado exitosamente en intento {intento}")
            return

        print(f"Post rechazado: {ultima_razon}")
        intento += 1

    # Agotó los intentos
    notificar_error_publicacion(pregunta, ultima_razon)
    print(f"\n✗ No se pudo publicar después de {MAX_INTENTOS} intentos")

if __name__ == "__main__":
    correr_agente()