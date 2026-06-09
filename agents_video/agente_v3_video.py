import os
import sys
import re
import json
import pathlib
import subprocess
import requests
import base64
import datetime
from dotenv import load_dotenv
from supabase import create_client
from slack_sdk import WebClient
from openai import OpenAI

BASE_DIR = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "utils"))

from errores import (
    ErrorInfraestructura,
    ErrorContenido,
    notificar_canal,
    notificar_infra
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
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1-hd")
OPENAI_TTS_VOZ   = os.getenv("OPENAI_TTS_VOZ", "onyx")
MUSICA_PATH      = pathlib.Path(os.getenv("MUSICA_PATH", str(BASE_DIR / "assets" / "musica.mp3")))

supabase      = create_client(SUPABASE_URL, SUPABASE_KEY)
slack         = WebClient(token=SLACK_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ============================================================
# VERIFICACIÓN DE FFMPEG
# ============================================================

def verificar_ffmpeg():
    """Verifica que ffmpeg esté instalado en el sistema."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=10
        )
        print("✓ ffmpeg disponible")
    except FileNotFoundError:
        raise ErrorInfraestructura(
            "ffmpeg no encontrado. Instalar: apt install ffmpeg  (Linux) "
            "o descargar desde https://ffmpeg.org/download.html (Windows)"
        )

# ============================================================
# PASO 1 — Obtener video con todas las imágenes listas
# ============================================================

def obtener_video_con_imagenes():
    """
    Busca un video que no tenga video_path pero que tenga todas las imágenes generadas.
    Retorna None si no hay ninguno listo.
    """
    print("Buscando video con imágenes completas...")
    try:
        resultado = supabase.table("videos")\
            .select("*, temas(pregunta, tono, region, epoca)")\
            .is_("video_path", "null")\
            .order("fecha_generacion")\
            .execute()
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo consultar Supabase: {e}")

    for video in resultado.data:
        escenas = video.get("escenas") or []
        if not escenas:
            continue

        # Verificar que todas las escenas tienen imagen y el archivo existe
        todas_tienen_imagen = True
        for escena in escenas:
            imagen_path = escena.get("imagen_path")
            if not imagen_path or not pathlib.Path(imagen_path).exists():
                todas_tienen_imagen = False
                break

        if todas_tienen_imagen:
            print(f"Video listo para ensamblar: {video['temas']['pregunta']}")
            return video
        else:
            print(f"Video aún sin todas las imágenes — omitiendo: {video.get('id')}")

    print("No hay videos listos para ensamblar.")
    return None

# ============================================================
# UTILIDADES DE AUDIO/VIDEO
# ============================================================

def get_duracion_audio(audio_path):
    """Obtiene la duración de un archivo de audio en segundos usando ffprobe."""
    try:
        resultado = subprocess.run(
            [
                "ffprobe",
                "-i", str(audio_path),
                "-show_entries", "format=duration",
                "-v", "quiet",
                "-of", "csv=p=0"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        duracion_str = resultado.stdout.strip()
        if duracion_str:
            return float(duracion_str)
    except Exception as e:
        print(f"No se pudo obtener duración de {audio_path}: {e}")
    return 5.0

def generar_audio_escena(narracion, audio_path):
    """Genera el audio TTS para una escena y lo guarda en audio_path."""
    print(f"Generando audio TTS: {str(audio_path).split('/')[-1]}")
    try:
        respuesta = openai_client.audio.speech.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_TTS_VOZ,
            input=narracion
        )
        with open(audio_path, "wb") as f:
            f.write(respuesta.content)
        print(f"✓ Audio guardado: {audio_path}")
    except Exception as e:
        raise ErrorContenido(f"Error generando audio TTS: {e}")

def crear_clip_escena(imagen_path, duracion, clip_path, num_escena):
    """
    Crea un clip de video con efecto Ken Burns a partir de una imagen.
    Usa 4 variantes de movimiento según el número de escena.
    """
    print(f"Creando clip escena {num_escena} (duración: {duracion:.1f}s)...")

    variante = num_escena % 4
    if variante == 0:
        # Zoom in centro
        z_expr = "min(zoom+0.0015,1.5)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif variante == 1:
        # Zoom in esquina superior izquierda
        z_expr = "min(zoom+0.0015,1.5)"
        x_expr = "0"
        y_expr = "0"
    elif variante == 2:
        # Zoom in esquina superior derecha
        z_expr = "min(zoom+0.0015,1.5)"
        x_expr = "iw-iw/zoom"
        y_expr = "0"
    else:
        # Zoom in centro inferior
        z_expr = "min(zoom+0.0015,1.5)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih-ih/zoom"

    frames = int(duracion * 30)
    vf = (
        f"scale=1440:2160:force_original_aspect_ratio=increase,"
        f"crop=1440:2160,"
        f"zoompan=z='{z_expr}':d={frames}:"
        f"x='{x_expr}':y='{y_expr}':s=1080x1920:fps=30,"
        f"fps=30,format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-t", str(duracion + 0.5),
        "-i", str(imagen_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-t", str(duracion),
        str(clip_path)
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        print(f"✓ Clip creado: {str(clip_path).split('/')[-1]}")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        raise ErrorContenido(
            f"ffmpeg falló en escena {num_escena}: {stderr[-500:]}"
        )

# ============================================================
# PASO 2 — Ensamblar video completo
# ============================================================

def ensamblar_video(video_dir, escenas):
    """
    Para cada escena: genera audio, obtiene duración, crea clip.
    Luego concatena clips y audio, mezcla con música de fondo si existe.
    Retorna la ruta absoluta del video_final.mp4.
    """
    video_dir = pathlib.Path(video_dir)
    video_dir.mkdir(parents=True, exist_ok=True)

    clips_paths = []
    audios_paths = []

    print(f"\nEnsamblando {len(escenas)} escenas...")

    for escena in escenas:
        num_escena = escena.get("numero", 0)
        narracion  = escena.get("narracion", "")
        imagen_path = pathlib.Path(escena["imagen_path"])

        # Generar audio
        audio_path = video_dir / f"audio_escena_{num_escena:02d}.mp3"
        if not audio_path.exists():
            generar_audio_escena(narracion, audio_path)

        # Obtener duración del audio
        duracion = get_duracion_audio(audio_path)
        print(f"Escena {num_escena}: {duracion:.2f}s")

        # Crear clip de video con Ken Burns
        clip_path = video_dir / f"clip_{num_escena:02d}.mp4"
        if not clip_path.exists():
            crear_clip_escena(imagen_path, duracion, clip_path, num_escena)

        clips_paths.append(clip_path)
        audios_paths.append(audio_path)

    # Crear archivo de lista para clips
    clips_list_path = video_dir / "clips_list.txt"
    with open(clips_list_path, "w", encoding="utf-8") as f:
        for cp in clips_paths:
            f.write(f"file '{cp.resolve()}'\n")

    # Crear archivo de lista para audios
    audio_list_path = video_dir / "audio_list.txt"
    with open(audio_list_path, "w", encoding="utf-8") as f:
        for ap in audios_paths:
            f.write(f"file '{ap.resolve()}'\n")

    video_sin_audio = video_dir / "video_sin_audio.mp4"
    narracion_mp3   = video_dir / "narracion.mp3"
    video_final     = video_dir / "video_final.mp4"

    # Concatenar clips de video
    print("Concatenando clips de video...")
    cmd_concat_video = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(clips_list_path),
        "-c", "copy",
        str(video_sin_audio)
    ]
    try:
        subprocess.run(cmd_concat_video, check=True, capture_output=True, timeout=600)
        print("✓ Clips concatenados")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        raise ErrorContenido(f"Error concatenando clips: {stderr[-500:]}")

    # Concatenar audios de narración
    print("Concatenando audios de narración...")
    cmd_concat_audio = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(audio_list_path),
        "-c", "copy",
        str(narracion_mp3)
    ]
    try:
        subprocess.run(cmd_concat_audio, check=True, capture_output=True, timeout=300)
        print("✓ Audios concatenados")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        raise ErrorContenido(f"Error concatenando audios: {stderr[-500:]}")

    # Mezclar con música de fondo si existe
    if MUSICA_PATH.exists():
        print(f"Mezclando con música de fondo: {MUSICA_PATH.name}")
        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(video_sin_audio),
            "-i", str(narracion_mp3),
            "-stream_loop", "-1",
            "-i", str(MUSICA_PATH),
            "-filter_complex", "[2:a]volume=0.15[bg];[1:a][bg]amix=inputs=2:duration=first[audio]",
            "-map", "0:v",
            "-map", "[audio]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(video_final)
        ]
    else:
        print("Sin música de fondo — usando solo narración")
        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(video_sin_audio),
            "-i", str(narracion_mp3),
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(video_final)
        ]

    try:
        subprocess.run(cmd_final, check=True, capture_output=True, timeout=600)
        print(f"✓ Video final: {video_final}")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        raise ErrorContenido(f"Error ensamblando video final: {stderr[-500:]}")

    return str(video_final.resolve())

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente V3 (Video)")
    print("=" * 50)

    verificar_ffmpeg()

    video = obtener_video_con_imagenes()
    if not video:
        return

    tema     = video["temas"]
    pregunta = tema["pregunta"]
    video_id = video["id"]
    tema_id  = video["tema_id"]
    escenas  = video["escenas"] or []

    print(f"\nTema: {pregunta}")
    print(f"Escenas: {len(escenas)}")

    video_dir = BASE_DIR / "output" / "videos" / str(tema_id)

    try:
        video_final_path = ensamblar_video(video_dir, escenas)

        # Actualizar tabla videos con la ruta del video final
        supabase.table("videos").update({
            "video_path": video_final_path
        }).eq("id", video_id).execute()

        print(f"\n✓ Video ensamblado y guardado: {video_final_path}")

        notificar_canal(
            CANAL_CONTENIDO,
            f"🎥 *Video ensamblado exitosamente*\n"
            f"*{pregunta}*\n"
            f"_Escenas: {len(escenas)} | {tema.get('tono', '')} | {tema.get('region', '')}_\n"
            f"`{video_final_path}`\n"
            f"_Pendiente de publicación — Agente V4_\n"
            f"_{datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}_"
        )

    except ErrorContenido as e:
        print(f"\n✗ Error ensamblando video: {e}")
        notificar_canal(
            os.getenv("SLACK_CANAL_ERRORES", "#errores"),
            f"⚠️ *Error en Agente V3 — Video*\n"
            f"*Tema:* {pregunta}\n"
            f"*Error:* {str(e)}\n"
            f"_El video NO fue ensamblado._"
        )
        raise

if __name__ == "__main__":
    correr_agente()
