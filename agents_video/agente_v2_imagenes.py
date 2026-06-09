import os
import sys
import re
import base64
import pathlib
import requests
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from slack_sdk import WebClient
from openai import OpenAI

BASE_DIR = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "utils"))

from errores import (
    ErrorInfraestructura,
    ErrorContenido,
    notificar_error_contenido,
    notificar_canal
)

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv(BASE_DIR / ".env")

SUPABASE_URL     = os.getenv("SUPABASE_URL")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY")
SLACK_TOKEN      = os.getenv("SLACK_TOKEN")
CANAL_CONTENIDO  = os.getenv("SLACK_CHANNEL", "#contenido")
OLLAMA_URL       = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434") + "/api/generate"
MODELO           = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
OPENAI_IMG_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")

MAX_INTENTOS = 2

supabase      = create_client(SUPABASE_URL, SUPABASE_KEY)
slack         = WebClient(token=SLACK_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Estilos visuales por tono
ESTILOS_POR_TONO = {
    "pesado":     "dramatic photorealistic historical scene, high contrast, tense atmosphere, cinematic lighting with deep shadows, documentary photograph style",
    "curioso":    "colorful detailed historical illustration, warm colors, 18th century encyclopedia engraving style, vintage illustrated book aesthetic",
    "reflexivo":  "soft cinematic historical scene, warm contemplative lighting, painterly quality, atmospheric depth, arthouse historical film style",
    "inspirador": "epic luminous historical scene, golden hour lighting, heroic composition, grand historical painting style inspired by romantic masters",
}

# ============================================================
# PASO 1 — Obtener video pendiente de imágenes
# ============================================================

def obtener_video_pendiente():
    """
    Busca el video más antiguo que no tenga video_path (sin ensamblar aún).
    Retorna None si no hay nada pendiente.
    """
    print("Buscando video pendiente de imágenes...")
    try:
        resultado = supabase.table("videos")\
            .select("*, temas(pregunta, tono, region, epoca)")\
            .is_("video_path", "null")\
            .order("fecha_generacion")\
            .limit(1)\
            .execute()
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo consultar Supabase: {e}")

    if not resultado.data:
        print("No hay videos pendientes de imágenes.")
        return None

    video = resultado.data[0]
    print(f"Video encontrado: {video['temas']['pregunta']}")
    return video

# ============================================================
# UTILIDAD — Limpiar meta-texto que Llama añade al prompt
# ============================================================

def limpiar_prompt_llama(texto):
    """
    Llama suele responder con prefijos como:
      'Here is the image prompt:\n\n"actual prompt"'
    Extrae solo el contenido visual útil.
    """
    # Si hay texto entre comillas dobles (mín 40 chars), extraer el más largo
    entre_comillas = re.findall(r'"([^"]{40,})"', texto)
    if entre_comillas:
        return max(entre_comillas, key=len).strip()

    # Saltar líneas de meta-texto al inicio
    lineas = texto.strip().splitlines()
    meta_prefijos = ("here is", "here's", "below is", "the following", "prompt:")
    inicio = 0
    for i, linea in enumerate(lineas):
        if linea.strip().lower().startswith(meta_prefijos):
            inicio = i + 1
        elif linea.strip():
            break

    resultado = "\n".join(lineas[inicio:]).strip().strip('"').strip()
    return resultado if resultado else texto.strip()

# ============================================================
# PASO 2 — Generar prompt visual con Llama (en inglés)
# ============================================================

def generar_prompt_visual(descripcion_visual, region, epoca):
    """
    Traduce la descripción visual al inglés como prompt para gpt-image-1.
    """
    print("Generando prompt visual con Llama...")

    prompt = f"""You are a visual art director for a history education channel called "Café con Historia".

Translate and expand this scene description into an image generation prompt in English.

SCENE DESCRIPTION (in Spanish): {descripcion_visual}
REGION: {region}
HISTORICAL ERA: {epoca}

Create a detailed image prompt in English that:
1. Depicts the specific scene described with historically accurate details
2. Specifies the historical period, geographical setting, architecture, clothing, and atmosphere
3. Does NOT include any text, letters, numbers, or writing anywhere in the image
4. Is suitable for an educational history channel — no graphic violence or gore
5. Uses historically accurate visual details for the region and era

Respond with ONLY the image prompt in English (2-4 sentences). No explanations, no Spanish."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=300)
        data = respuesta.json()
        prompt_visual = data.get("response", "").strip()

        if not prompt_visual:
            raise ErrorContenido("Llama devolvió prompt visual vacío")

        prompt_visual = limpiar_prompt_llama(prompt_visual)
        print(f"Prompt visual: {prompt_visual[:120]}...")
        return prompt_visual

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al generar prompt visual")
    except (ErrorInfraestructura, ErrorContenido):
        raise
    except Exception as e:
        raise ErrorContenido(f"Error generando prompt visual: {e}")

# ============================================================
# PASO 3 — Generar imagen con gpt-image-1
# ============================================================

def generar_imagen(prompt_visual, tono, output_dir, num_escena):
    """
    Genera la imagen para una escena y la guarda en output_dir.
    Retorna la ruta local como string.
    """
    print(f"Generando imagen escena {num_escena} con {OPENAI_IMG_MODEL}...")

    estilo = ESTILOS_POR_TONO.get(tono, ESTILOS_POR_TONO["reflexivo"])
    prompt_completo = (
        f"{prompt_visual} "
        f"{estilo}. "
        f"No text, no letters, no numbers, no writing anywhere in the image."
    )

    print(f"Prompt ({len(prompt_completo)} chars): {prompt_completo[:100]}...")

    try:
        respuesta = openai_client.images.generate(
            model=OPENAI_IMG_MODEL,
            prompt=prompt_completo,
            size="1024x1536",
            quality="high",
            n=1
        )

        imagen_b64   = respuesta.data[0].b64_json
        imagen_bytes = base64.b64decode(imagen_b64)

        output_dir.mkdir(parents=True, exist_ok=True)
        ruta_local = output_dir / f"escena_{num_escena:02d}.png"

        with open(ruta_local, "wb") as f:
            f.write(imagen_bytes)

        print(f"✓ Imagen guardada: {ruta_local}")
        return str(ruta_local)

    except Exception as e:
        raise ErrorContenido(f"Error en {OPENAI_IMG_MODEL} (escena {num_escena}): {e}")

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print(f"CAFÉ CON HISTORIA — Agente V2 (Imágenes / {OPENAI_IMG_MODEL})")
    print("=" * 50)

    video = obtener_video_pendiente()
    if not video:
        return

    tema     = video["temas"]
    pregunta = tema["pregunta"]
    tono     = tema.get("tono", "reflexivo")
    region   = tema.get("region", "global")
    epoca    = tema.get("epoca", "contemporanea")
    video_id = video["id"]
    tema_id  = video["tema_id"]
    escenas  = video["escenas"] or []

    print(f"\nTema: {pregunta}")
    print(f"Escenas a procesar: {len(escenas)}")

    output_dir = BASE_DIR / "output" / "videos" / str(tema_id)

    imagenes_generadas = 0
    imagenes_omitidas  = 0

    for escena in escenas:
        num_escena = escena.get("numero", 0)

        # Skip si ya tiene imagen y el archivo existe
        imagen_path_existente = escena.get("imagen_path")
        if imagen_path_existente and pathlib.Path(imagen_path_existente).exists():
            print(f"Escena {num_escena}: imagen ya existe — omitiendo")
            imagenes_omitidas += 1
            continue

        descripcion_visual = escena.get("descripcion_visual", "")
        if not descripcion_visual:
            print(f"Escena {num_escena}: sin descripción visual — omitiendo")
            continue

        intento      = 1
        ultima_razon = ""
        exito        = False

        while intento <= MAX_INTENTOS:
            print(f"\nEscena {num_escena} — Intento {intento}/{MAX_INTENTOS}")
            try:
                prompt_visual = generar_prompt_visual(descripcion_visual, region, epoca)
                ruta_local    = generar_imagen(prompt_visual, tono, output_dir, num_escena)

                # Actualizar el dict de la escena
                escena["imagen_path"] = ruta_local

                # Actualizar escenas en Supabase después de cada imagen exitosa
                supabase.table("videos").update({
                    "escenas": escenas
                }).eq("id", video_id).execute()

                imagenes_generadas += 1
                exito = True
                break

            except ErrorInfraestructura:
                raise

            except ErrorContenido as e:
                print(f"Error en escena {num_escena}, intento {intento}: {e}")
                ultima_razon = str(e)

            intento += 1

        if not exito:
            print(f"✗ No se pudo generar imagen para escena {num_escena}: {ultima_razon}")

    print(f"\n✓ Proceso completado: {imagenes_generadas} generadas | {imagenes_omitidas} omitidas")

    notificar_canal(
        CANAL_CONTENIDO,
        f"🖼️ *Imágenes de video generadas* ({OPENAI_IMG_MODEL})\n"
        f"*{pregunta}*\n"
        f"_Tono: {tono} | {region} | {epoca}_\n"
        f"*Generadas:* {imagenes_generadas} | *Omitidas:* {imagenes_omitidas} de {len(escenas)} escenas\n"
        f"_Pendiente de ensamblado — Agente V3_\n"
        f"_{datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    )

if __name__ == "__main__":
    correr_agente()
