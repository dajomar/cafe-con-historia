import os
import json
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

SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY")
SLACK_TOKEN   = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#contenido")
SLACK_ERRORES = "#errores"
OLLAMA_URL    = "http://localhost:11434/api/generate"
MODELO        = "llama3.1"

MAX_INTENTOS  = 3
SCORE_MINIMO  = 7

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# ESTÁNDARES DE CALIDAD
# ============================================================

ESTANDARES = """
1. INTEGRIDAD — No contiene frases de rechazo como "Lo siento", "no puedo", "no es apropiado", "contenido falso". No está vacío. Está en español.

2. ESTRUCTURA HISTÓRICA — Menciona al menos un período, fecha o época histórica concreta. Conecta explícitamente el pasado con el presente. No es opinión política disfrazada de historia.

3. ENGAGEMENT — Termina con una pregunta o reflexión que invite a comentar. Tiene un hook impactante en la primera línea. Tono conversacional, no académico ni aburrido.

4. CREDIBILIDAD — No contiene afirmaciones absolutas sin contexto. No promueve desinformación ni teorías conspirativas. Es equilibrado y presenta contexto sin tomar partido extremo.

5. PERSONALIDAD VISUAL — Incluye entre 3 y 7 emojis relevantes al tema. Los emojis refuerzan el mensaje y son coherentes con el tono (no emojis alegres en temas de guerra o tragedia).
"""

# ============================================================
# PASO 1 — Obtener último contenido no aprobado
# ============================================================

def obtener_contenido_pendiente():
    print("Buscando contenido pendiente de aprobación...")
    resultado = supabase.table("contenido")\
        .select("*, temas(pregunta, categoria)")\
        .eq("aprobado", False)\
        .order("fecha_generacion", desc=True)\
        .limit(1)\
        .execute()

    if not resultado.data:
        print("No hay contenido pendiente de aprobación.")
        return None

    contenido = resultado.data[0]
    print(f"Contenido encontrado: {contenido['temas']['pregunta']}")
    return contenido

# ============================================================
# PASO 2 — Evaluar contenido con Llama
# ============================================================

def evaluar_contenido(pregunta, contenido_texto):
    print("Evaluando contenido con Llama...")

    prompt = f"""Eres un editor crítico y exigente del canal educativo "Café con Historia".
Tu trabajo es evaluar si el siguiente contenido cumple los estándares de calidad del canal.

PREGUNTA DEL TEMA: {pregunta}

CONTENIDO A EVALUAR:
{contenido_texto}

ESTÁNDARES DE CALIDAD:
{ESTANDARES}

Evalúa el contenido contra cada estándar y responde ÚNICAMENTE con un objeto JSON con este formato exacto:
{{
  "score": <número del 1 al 10>,
  "aprobado": <true o false>,
  "evaluacion": {{
    "integridad": <número del 1 al 10>,
    "estructura_historica": <número del 1 al 10>,
    "engagement": <número del 1 al 10>,
    "credibilidad": <número del 1 al 10>,
    "personalidad_visual": <número del 1 al 10>
  }},
  "razon_rechazo": "<explicación si no aprueba, vacío si aprueba>",
  "sugerencias": "<qué mejorar si no aprueba>"
}}

El score mínimo para aprobar es {SCORE_MINIMO}/10.
Responde SOLO con el JSON, sin texto adicional."""

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False
    }

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        texto = data.get("response", "").strip()

        # Limpiar posibles caracteres extra
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            texto_json = texto[inicio:fin]
            evaluacion = json.loads(texto_json)
            return evaluacion
        else:
            print(f"Error: Llama no respondió con JSON válido: {texto[:200]}")
            return None

    except json.JSONDecodeError as e:
        print(f"Error parseando JSON de evaluación: {e}")
        return None
    except Exception as e:
        print(f"Error evaluando contenido: {e}")
        return None

# ============================================================
# PASO 3 — Regenerar contenido si no aprueba
# ============================================================

def regenerar_contenido(pregunta, categoria, razon_rechazo, sugerencias):
    print(f"Regenerando contenido — Razón: {razon_rechazo}")

    prompt = f"""Eres un divulgador experto de historia y geografía del canal "Café con Historia".
Tu enfoque es: "La historia explica el presente".

El contenido anterior fue rechazado por esta razón: {razon_rechazo}

Sugerencias para mejorar: {sugerencias}

Genera un nuevo contenido sobre esta pregunta que corrija los problemas mencionados:
PREGUNTA: {pregunta}
CATEGORÍA: {categoria}

Tu respuesta debe:
1. Empezar con un hook impactante que genere curiosidad
2. Explicar el contexto histórico concreto con fechas o épocas específicas
3. Conectar explícitamente ese pasado con lo que vemos hoy
4. Usar tono conversacional — como explicarle a un amigo tomando un café
5. Tener entre 200 y 300 palabras
6. Terminar con una pregunta que invite a reflexionar
7. Incluir entre 3 y 7 emojis relevantes y coherentes con el tono del tema

Responde directamente con el contenido, sin introducción ni meta-comentarios."""

    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False
    }

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        contenido = data.get("response", "").strip()
        print(f"Contenido regenerado: {len(contenido)} caracteres")
        return contenido
    except Exception as e:
        print(f"Error regenerando: {e}")
        return None

# ============================================================
# PASO 4 — Guardar resultado en Supabase
# ============================================================

def guardar_evaluacion(contenido_id, score, aprobado, contenido_nuevo=None, intentos=1):
    update = {
        "score_calidad": score,
        "aprobado": aprobado,
        "intentos_generacion": intentos
    }
    if contenido_nuevo:
        update["contenido_slack"] = contenido_nuevo

    supabase.table("contenido").update(update).eq("id", contenido_id).execute()
    print(f"✓ Evaluación guardada — Score: {score}/10 | Aprobado: {aprobado}")

# ============================================================
# PASO 5 — Notificar resultado a Slack
# ============================================================

def notificar_aprobado(pregunta, score, evaluacion):
    mensaje = f"""✅ *Contenido aprobado — listo para publicar*
*{pregunta}*

📊 *Score: {score}/10*
• Integridad: {evaluacion['integridad']}/10
• Estructura histórica: {evaluacion['estructura_historica']}/10
• Engagement: {evaluacion['engagement']}/10
• Credibilidad: {evaluacion['credibilidad']}/10
• Personalidad visual: {evaluacion['personalidad_visual']}/10

_El Agente 3 publicará este contenido en Facebook_"""

    slack.chat_postMessage(channel=SLACK_CHANNEL, text=mensaje, mrkdwn=True)

def notificar_rechazado(pregunta, intentos, razon):
    mensaje = f"""🚨 *Contenido rechazado después de {intentos} intentos*
*{pregunta}*

Razón: {razon}

_El contenido NO será publicado. Revisa manualmente si es necesario._"""

    slack.chat_postMessage(channel=SLACK_ERRORES, text=mensaje, mrkdwn=True)

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente 2 (Editor Crítico)")
    print("=" * 50)

    # Obtener contenido pendiente
    contenido = obtener_contenido_pendiente()
    if not contenido:
        print("No hay contenido que evaluar.")
        return

    pregunta       = contenido["temas"]["pregunta"]
    categoria      = contenido["temas"]["categoria"]
    contenido_id   = contenido["id"]
    texto_actual   = contenido["contenido_slack"]

    intento = 1
    ultima_razon = ""
    ultimas_sugerencias = ""

    while intento <= MAX_INTENTOS:
        print(f"\n--- Intento {intento}/{MAX_INTENTOS} ---")

        # Evaluar contenido
        evaluacion = evaluar_contenido(pregunta, texto_actual)

        if not evaluacion:
            print("Error en la evaluación — reintentando...")
            intento += 1
            continue

        score    = evaluacion.get("score", 0)
        aprobado = evaluacion.get("aprobado", False) and score >= SCORE_MINIMO
        detalles = evaluacion.get("evaluacion", {})
        ultima_razon = evaluacion.get("razon_rechazo", "")
        ultimas_sugerencias = evaluacion.get("sugerencias", "")

        print(f"Score obtenido: {score}/10 | Aprobado: {aprobado}")
        print(f"Detalles: {detalles}")

        if aprobado:
            guardar_evaluacion(contenido_id, score, True,
                             texto_actual if intento > 1 else None, intento)
            notificar_aprobado(pregunta, score, detalles)
            print(f"\n✓ Contenido aprobado en intento {intento}")
            return

        # No aprobado — regenerar si hay intentos disponibles
        print(f"Rechazado: {ultima_razon}")

        if intento < MAX_INTENTOS:
            texto_actual = regenerar_contenido(
                pregunta, categoria, ultima_razon, ultimas_sugerencias
            )
            if not texto_actual:
                print("Error regenerando — abortando")
                break

        intento += 1

    # Agotó los intentos
    guardar_evaluacion(contenido_id, 0, False, intentos=MAX_INTENTOS)
    notificar_rechazado(pregunta, MAX_INTENTOS, ultima_razon)
    print(f"\n✗ Contenido rechazado después de {MAX_INTENTOS} intentos")

if __name__ == "__main__":
    correr_agente()