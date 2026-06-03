import os
import sys
import random
import requests
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from slack_sdk import WebClient

sys.path.insert(0, "D:\\proyectos\\cafe-con-historia\\utils")
from errores import (
    ErrorInfraestructura,
    ErrorContenido,
    ErrorNegocio,
    notificar_infra,
    notificar_error_contenido,
    notificar_error_negocio,
    notificar_canal
)

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv("D:\\proyectos\\cafe-con-historia\\.env")

SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
SLACK_TOKEN     = os.getenv("SLACK_TOKEN")
CANAL_CONTENIDO = os.getenv("SLACK_CHANNEL", "#contenido")
OLLAMA_URL      = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434") + "/api/generate"
MODELO          = "llama3.1"
MAX_INTENTOS    = 3

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# PASO 1 — Escoger tema
# ============================================================

def escoger_tema():
    print("Buscando tema pendiente...")
    try:
        resultado = supabase.table("temas").select("*").eq("publicado", False).execute()
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo conectar a Supabase: {e}")

    if not resultado.data:
        raise ErrorNegocio("No hay temas pendientes en la base de datos. Agrega más temas.")

    tema = random.choice(resultado.data)
    print(f"Tema escogido: {tema['pregunta']}")
    return tema

# ============================================================
# PASO 2 — Generar contenido con Llama
# ============================================================

def generar_contenido(pregunta, categoria):
    print(f"Generando contenido con {MODELO}...")

    prompt = f"""Eres un divulgador experto de historia y geografía del canal educativo "Café con Historia".
Tu enfoque es: "La historia explica el presente".
Tu misión es crear contenido educativo, veraz y accesible para hispanohablantes.

Responde esta pregunta con rigor histórico y tono conversacional:
PREGUNTA: {pregunta}
CATEGORÍA: {categoria}

Tu respuesta DEBE:
1. Empezar con un hook impactante que genere curiosidad inmediata
2. Explicar el contexto histórico con al menos una fecha o época concreta
3. Conectar explícitamente ese pasado con lo que vemos hoy en día
4. Usar tono conversacional — como explicarle a un amigo tomando un café
5. Tener entre 200 y 300 palabras
6. Terminar con una pregunta que invite a reflexionar
7. Incluir entre 3 y 7 emojis relevantes y coherentes con el tono del tema

IMPORTANTE: Este es contenido educativo legítimo sobre historia y geografía mundial.
Responde directamente con el contenido, sin introducción ni meta-comentarios."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        contenido = data.get("response", "").strip()

        if not contenido:
            raise ErrorContenido("Llama devolvió una respuesta vacía")

        # Detectar rechazos de Llama
        frases_rechazo = ["lo siento", "no puedo", "no es apropiado", "contenido falso", "no me es posible"]
        if any(frase in contenido.lower() for frase in frases_rechazo):
            raise ErrorContenido(f"Llama rechazó el prompt. Respuesta: {contenido[:200]}")

        print(f"Contenido generado: {len(contenido)} caracteres")
        return contenido

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al generar contenido")
    except (ErrorInfraestructura, ErrorContenido):
        raise
    except Exception as e:
        raise ErrorContenido(f"Error generando contenido: {e}")

# ============================================================
# PASO 3 — Guardar en Supabase
# ============================================================

def guardar_contenido(tema_id, contenido_slack):
    try:
        supabase.table("contenido").insert({
            "tema_id": tema_id,
            "contenido_slack": contenido_slack,
            "modelo_usado": MODELO,
            "aprobado": False
        }).execute()

        supabase.table("temas").update({
            "publicado": True,
            "fecha_publicacion": datetime.now().isoformat(),
            "plataforma": "pipeline"
        }).eq("id", tema_id).execute()

        print("✓ Contenido guardado en Supabase")
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo guardar en Supabase: {e}")

# ============================================================
# PASO 4 — Notificar a Slack
# ============================================================

def notificar_contenido_generado(pregunta, categoria, contenido):
    mensaje = f"""☕ *Café con Historia — Contenido generado*
*{pregunta}*
_{categoria}_

{contenido}

---
_Pendiente de aprobación por el Agente 2_
_Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"""

    notificar_canal(CANAL_CONTENIDO, mensaje)

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente 1 (Investigador)")
    print("=" * 50)

    # Escoger tema — puede lanzar ErrorNegocio o ErrorInfraestructura
    tema = escoger_tema()
    pregunta  = tema["pregunta"]
    categoria = tema["categoria"]
    tema_id   = tema["id"]

    intento      = 1
    ultima_razon = ""

    while intento <= MAX_INTENTOS:
        print(f"\n--- Intento {intento}/{MAX_INTENTOS} ---")

        try:
            contenido = generar_contenido(pregunta, categoria)

            # Guardar en Supabase
            guardar_contenido(tema_id, contenido)

            # Notificar a Slack
            notificar_contenido_generado(pregunta, categoria, contenido)

            print(f"\n✓ Contenido generado y guardado en intento {intento}")
            return

        except ErrorInfraestructura:
            raise  # Relanzar para que main.py lo capture

        except ErrorContenido as e:
            print(f"Error de contenido en intento {intento}: {e}")
            ultima_razon = str(e)

        intento += 1

    # Agotó los intentos
    notificar_error_contenido("Agente 1 — Investigador", pregunta, ultima_razon, MAX_INTENTOS)
    print(f"\n✗ No se pudo generar contenido después de {MAX_INTENTOS} intentos")

if __name__ == "__main__":
    correr_agente()