import os
import random
import requests
import json
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
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#general")
OLLAMA_URL    = "http://localhost:11434/api/generate"
MODELO        = "llama3.1"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# PASO 1 — Escoger tema
# ============================================================

def escoger_tema():
    print("Buscando tema pendiente...")
    resultado = supabase.table("temas").select("*").eq("publicado", False).execute()

    if not resultado.data:
        print("No hay temas pendientes.")
        return None

    tema = random.choice(resultado.data)
    print(f"Tema escogido: {tema['pregunta']}")
    return tema

# ============================================================
# PASO 2 — Generar contenido con Llama
# ============================================================

def generar_contenido(pregunta):
    print(f"Generando contenido con {MODELO}...")

    prompt = f"""Eres un divulgador de historia y geografía con el enfoque: "La historia explica el presente".

Tu canal se llama Café con Historia.

Responde esta pregunta de forma clara, interesante y accesible para cualquier persona:

PREGUNTA: {pregunta}

Tu respuesta debe:
1. Explicar el contexto histórico que originó la situación
2. Conectar ese pasado con lo que vemos hoy
3. Usar un tono conversacional, como si le explicaras a un amigo tomando un café
4. Tener entre 200 y 300 palabras
5. Terminar con una reflexión que invite a pensar

Responde directamente sin introducción ni meta-comentarios."""

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False
    }

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        # respuesta = requests.post(OLLAMA_URL, json=payload, timeout=120)
        data = respuesta.json()
        contenido = data.get("response", "").strip()
        print(f"Contenido generado: {len(contenido)} caracteres")
        return contenido
    except Exception as e:
        print(f"Error generando contenido: {e}")
        return None

# ============================================================
# PASO 3 — Adaptar para Slack
# ============================================================

def formatear_slack(pregunta, contenido, categoria):
    mensaje = f"""*☕ Café con Historia*
*{pregunta}*
_{categoria}_

{contenido}

---
_Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"""
    return mensaje

# ============================================================
# PASO 4 — Enviar a Slack
# ============================================================

def enviar_slack(mensaje):
    print(f"Enviando a Slack en {SLACK_CHANNEL}...")
    try:
        resultado = slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=mensaje,
            mrkdwn=True
        )
        print(f"✓ Mensaje enviado a Slack")
        return True
    except SlackApiError as e:
        print(f"Error Slack: {e.response['error']}")
        return False

# ============================================================
# PASO 5 — Guardar en Supabase y marcar como publicado
# ============================================================

def guardar_contenido(tema_id, contenido_slack):
    supabase.table("contenido").insert({
        "tema_id": tema_id,
        "contenido_slack": contenido_slack,
        "modelo_usado": MODELO
    }).execute()

    supabase.table("temas").update({
        "publicado": True,
        "fecha_publicacion": datetime.now().isoformat(),
        "plataforma": "slack"
    }).eq("id", tema_id).execute()

    print(f"✓ Tema marcado como publicado")

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente 1")
    print("=" * 50)

    # Paso 1 — Escoger tema
    tema = escoger_tema()
    if not tema:
        print("No hay temas disponibles. Agrega más temas a la base de datos.")
        return

    # Paso 2 — Generar contenido
    contenido = generar_contenido(tema["pregunta"])
    if not contenido:
        print("Error generando contenido.")
        return

    # Paso 3 — Formatear
    mensaje_slack = formatear_slack(
        tema["pregunta"],
        contenido,
        tema["categoria"]
    )

    # Paso 4 — Enviar a Slack
    enviado = enviar_slack(mensaje_slack)
    if not enviado:
        return

    # Paso 5 — Guardar en base de datos
    guardar_contenido(tema["id"], mensaje_slack)

    print("\n¡Agente completado exitosamente!")
    print(f"Tema: {tema['pregunta']}")

if __name__ == "__main__":
    correr_agente()