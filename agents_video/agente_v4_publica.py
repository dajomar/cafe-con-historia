import os
import sys
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
    notificar_canal,
    notificar_infra,
    verificar_error_facebook
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
FB_PAGE_TOKEN   = os.getenv("FB_PAGE_TOKEN")
FB_PAGE_ID      = os.getenv("FB_PAGE_ID")

FB_GRAPH_VIDEO  = f"https://graph-video.facebook.com/v25.0/{FB_PAGE_ID}/video_reels"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# PASO 1 — Obtener video listo para publicar
# ============================================================

def obtener_video_listo():
    """
    Busca el video más antiguo con video_path definido y que no haya sido publicado.
    También intenta obtener el contenido_facebook del tema si existe.
    """
    print("Buscando video listo para publicar...")
    try:
        resultado = supabase.table("videos")\
            .select("*, temas(pregunta, tono, region, epoca)")\
            .eq("video_publicado", False)\
            .not_.is_("video_path", "null")\
            .order("fecha_generacion")\
            .limit(1)\
            .execute()
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo consultar Supabase: {e}")

    if not resultado.data:
        print("No hay videos listos para publicar.")
        return None

    video = resultado.data[0]
    print(f"Video listo: {video['temas']['pregunta']}")
    return video

# ============================================================
# PASO 2 — Obtener o generar caption
# ============================================================

def obtener_caption(tema_id, guion, pregunta):
    """
    Intenta reutilizar el contenido_facebook del pipeline de texto.
    Si no existe, genera un caption con Llama.
    """
    print("Obteniendo caption para el Reel...")

    # Intentar usar contenido_facebook existente del pipeline de texto
    try:
        resultado = supabase.table("contenido")\
            .select("contenido_facebook")\
            .eq("tema_id", tema_id)\
            .not_.is_("contenido_facebook", "null")\
            .limit(1)\
            .execute()

        if resultado.data and resultado.data[0].get("contenido_facebook"):
            caption = resultado.data[0]["contenido_facebook"]
            print(f"✓ Caption reutilizado del pipeline de texto ({len(caption)} chars)")
            return caption
    except Exception as e:
        print(f"No se pudo consultar contenido existente: {e}")

    # Generar caption con Llama
    print("Generando caption con Llama...")
    prompt = (
        f"Crea un caption para Facebook de máximo 100 palabras basado en este guión. "
        f"Incluye 3-5 emojis relevantes, un hook inicial y 3-4 hashtags al final. "
        f"El canal se llama 'Café con Historia'. "
        f"Responde solo con el caption, sin explicaciones.\n\n"
        f"Guión: {guion[:500]}"
    )

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=300)
        data = respuesta.json()
        caption = data.get("response", "").strip()

        if not caption:
            caption = f"☕ {pregunta}\n\n#CaféConHistoria #Historia #Educación"
            print("Llama devolvió caption vacío — usando caption por defecto")
        else:
            print(f"✓ Caption generado por Llama ({len(caption)} chars)")

        return caption

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al generar caption")
    except Exception as e:
        print(f"Error generando caption: {e} — usando caption por defecto")
        return f"☕ {pregunta}\n\n#CaféConHistoria #Historia #Educación"

# ============================================================
# PASO 3 — Publicar Reel en Facebook
# ============================================================

def publicar_reel_facebook(video_path, descripcion):
    """
    Publica un Reel en Facebook usando la API de video en 3 pasos:
    1. Iniciar sesión de upload (start)
    2. Subir el archivo binario (upload)
    3. Finalizar y publicar (finish)
    Retorna el video_id del Reel publicado.
    """
    video_path = pathlib.Path(video_path)
    if not video_path.exists():
        raise ErrorContenido(f"El archivo de video no existe: {video_path}")

    file_size = os.path.getsize(video_path)
    print(f"Publicando Reel ({file_size / 1024 / 1024:.1f} MB)...")

    # ---- Paso 1: Iniciar sesión de upload ----
    print("Paso 1: Iniciando upload...")
    r_start = requests.post(
        FB_GRAPH_VIDEO,
        data={
            "upload_phase":    "start",
            "video_file_size": file_size,
            "access_token":    FB_PAGE_TOKEN,
        },
        timeout=60
    )
    data_start = r_start.json()

    if "error" in data_start:
        verificar_error_facebook(data_start["error"])

    video_id   = data_start.get("video_id")
    upload_url = data_start.get("upload_url")

    if not video_id or not upload_url:
        raise ErrorContenido(f"Respuesta inesperada en inicio de upload: {data_start}")

    print(f"Video ID: {video_id}")

    # ---- Paso 2: Subir el archivo ----
    print("Paso 2: Subiendo archivo de video...")
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    r_upload = requests.post(
        upload_url,
        headers={
            "Authorization": f"OAuth {FB_PAGE_TOKEN}",
            "offset":        "0",
            "file_size":     str(file_size),
        },
        data=video_bytes,
        timeout=600
    )
    data_upload = r_upload.json()

    if "error" in data_upload:
        verificar_error_facebook(data_upload["error"])

    print("✓ Archivo subido")

    # ---- Paso 3: Finalizar y publicar ----
    print("Paso 3: Publicando Reel...")
    r_finish = requests.post(
        FB_GRAPH_VIDEO,
        data={
            "upload_phase":  "finish",
            "video_id":      video_id,
            "video_state":   "PUBLISHED",
            "description":   descripcion,
            "access_token":  FB_PAGE_TOKEN,
        },
        timeout=120
    )
    data_finish = r_finish.json()

    if "error" in data_finish:
        verificar_error_facebook(data_finish["error"])

    if not data_finish.get("success"):
        raise ErrorContenido(f"Facebook no confirmó publicación del Reel: {data_finish}")

    print(f"✓ Reel publicado — Video ID: {video_id}")
    return video_id

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente V4 (Publicador Reels)")
    print("=" * 50)

    video = obtener_video_listo()
    if not video:
        return

    tema     = video["temas"]
    pregunta = tema["pregunta"]
    video_id_db = video["id"]
    tema_id  = video["tema_id"]
    guion    = video.get("guion", "")
    video_path = video["video_path"]

    print(f"\nTema: {pregunta}")
    print(f"Video: {video_path}")

    caption = obtener_caption(tema_id, guion, pregunta)

    try:
        fb_reel_id = publicar_reel_facebook(video_path, caption)

        # Actualizar Supabase
        supabase.table("videos").update({
            "video_publicado":   True,
            "fb_reel_id":        fb_reel_id,
            "fecha_publicacion": datetime.now().isoformat()
        }).eq("id", video_id_db).execute()

        print(f"\n✓ Reel publicado en Facebook: {fb_reel_id}")

        notificar_canal(
            CANAL_CONTENIDO,
            f"✅ *Reel publicado en Facebook*\n"
            f"*{pregunta}*\n"
            f"_Tono: {tema.get('tono', '')} | {tema.get('region', '')} | {tema.get('epoca', '')}_\n"
            f"*Facebook Reel ID:* `{fb_reel_id}`\n"
            f"_{datetime.now().strftime('%d/%m/%Y %H:%M')}_"
        )

    except ErrorInfraestructura:
        raise

    except ErrorContenido as e:
        print(f"\n✗ Error publicando Reel: {e}")
        notificar_canal(
            os.getenv("SLACK_CANAL_ERRORES", "#errores"),
            f"⚠️ *Error en Agente V4 — Publicador Reels*\n"
            f"*Tema:* {pregunta}\n"
            f"*Error:* {str(e)}\n"
            f"_El Reel NO fue publicado._"
        )
        raise

if __name__ == "__main__":
    correr_agente()
