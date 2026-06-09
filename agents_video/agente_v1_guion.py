import os
import sys
import re
import json
import random
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
    ErrorNegocio,
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
OLLAMA_URL      = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434") + "/api/generate"
MODELO          = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
MAX_INTENTOS    = 3

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# PASO 1 — Escoger tema no usado en videos
# ============================================================

def escoger_tema():
    """
    Obtiene un tema que no tenga entrada en la tabla videos aún.
    Elige uno al azar entre los disponibles.
    """
    print("Buscando tema disponible para video...")

    try:
        # Obtener todos los tema_ids ya procesados en videos
        resultado_videos = supabase.table("videos").select("tema_id").execute()
        temas_en_videos = {row["tema_id"] for row in resultado_videos.data if row.get("tema_id")}

        # Obtener todos los temas
        resultado_temas = supabase.table("temas").select("*").execute()
        todos_los_temas = resultado_temas.data

    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo conectar a Supabase: {e}")

    # Filtrar temas que no están en videos
    temas_disponibles = [t for t in todos_los_temas if t["id"] not in temas_en_videos]

    if not temas_disponibles:
        raise ErrorNegocio(
            "No hay temas disponibles para el pipeline de video. "
            "Todos los temas ya tienen video generado o la tabla de temas está vacía."
        )

    tema = random.choice(temas_disponibles)
    print(f"Tema seleccionado: {tema['pregunta']}")
    return tema

# ============================================================
# UTILIDAD — Extraer JSON de respuesta de Llama
# ============================================================

def extraer_json(texto):
    """
    Extrae el primer objeto JSON válido de la respuesta de Llama.
    Maneja bloques markdown (```json ... ```) y texto libre.
    """
    # Intentar extraer de bloque markdown
    match_markdown = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
    if match_markdown:
        try:
            return json.loads(match_markdown.group(1))
        except json.JSONDecodeError:
            pass

    # Buscar el primer { en el texto
    inicio = texto.find("{")
    if inicio == -1:
        raise ErrorContenido("No se encontró JSON en la respuesta de Llama")

    # Intentar parsear desde el primer { hasta el final
    fragmento = texto[inicio:]
    try:
        return json.loads(fragmento)
    except json.JSONDecodeError:
        pass

    # Intentar encontrar el JSON balanceado manualmente
    nivel = 0
    fin = -1
    for i, char in enumerate(fragmento):
        if char == "{":
            nivel += 1
        elif char == "}":
            nivel -= 1
            if nivel == 0:
                fin = i + 1
                break

    if fin == -1:
        raise ErrorContenido("No se pudo extraer JSON balanceado de la respuesta")

    try:
        return json.loads(fragmento[:fin])
    except json.JSONDecodeError as e:
        raise ErrorContenido(f"JSON malformado en respuesta de Llama: {e}")

# ============================================================
# PASO 2 — Generar guión y escenas con Llama
# ============================================================

def generar_guion_escenas(pregunta, categoria, tono, region, epoca):
    """
    Genera un guión de 45-60 segundos dividido en 6-8 escenas.
    Retorna (guion_completo, lista_de_escenas).
    """
    print(f"Generando guión con {MODELO}...")

    contexto_tono = {
        "pesado":     "El tono debe ser serio y reflexivo, apropiado para temas difíciles.",
        "curioso":    "El tono debe ser sorprendente y entretenido, destacando lo inesperado.",
        "reflexivo":  "El tono debe invitar a la reflexión profunda sobre la condición humana.",
        "inspirador": "El tono debe ser positivo y motivador, destacando logros humanos."
    }.get(tono, "")

    prompt = f"""Eres el guionista del canal educativo "Café con Historia".
Tu enfoque es: "La historia explica el presente".
Creas guiones para videos cortos de 45-60 segundos en formato Reels/TikTok.

Crea un guión para este tema:
PREGUNTA: {pregunta}
CATEGORÍA: {categoria}
REGIÓN: {region}
ÉPOCA HISTÓRICA: {epoca}
INDICACIÓN DE TONO: {contexto_tono}

El guión debe:
1. Dividirse en 6-8 escenas de 5-8 segundos cada una
2. Narración en español, conversacional y educativa
3. Comenzar con un hook impactante que enganche en los primeros 3 segundos
4. Cada escena tiene narración hablada y una descripción visual para generar imagen
5. Las descripciones visuales deben ser específicas: lugar, época, vestimenta, atmósfera
6. Terminar con una pregunta reflexiva que invite a comentar

Responde ÚNICAMENTE con este JSON (sin texto antes ni después):
{{
  "guion_completo": "texto completo del guión de corrido",
  "escenas": [
    {{
      "numero": 1,
      "narracion": "texto que se narra en esta escena",
      "descripcion_visual": "descripción detallada de la imagen a generar para esta escena"
    }}
  ]
}}

IMPORTANTE: Responde solo con el JSON. Sin explicaciones ni texto adicional."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        texto = data.get("response", "").strip()

        if not texto:
            raise ErrorContenido("Llama devolvió una respuesta vacía al generar guión")

        frases_rechazo = ["lo siento", "no puedo", "no es apropiado", "no me es posible"]
        if any(frase in texto.lower() for frase in frases_rechazo):
            raise ErrorContenido(f"Llama rechazó el prompt de guión: {texto[:200]}")

        datos = extraer_json(texto)

        guion_completo = datos.get("guion_completo", "").strip()
        escenas = datos.get("escenas", [])

        if not guion_completo:
            raise ErrorContenido("El JSON no contiene 'guion_completo'")

        if not escenas or len(escenas) < 4:
            raise ErrorContenido(f"El guión tiene muy pocas escenas: {len(escenas)}")

        print(f"Guión generado: {len(guion_completo)} chars | {len(escenas)} escenas")
        return guion_completo, escenas

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al generar guión")
    except (ErrorInfraestructura, ErrorContenido):
        raise
    except Exception as e:
        raise ErrorContenido(f"Error generando guión: {e}")

# ============================================================
# PASO 3 — Guardar en Supabase
# ============================================================

def guardar_en_supabase(tema_id, guion_completo, escenas):
    """Inserta el video con guión y escenas en la tabla videos."""
    try:
        supabase.table("videos").insert({
            "tema_id":          tema_id,
            "guion":            guion_completo,
            "escenas":          escenas,
            "fecha_generacion": datetime.now().isoformat()
        }).execute()
        print("✓ Guión guardado en Supabase")
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo guardar el guión en Supabase: {e}")

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente V1 (Guión)")
    print("=" * 50)

    tema = escoger_tema()

    pregunta  = tema["pregunta"]
    categoria = tema["categoria"]
    tono      = tema.get("tono", "reflexivo")
    region    = tema.get("region", "global")
    epoca     = tema.get("epoca", "contemporanea")
    tema_id   = tema["id"]

    print(f"\nTema: {pregunta}")
    print(f"Clasificación: {tono} | {region} | {epoca}")

    intento      = 1
    ultima_razon = ""

    while intento <= MAX_INTENTOS:
        print(f"\n--- Intento {intento}/{MAX_INTENTOS} ---")

        try:
            guion_completo, escenas = generar_guion_escenas(pregunta, categoria, tono, region, epoca)
            guardar_en_supabase(tema_id, guion_completo, escenas)

            notificar_canal(
                CANAL_CONTENIDO,
                f"🎬 *Café con Historia — Guión de video generado*\n"
                f"*{pregunta}*\n"
                f"_{categoria} | {tono} | {region} | {epoca}_\n"
                f"*Escenas:* {len(escenas)} | *Guión:* {len(guion_completo)} chars\n"
                f"_Pendiente de imágenes — Agente V2_\n"
                f"_Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"
            )

            print(f"\n✓ Guión generado y guardado en intento {intento}")
            return

        except ErrorInfraestructura:
            raise

        except ErrorContenido as e:
            print(f"Error de contenido en intento {intento}: {e}")
            ultima_razon = str(e)

        intento += 1

    notificar_error_contenido("Agente V1 — Guión", pregunta, ultima_razon, MAX_INTENTOS)
    print(f"\n✗ No se pudo generar guión después de {MAX_INTENTOS} intentos")

if __name__ == "__main__":
    correr_agente()
