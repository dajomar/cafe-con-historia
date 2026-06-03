import os
import sys
import traceback
from datetime import datetime
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv("D:\\proyectos\\cafe-con-historia\\.env")

SLACK_TOKEN   = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#contenido")
SLACK_ERRORES = "#errores"

slack = WebClient(token=SLACK_TOKEN)

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
    try:
        slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"☕ *Café con Historia* — Pipeline iniciado\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_",
            mrkdwn=True
        )
    except Exception as e:
        log(f"Aviso: No se pudo notificar inicio: {e}")

def notificar_exito():
    try:
        slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"✅ *Pipeline completado exitosamente*\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_",
            mrkdwn=True
        )
    except Exception as e:
        log(f"Aviso: No se pudo notificar éxito: {e}")

def notificar_error(agente, error):
    mensaje = f"""🚨 *Error crítico en el pipeline — {agente}*

```{error[:500]}```

_Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}_
_Pipeline detenido. Revisión manual requerida._"""
    try:
        slack.chat_postMessage(
            channel=SLACK_ERRORES,
            text=mensaje,
            mrkdwn=True
        )
    except Exception as e:
        log(f"No se pudo enviar error a Slack: {e}")

# ============================================================
# EJECUTAR AGENTES
# ============================================================

AGENTS_PATH = "D:\\proyectos\\cafe-con-historia\\agents"

def ejecutar_agente_1():
    log("Iniciando Agente 1 — Investigador...")
    sys.path.insert(0, AGENTS_PATH)
    import importlib
    agente = importlib.import_module("agente_1_investigador")
    importlib.reload(agente)
    agente.correr_agente()
    log("✓ Agente 1 completado")

def ejecutar_agente_2():
    log("Iniciando Agente 2 — Editor crítico...")
    sys.path.insert(0, AGENTS_PATH)
    import importlib
    agente = importlib.import_module("agente_2_editor")
    importlib.reload(agente)
    agente.correr_agente()
    log("✓ Agente 2 completado")

def ejecutar_agente_3():
    log("Iniciando Agente 3 — Publicador...")
    sys.path.insert(0, AGENTS_PATH)
    import importlib
    agente = importlib.import_module("agente_3_publicador")
    importlib.reload(agente)
    agente.correr_agente()
    log("✓ Agente 3 completado")

# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def main():
    log("=" * 50)
    log("CAFÉ CON HISTORIA — Pipeline iniciado")
    log("=" * 50)

    notificar_inicio()

    # Agente 1 — Investigador
    try:
        ejecutar_agente_1()
    except Exception as e:
        error = traceback.format_exc()
        log(f"ERROR en Agente 1: {e}")
        notificar_error("Agente 1 — Investigador", error)
        log("Pipeline detenido")
        sys.exit(1)

    # Agente 2 — Editor crítico
    try:
        ejecutar_agente_2()
    except Exception as e:
        error = traceback.format_exc()
        log(f"ERROR en Agente 2: {e}")
        notificar_error("Agente 2 — Editor", error)
        log("Pipeline detenido")
        sys.exit(1)

    # Agente 3 — Publicador
    try:
        ejecutar_agente_3()
    except Exception as e:
        error = traceback.format_exc()
        log(f"ERROR en Agente 3: {e}")
        notificar_error("Agente 3 — Publicador", error)
        log("Pipeline detenido")
        sys.exit(1)

    log("Pipeline completado exitosamente")
    notificar_exito()

if __name__ == "__main__":
    main()