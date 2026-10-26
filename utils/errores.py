import os
import requests
from datetime import datetime, date
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

SLACK_TOKEN       = os.getenv("SLACK_TOKEN")
CANAL_CONTENIDO   = os.getenv("SLACK_CHANNEL", "#contenido")
CANAL_ERRORES     = os.getenv("SLACK_CANAL_ERRORES", "#errores")
CANAL_INFRA       = os.getenv("SLACK_CANAL_INFRA", "#infraestructura")
OLLAMA_ENDPOINT   = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
FB_TOKEN_EXPIRA   = os.getenv("FB_TOKEN_EXPIRA", "")
FB_TOKEN_AVISO    = int(os.getenv("FB_TOKEN_AVISO_DIAS", "5"))

slack = WebClient(token=SLACK_TOKEN)

# ============================================================
# TIPOS DE ERROR
# ============================================================

class ErrorInfraestructura(Exception):
    """Error crítico del sistema — detiene el pipeline completo"""
    pass

class ErrorContenido(Exception):
    """Error de contenido — se reintenta hasta MAX_INTENTOS"""
    pass

class ErrorNegocio(Exception):
    """Error de negocio — notifica pero no detiene"""
    pass

# ============================================================
# VERIFICACIONES DE INFRAESTRUCTURA
# ============================================================

def verificar_ollama():
    """Verifica que Ollama esté corriendo antes de continuar"""
    try:
        r = requests.get(f"{OLLAMA_ENDPOINT}/api/tags", timeout=5)
        if r.status_code == 200:
            return True
        raise ErrorInfraestructura(f"Ollama responde pero con error: {r.status_code}")
    except requests.ConnectionError:
        raise ErrorInfraestructura(
            f"Ollama no está corriendo en {OLLAMA_ENDPOINT}. "
            "Inicia Ollama antes de correr el pipeline."
        )
    except requests.Timeout:
        raise ErrorInfraestructura("Ollama no responde — timeout de conexión")

def verificar_token_facebook():
    """Verifica si el token de Facebook está próximo a expirar"""
    if not FB_TOKEN_EXPIRA:
        return

    try:
        fecha_expira = datetime.strptime(FB_TOKEN_EXPIRA, "%Y-%m-%d").date()
        hoy = date.today()
        dias_restantes = (fecha_expira - hoy).days

        if dias_restantes <= 0:
            raise ErrorInfraestructura(
                f"El token de Facebook expiró el {FB_TOKEN_EXPIRA}. "
                "Renueva el token en developers.facebook.com"
            )

        if dias_restantes <= FB_TOKEN_AVISO:
            notificar_infra(
                f"⚠️ *Token de Facebook próximo a expirar*\n"
                f"Expira en *{dias_restantes} días* ({FB_TOKEN_EXPIRA})\n"
                f"Renueva el token en developers.facebook.com"
            )
    except ValueError:
        pass  # Formato de fecha inválido — ignorar

def verificar_error_facebook(respuesta_error):
    """Detecta si un error de Facebook es de infraestructura o de contenido"""
    codigo = respuesta_error.get("code", 0)
    mensaje = respuesta_error.get("message", "")

    # Errores de token — infraestructura
    if codigo == 190 or "access token" in mensaje.lower() or "session has expired" in mensaje.lower():
        raise ErrorInfraestructura(
            f"Token de Facebook inválido o expirado.\n"
            f"Mensaje: {mensaje}\n"
            f"Acción: Renueva el token en developers.facebook.com y actualiza FB_PAGE_TOKEN en .env"
        )

    # Errores de permisos — infraestructura
    if codigo in [200, 283]:
        raise ErrorInfraestructura(
            f"Permisos insuficientes en Facebook.\n"
            f"Mensaje: {mensaje}\n"
            f"Acción: Revisa los permisos de la app en developers.facebook.com"
        )

    # Otros errores — contenido
    raise ErrorContenido(f"Error de Facebook: {mensaje}")

# ============================================================
# NOTIFICACIONES
# ============================================================

def notificar_infra(mensaje):
    """Notifica en #infraestructura — errores críticos del sistema"""
    try:
        slack.chat_postMessage(
            channel=CANAL_INFRA,
            text=f"🔴 *INFRAESTRUCTURA*\n{mensaje}\n\n_Pipeline detenido: {datetime.now().strftime('%d/%m/%Y %H:%M')}_",
            mrkdwn=True
        )
    except SlackApiError as e:
        print(f"No se pudo notificar en {CANAL_INFRA}: {e}")

def notificar_error_contenido(agente, pregunta, razon, intentos):
    """Notifica en #errores — problemas de contenido"""
    try:
        slack.chat_postMessage(
            channel=CANAL_ERRORES,
            text=f"⚠️ *Error de contenido — {agente}*\n"
                 f"*Tema:* {pregunta}\n"
                 f"*Razón:* {razon}\n"
                 f"*Intentos:* {intentos}\n"
                 f"_El contenido NO fue publicado._",
            mrkdwn=True
        )
    except SlackApiError as e:
        print(f"No se pudo notificar en {CANAL_ERRORES}: {e}")

def notificar_error_negocio(mensaje):
    """Notifica en #errores — problemas de negocio"""
    try:
        slack.chat_postMessage(
            channel=CANAL_ERRORES,
            text=f"ℹ️ *Aviso de negocio*\n{mensaje}\n_Pipeline continuó normalmente._",
            mrkdwn=True
        )
    except SlackApiError as e:
        print(f"No se pudo notificar en {CANAL_ERRORES}: {e}")

def notificar_canal(canal, mensaje):
    """Notifica en cualquier canal"""
    try:
        slack.chat_postMessage(channel=canal, text=mensaje, mrkdwn=True)
    except SlackApiError as e:
        print(f"No se pudo notificar en {canal}: {e}")