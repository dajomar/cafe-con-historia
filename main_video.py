import os
import sys
import traceback
import pathlib
from datetime import datetime
from dotenv import load_dotenv

# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = pathlib.Path(__file__).parent

load_dotenv(BASE_DIR / ".env")

SLACK_TOKEN     = os.getenv("SLACK_TOKEN")
CANAL_CONTENIDO = os.getenv("SLACK_CHANNEL", "#contenido")
CANAL_INFRA     = os.getenv("SLACK_CANAL_INFRA", "#infraestructura")
CANAL_ERRORES   = os.getenv("SLACK_CANAL_ERRORES", "#errores")

sys.path.insert(0, str(BASE_DIR / "utils"))
sys.path.insert(0, str(BASE_DIR / "agents_video"))

from errores import (
    ErrorInfraestructura,
    ErrorNegocio,
    verificar_ollama,
    notificar_infra,
    notificar_canal
)

# ============================================================
# LOGGING
# ============================================================

def log(mensaje):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{timestamp}] {mensaje}"
    print(linea)
    with open(BASE_DIR / "pipeline_video.log", "a", encoding="utf-8") as f:
        f.write(linea + "\n")

# ============================================================
# NOTIFICACIONES
# ============================================================

def notificar_inicio():
    notificar_canal(
        CANAL_CONTENIDO,
        f"🎬 *Café con Historia* — Pipeline de Video iniciado\n"
        f"_{datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    )

def notificar_exito():
    notificar_canal(
        CANAL_CONTENIDO,
        f"✅ *Pipeline de Video completado exitosamente*\n"
        f"_{datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    )

# ============================================================
# VERIFICACIONES PREVIAS
# ============================================================

def verificar_infraestructura():
    log("Verificando infraestructura del pipeline de video...")

    # Verificar OPENAI_API_KEY
    if not os.getenv("OPENAI_API_KEY"):
        log("ERROR — OPENAI_API_KEY no está configurado en .env")
        notificar_infra("Pipeline de Video: OPENAI_API_KEY no está configurado en .env")
        sys.exit(1)

    # Verificar Ollama
    try:
        verificar_ollama()
        log("✓ Ollama corriendo")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA — Ollama: {e}")
        notificar_infra(str(e))
        sys.exit(1)

    log("✓ Infraestructura lista")

# ============================================================
# EJECUTAR AGENTES
# ============================================================

def ejecutar_agente(nombre, modulo_nombre):
    log(f"Iniciando {nombre}...")
    import importlib
    agente = importlib.import_module(modulo_nombre)
    importlib.reload(agente)
    agente.correr_agente()
    log(f"✓ {nombre} completado")

# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def main():
    log("=" * 50)
    log("CAFÉ CON HISTORIA — Pipeline de Video iniciado")
    log("=" * 50)

    verificar_infraestructura()
    notificar_inicio()

    # Agente V1 — Guión
    try:
        ejecutar_agente("Agente V1 — Guión", "agente_v1_guion")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente V1: {e}")
        notificar_infra(f"Agente V1 — Guión\n{str(e)}")
        sys.exit(1)
    except ErrorNegocio as e:
        log(f"AVISO en Agente V1: {e}")
        notificar_canal(CANAL_ERRORES, f"ℹ️ *Agente V1 — sin temas disponibles*\n{str(e)}")
        sys.exit(0)
    except Exception as e:
        log(f"ERROR en Agente V1: {e}")
        notificar_canal(CANAL_ERRORES, f"🚨 *Error en Agente V1 — Guión*\n```{traceback.format_exc()[:500]}```")
        sys.exit(1)

    # Agente V2 — Imágenes
    try:
        ejecutar_agente("Agente V2 — Imágenes", "agente_v2_imagenes")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente V2: {e}")
        notificar_infra(f"Agente V2 — Imágenes\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR en Agente V2: {e}")
        notificar_canal(CANAL_ERRORES, f"🚨 *Error en Agente V2 — Imágenes*\n```{traceback.format_exc()[:500]}```")
        sys.exit(1)

    # Agente V3 — Video (ffmpeg + TTS)
    try:
        ejecutar_agente("Agente V3 — Video", "agente_v3_video")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente V3: {e}")
        notificar_infra(f"Agente V3 — Video (ffmpeg/TTS)\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR en Agente V3: {e}")
        notificar_canal(CANAL_ERRORES, f"🚨 *Error en Agente V3 — Video*\n```{traceback.format_exc()[:500]}```")
        sys.exit(1)

    # Agente V4 — Publicador Reels
    try:
        ejecutar_agente("Agente V4 — Publicador Reels", "agente_v4_publica")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente V4: {e}")
        notificar_infra(f"Agente V4 — Publicador Reels\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR en Agente V4: {e}")
        notificar_canal(CANAL_ERRORES, f"🚨 *Error en Agente V4 — Publicador*\n```{traceback.format_exc()[:500]}```")
        sys.exit(1)

    log("Pipeline de Video completado exitosamente")
    notificar_exito()

if __name__ == "__main__":
    main()
