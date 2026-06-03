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
# NOTIFICACIONES
# ============================================================

def notificar_inicio():
    slack.chat_postMessage(
        channel=SLACK_CHANNEL,
        text=f"☕ *Café con Historia* — Pipeline iniciado\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_",
        mrkdwn=True
    )

def notificar_exito():
    slack.chat_postMessage(
        channel=SLACK_CHANNEL,
        text=f"✅ *Pipeline completado exitosamente*\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_",
        mrkdwn=True
    )

def notificar_error(agente, error):
    mensaje = f"""🚨 *Error en el pipeline — {agente}*

```{error}```

_Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}_
_Revisa los logs para más detalles_"""

    try:
        slack.chat_postMessage(
            channel=SLACK_ERRORES,
            text=mensaje,
            mrkdwn=True
        )
    except SlackApiError:
        print(f"No se pudo enviar error a Slack: {error}")

# ============================================================
# LOGGING
# ============================================================

def log(mensaje):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{timestamp}] {mensaje}"
    print(linea)

    # Guarda también en archivo de log
    with open("D:\\proyectos\\cafe-con-historia\\pipeline.log", "a", encoding="utf-8") as f:
        f.write(linea + "\n")

# ============================================================
# EJECUTAR AGENTES
# ============================================================

def ejecutar_agente_1():
    log("Iniciando Agente 1 — Slack...")
    sys.path.insert(0, "D:\\proyectos\\cafe-con-historia\\agents")
    from agente_1_slack import correr_agente
    correr_agente()
    log("Agente 1 completado")

def ejecutar_agente_2():
    log("Iniciando Agente 2 — Facebook...")
    sys.path.insert(0, "D:\\proyectos\\cafe-con-historia\\agents")
    from agente_2_facebook import correr_agente
    correr_agente()
    log("Agente 2 completado")

# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def main():
    log("=" * 50)
    log("CAFÉ CON HISTORIA — Pipeline iniciado")
    log("=" * 50)

    try:
        notificar_inicio()
    except Exception as e:
        log(f"Aviso: No se pudo notificar inicio en Slack: {e}")

    # Agente 1
    try:
        ejecutar_agente_1()
    except Exception as e:
        error = traceback.format_exc()
        log(f"ERROR en Agente 1: {e}")
        notificar_error("Agente 1 — Slack", error)
        log("Pipeline detenido por error en Agente 1")
        sys.exit(1)

    # Agente 2
    try:
        ejecutar_agente_2()
    except Exception as e:
        error = traceback.format_exc()
        log(f"ERROR en Agente 2: {e}")
        notificar_error("Agente 2 — Facebook", error)
        log("Pipeline detenido por error en Agente 2")
        sys.exit(1)

    # Éxito
    log("Pipeline completado exitosamente")
    try:
        notificar_exito()
    except Exception as e:
        log(f"Aviso: No se pudo notificar éxito en Slack: {e}")

if __name__ == "__main__":
    main()