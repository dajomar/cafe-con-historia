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

IMAGES_DIR   = BASE_DIR / "images"
MAX_INTENTOS = 2

supabase      = create_client(SUPABASE_URL, SUPABASE_KEY)
slack         = WebClient(token=SLACK_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Estilos visuales por tono — Opción D (Híbrido)
ESTILOS_POR_TONO = {
    "pesado":     "dramatic photorealistic historical scene, high contrast, tense atmosphere, cinematic lighting with deep shadows, documentary photograph style",
    "curioso":    "colorful detailed historical illustration, warm colors, 18th century encyclopedia engraving style, vintage illustrated book aesthetic",
    "reflexivo":  "soft cinematic historical scene, warm contemplative lighting, painterly quality, atmospheric depth, arthouse historical film style",
    "inspirador": "epic luminous historical scene, golden hour lighting, heroic composition, grand historical painting style inspired by romantic masters",
}

# ============================================================
# PASO 1 — Obtener contenido aprobado sin imagen
# ============================================================

def obtener_contenido_para_imagen():
    print("Buscando contenido aprobado sin imagen...")
    resultado = supabase.table("contenido")\
        .select("*, temas(pregunta, categoria, tono, region, epoca)")\
        .eq("aprobado", True)\
        .is_("contenido_facebook", "null")\
        .is_("imagen_url", "null")\
        .order("fecha_generacion", desc=True)\
        .limit(1)\
        .execute()

    if not resultado.data:
        print("No hay contenido pendiente de imagen.")
        return None

    contenido = resultado.data[0]
    print(f"Contenido encontrado: {contenido['temas']['pregunta']}")
    return contenido

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

def generar_prompt_visual(pregunta, region, epoca, contenido_texto):
    print("Generando prompt visual con Llama...")

    prompt = f"""You are a visual art director for a history education channel called "Café con Historia".

Based on this historical topic, create an image generation prompt in English.

TOPIC (in Spanish): {pregunta}
REGION: {region}
HISTORICAL ERA: {epoca}
CONTENT SUMMARY (in Spanish): {contenido_texto[:400]}

Create a detailed image prompt in English that:
1. Depicts a specific historical scene, setting, or moment directly related to the topic
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
# PASO 3 — Generar imagen con gpt-image-1 y guardar localmente
# ============================================================

def generar_y_guardar_imagen(prompt_visual, tono, contenido_id):
    print(f"Generando imagen con {OPENAI_IMG_MODEL}...")

    estilo = ESTILOS_POR_TONO.get(tono, ESTILOS_POR_TONO["reflexivo"])
    prompt_completo = (
        f"{prompt_visual} "
        f"{estilo}. "
        f"No text, no letters, no numbers, no writing anywhere in the image."
    )

    print(f"Prompt ({len(prompt_completo)} chars): {prompt_completo[:150]}...")

    try:
        respuesta = openai_client.images.generate(
            model=OPENAI_IMG_MODEL,
            prompt=prompt_completo,
            size="1024x1536",  # portrait — compatible con gpt-image-1
            quality="high",    # gpt-image-1 usa "high", no "hd"
            n=1
        )

        # gpt-image-1 devuelve base64, no URL
        imagen_b64   = respuesta.data[0].b64_json
        imagen_bytes = base64.b64decode(imagen_b64)

        IMAGES_DIR.mkdir(exist_ok=True)
        fecha      = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_local = IMAGES_DIR / f"{fecha}_{contenido_id}.png"

        with open(ruta_local, "wb") as f:
            f.write(imagen_bytes)

        print(f"Imagen guardada: {ruta_local}")
        return str(ruta_local), prompt_completo

    except Exception as e:
        raise ErrorContenido(f"Error en {OPENAI_IMG_MODEL}: {e}")

# ============================================================
# PASO 4 — Guardar ruta e información en Supabase
# ============================================================

def guardar_imagen_en_supabase(contenido_id, ruta_local, prompt_completo):
    try:
        supabase.table("contenido").update({
            "imagen_url":    ruta_local,
            "imagen_prompt": prompt_completo
        }).eq("id", contenido_id).execute()
        print("✓ Imagen registrada en Supabase")
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo registrar imagen en Supabase: {e}")

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print(f"CAFÉ CON HISTORIA — Agente Imagen ({OPENAI_IMG_MODEL})")
    print("=" * 50)

    contenido = obtener_contenido_para_imagen()
    if not contenido:
        return

    tema            = contenido["temas"]
    pregunta        = tema["pregunta"]
    tono            = tema.get("tono", "reflexivo")
    region          = tema.get("region", "global")
    epoca           = tema.get("epoca", "contemporanea")
    contenido_id    = contenido["id"]
    contenido_texto = contenido["contenido_slack"]

    print(f"\nTema: {pregunta}")
    print(f"Estilo visual: {tono} | {region} | {epoca}")

    intento      = 1
    ultima_razon = ""

    while intento <= MAX_INTENTOS:
        print(f"\n--- Intento {intento}/{MAX_INTENTOS} ---")

        try:
            prompt_visual            = generar_prompt_visual(pregunta, region, epoca, contenido_texto)
            ruta_local, prompt_final = generar_y_guardar_imagen(prompt_visual, tono, contenido_id)
            guardar_imagen_en_supabase(contenido_id, ruta_local, prompt_final)

            notificar_canal(
                CANAL_CONTENIDO,
                f"🖼️ *Imagen generada* ({OPENAI_IMG_MODEL})\n"
                f"*{pregunta}*\n"
                f"_Estilo: {tono} | {region} | {epoca}_\n"
                f"`{ruta_local}`"
            )
            print(f"\n✓ Imagen generada y guardada en intento {intento}")
            return

        except ErrorInfraestructura:
            raise

        except ErrorContenido as e:
            print(f"Error en intento {intento}: {e}")
            ultima_razon = str(e)

        intento += 1

    notificar_error_contenido("Agente Imagen", pregunta, ultima_razon, MAX_INTENTOS)
    print(f"\n✗ No se pudo generar imagen después de {MAX_INTENTOS} intentos")

if __name__ == "__main__":
    correr_agente()
