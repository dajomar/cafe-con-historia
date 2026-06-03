import os
import sys
import traceback
from datetime import datetime
from dotenv import load_dotenv
from slack_sdk import WebClient

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv("D:\\proyectos\\cafe-con-historia\\.env")

SLACK_TOKEN   = os.getenv("SLACK_TOKEN")
CANAL_CONTENIDO = os.getenv("SLACK_CHANNEL", "#contenido")
CANAL_INFRA     = os.getenv("SLACK_CANAL_INFRA", "#infraestructura")

slack = WebClient(token=SLACK_TOKEN)

sys.path.insert(0, "D:\\proyectos\\cafe-con-historia\\utils")
sys.path.insert(0, "D:\\proyectos\\cafe-con-historia\\agents")

from errores import (
    ErrorInfraestructura,
    verificar_ollama,
    verificar_token_facebook,
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
    with open("D:\\proyectos\\cafe-con-historia\\pipeline.log", "a", encoding="utf-8") as f:
        f.write(linea + "\n")

# ============================================================
# NOTIFICACIONES
# ============================================================

def notificar_inicio():
    notificar_canal(
        CANAL_CONTENIDO,
        f"☕ *Café con Historia* — Pipeline iniciado\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    )

def notificar_exito():
    notificar_canal(
        CANAL_CONTENIDO,
        f"✅ *Pipeline completado exitosamente*\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    )

# ============================================================
# VERIFICACIONES PREVIAS
# ============================================================

def verificar_infraestructura():
    log("Verificando infraestructura...")

    # 1. Verificar Ollama
    try:
        verificar_ollama()
        log("✓ Ollama corriendo")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA — Ollama: {e}")
        notificar_infra(str(e))
        sys.exit(1)

    # 2. Verificar token de Facebook
    try:
        verificar_token_facebook()
        log("✓ Token de Facebook verificado")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA — Facebook token: {e}")
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
    log("CAFÉ CON HISTORIA — Pipeline iniciado")
    log("=" * 50)

    # Verificar infraestructura ANTES de todo
    verificar_infraestructura()

    notificar_inicio()

    # Agente 1 — Investigador
    try:
        ejecutar_agente("Agente 1 — Investigador", "agente_1_investigador")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente 1: {e}")
        notificar_infra(f"Agente 1 — Investigador\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR en Agente 1: {e}")
        notificar_canal(
            os.getenv("SLACK_CANAL_ERRORES", "#errores"),
            f"🚨 *Error en Agente 1*\n```{traceback.format_exc()[:500]}```"
        )
        sys.exit(1)

    # Agente 2 — Editor crítico
    try:
        ejecutar_agente("Agente 2 — Editor", "agente_2_editor")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente 2: {e}")
        notificar_infra(f"Agente 2 — Editor\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR en Agente 2: {e}")
        notificar_canal(
            os.getenv("SLACK_CANAL_ERRORES", "#errores"),
            f"🚨 *Error en Agente 2*\n```{traceback.format_exc()[:500]}```"
        )
        sys.exit(1)

    # Agente 3 — Publicador
    try:
        ejecutar_agente("Agente 3 — Publicador", "agente_3_publicador")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente 3: {e}")
        notificar_infra(f"Agente 3 — Publicador\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR en Agente 3: {e}")
        notificar_canal(
            os.getenv("SLACK_CANAL_ERRORES", "#errores"),
            f"🚨 *Error en Agente 3*\n```{traceback.format_exc()[:500]}```"
        )
        sys.exit(1)

    log("Pipeline completado exitosamente")
    notificar_exito()

if __name__ == "__main__":
    main()