import os
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

SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")
FB_PAGE_TOKEN  = os.getenv("FB_PAGE_TOKEN")
FB_PAGE_ID     = os.getenv("FB_PAGE_ID")
SLACK_TOKEN    = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL  = os.getenv("SLACK_CHANNEL", "#contenido")
OLLAMA_URL     = "http://localhost:11434/api/generate"
MODELO         = "llama3.1"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# PASO 1 — Obtener último contenido generado
# ============================================================

def obtener_ultimo_contenido():
    print("Buscando último contenido generado...")
    resultado = supabase.table("contenido")\
        .select("*, temas(pregunta, categoria)")\
        .order("fecha_generacion", desc=True)\
        .limit(1)\
        .execute()

    if not resultado.data:
        print("No hay contenido generado aún. Corre el Agente 1 primero.")
        return None

    contenido = resultado.data[0]
    print(f"Contenido encontrado: {contenido['temas']['pregunta']}")
    return contenido

# ============================================================
# PASO 2 — Adaptar para Facebook con Llama
# ============================================================

def adaptar_para_facebook(pregunta, contenido_largo, categoria):
    print("Adaptando contenido para Facebook...")

    prompt = f"""Eres el community manager de Café con Historia, un canal educativo en Facebook.

Tienes este contenido largo sobre la siguiente pregunta:
PREGUNTA: {pregunta}
CATEGORÍA: {categoria}

CONTENIDO ORIGINAL:
{contenido_largo}

Tu tarea es crear un post para Facebook que:
1. Empiece con un hook IMPACTANTE en la primera línea que genere curiosidad inmediata
2. Use emojis relevantes y acordes al tema (máximo 5-7 emojis en todo el post)
3. Sea más corto que el original — máximo 300 palabras
4. Tenga un tono conversacional y cercano, como si hablaras con amigos
5. Termine con una pregunta que invite a comentar
6. Incluya 3-5 hashtags relevantes al final

El post debe enganchar al público hispanohablante de Facebook.
Responde SOLO con el texto del post, sin explicaciones ni meta-comentarios."""

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
        print(f"Error adaptando contenido: {e}")
        return None

# ============================================================
# PASO 3 — Publicar en Facebook
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
            print(f"✓ Publicado en Facebook — Post ID: {data['id']}")
            return data["id"]
        else:
            print(f"Error Facebook: {data}")
            return None
    except Exception as e:
        print(f"Error publicando: {e}")
        return None

# ============================================================
# PASO 4 — Enviar a Slack
# ============================================================

def enviar_slack(pregunta, post_facebook, fb_post_id):
    print(f"Enviando resumen a Slack...")
    mensaje = f"""*☕ Café con Historia — Facebook*
*{pregunta}*

{post_facebook}

---
🔗 Post ID: `{fb_post_id}`
_Publicado: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"""

    try:
        slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=mensaje,
            mrkdwn=True
        )
        print(f"✓ Resumen enviado a Slack")
    except SlackApiError as e:
        print(f"Error Slack: {e.response['error']}")

# ============================================================
# PASO 5 — Guardar post en Supabase
# ============================================================

def guardar_post_facebook(contenido_id, post_facebook):
    supabase.table("contenido").update({
        "contenido_facebook": post_facebook,
    }).eq("id", contenido_id).execute()
    print(f"✓ Post guardado en Supabase")

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente 2 (Facebook + Slack)")
    print("=" * 50)

    # Paso 1 — Obtener contenido
    contenido = obtener_ultimo_contenido()
    if not contenido:
        return

    pregunta        = contenido["temas"]["pregunta"]
    categoria       = contenido["temas"]["categoria"]
    contenido_largo = contenido["contenido_slack"]

    # Paso 2 — Adaptar para Facebook
    post_facebook = adaptar_para_facebook(pregunta, contenido_largo, categoria)
    if not post_facebook:
        return

    print(f"\nPost generado:\n{'-'*40}\n{post_facebook}\n{'-'*40}")

    # Paso 3 — Publicar en Facebook
    fb_post_id = publicar_facebook(post_facebook)
    if not fb_post_id:
        return

    # Paso 4 — Enviar a Slack
    enviar_slack(pregunta, post_facebook, fb_post_id)

    # Paso 5 — Guardar en Supabase
    guardar_post_facebook(contenido["id"], post_facebook)

    print("\n¡Agente 2 completado exitosamente!")
    print(f"Tema: {pregunta}")
    print(f"Facebook Post ID: {fb_post_id}")

if __name__ == "__main__":
    correr_agente()
