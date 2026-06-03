import os
import sys
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from slack_sdk import WebClient

sys.path.insert(0, "D:\\proyectos\\cafe-con-historia\\utils")
from errores import (
    ErrorInfraestructura,
    ErrorContenido,
    ErrorNegocio,
    notificar_error_contenido,
    notificar_error_negocio,
    notificar_canal
)

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv("D:\\proyectos\\cafe-con-historia\\.env")

SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
SLACK_TOKEN     = os.getenv("SLACK_TOKEN")
CANAL_CONTENIDO = os.getenv("SLACK_CHANNEL", "#contenido")
OLLAMA_URL      = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434") + "/api/generate"
MODELO          = "llama3.1"
MAX_INTENTOS    = 3
SCORE_MINIMO    = 7

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# ESTÁNDARES DE CALIDAD
# ============================================================

ESTANDARES = """
1. INTEGRIDAD — No contiene frases de rechazo como "Lo siento", "no puedo", "no es apropiado". No está vacío. Está en español.

2. ESTRUCTURA HISTÓRICA — Menciona al menos un período, fecha o época histórica concreta. Conecta explícitamente el pasado con el presente. No es opinión política disfrazada de historia.

3. ENGAGEMENT — Termina con una pregunta o reflexión que invite a comentar. Tiene un hook impactante en la primera línea. Tono conversacional, no académico ni aburrido.

4. CREDIBILIDAD — No contiene afirmaciones absolutas sin contexto. No promueve desinformación ni teorías conspirativas. Es equilibrado y presenta contexto sin tomar partido extremo.

5. PERSONALIDAD VISUAL — Incluye entre 3 y 7 emojis relevantes al tema. Los emojis refuerzan el mensaje y son coherentes con el tono.
"""

# ============================================================
# PASO 1 — Obtener contenido pendiente
# ============================================================

def obtener_contenido_pendiente():
    print("Buscando contenido pendiente de aprobación...")
    try:
        resultado = supabase.table("contenido")\
            .select("*, temas(pregunta, categoria)")\
            .eq("aprobado", False)\
            .order("fecha_generacion", desc=True)\
            .limit(1)\
            .execute()
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo conectar a Supabase: {e}")

    if not resultado.data:
        raise ErrorNegocio("No hay contenido pendiente de aprobación.")

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
Este es contenido educativo legítimo sobre historia y geografía mundial.

PREGUNTA DEL TEMA: {pregunta}

CONTENIDO A EVALUAR:
{contenido_texto}

ESTÁNDARES DE CALIDAD:
{ESTANDARES}

Evalúa el contenido contra cada estándar y responde ÚNICAMENTE con un objeto JSON:
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

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        texto = data.get("response", "").strip()

        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            return json.loads(texto[inicio:fin])
        raise ErrorContenido(f"Llama no respondió con JSON válido: {texto[:200]}")

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al evaluar contenido")
    except json.JSONDecodeError as e:
        raise ErrorContenido(f"Error parseando JSON de evaluación: {e}")
    except (ErrorInfraestructura, ErrorContenido):
        raise
    except Exception as e:
        raise ErrorContenido(f"Error evaluando contenido: {e}")

# ============================================================
# PASO 3 — Regenerar contenido si no aprueba
# ============================================================

def regenerar_contenido(pregunta, categoria, razon_rechazo, sugerencias):
    print(f"Regenerando contenido — Razón: {razon_rechazo}")

    prompt = f"""Eres un divulgador experto de historia y geografía del canal "Café con Historia".
Tu enfoque es: "La historia explica el presente".
Este es contenido educativo legítimo sobre historia y geografía mundial.

El contenido anterior fue rechazado por esta razón: {razon_rechazo}
Sugerencias para mejorar: {sugerencias}

Genera un nuevo contenido sobre esta pregunta que corrija los problemas mencionados:
PREGUNTA: {pregunta}
CATEGORÍA: {categoria}

Tu respuesta DEBE:
1. Empezar con un hook impactante que genere curiosidad
2. Explicar el contexto histórico con fechas o épocas específicas
3. Conectar explícitamente ese pasado con lo que vemos hoy
4. Usar tono conversacional — como explicarle a un amigo tomando un café
5. Tener entre 200 y 300 palabras
6. Terminar con una pregunta que invite a reflexionar
7. Incluir entre 3 y 7 emojis relevantes y coherentes con el tono del tema

Responde directamente con el contenido, sin introducción ni meta-comentarios."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        contenido = data.get("response", "").strip()

        if not contenido:
            raise ErrorContenido("Llama devolvió respuesta vacía al regenerar")

        print(f"Contenido regenerado: {len(contenido)} caracteres")
        return contenido

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al regenerar contenido")
    except (ErrorInfraestructura, ErrorContenido):
        raise
    except Exception as e:
        raise ErrorContenido(f"Error regenerando contenido: {e}")

# ============================================================
# PASO 4 — Guardar evaluación en Supabase
# ============================================================

def guardar_evaluacion(contenido_id, score, aprobado, contenido_nuevo=None, intentos=1):
    try:
        update = {
            "score_calidad": score,
            "aprobado": aprobado,
            "intentos_generacion": intentos
        }
        if contenido_nuevo:
            update["contenido_slack"] = contenido_nuevo

        supabase.table("contenido").update(update).eq("id", contenido_id).execute()
        print(f"✓ Evaluación guardada — Score: {score}/10 | Aprobado: {aprobado}")
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo guardar evaluación en Supabase: {e}")

# ============================================================
# PASO 5 — Notificar resultado
# ============================================================

def notificar_aprobado(pregunta, score, evaluacion):
    mensaje = f"""✅ *Contenido aprobado — listo para publicar*
*{pregunta}*

📊 *Score: {score}/10*
• Integridad: {evaluacion.get('integridad', 'N/A')}/10
• Estructura histórica: {evaluacion.get('estructura_historica', 'N/A')}/10
• Engagement: {evaluacion.get('engagement', 'N/A')}/10
• Credibilidad: {evaluacion.get('credibilidad', 'N/A')}/10
• Personalidad visual: {evaluacion.get('personalidad_visual', 'N/A')}/10

_El Agente 3 publicará este contenido en Facebook_"""

    notificar_canal(CANAL_CONTENIDO, mensaje)

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente 2 (Editor Crítico)")
    print("=" * 50)

    # Obtener contenido — puede lanzar ErrorNegocio o ErrorInfraestructura
    contenido = obtener_contenido_pendiente()

    pregunta     = contenido["temas"]["pregunta"]
    categoria    = contenido["temas"]["categoria"]
    contenido_id = contenido["id"]
    texto_actual = contenido["contenido_slack"]

    intento             = 1
    ultima_razon        = ""
    ultimas_sugerencias = ""

    while intento <= MAX_INTENTOS:
        print(f"\n--- Intento {intento}/{MAX_INTENTOS} ---")

        try:
            evaluacion = evaluar_contenido(pregunta, texto_actual)

            score    = evaluacion.get("score", 0)
            aprobado = evaluacion.get("aprobado", False) and score >= SCORE_MINIMO
            detalles = evaluacion.get("evaluacion", {})
            ultima_razon        = evaluacion.get("razon_rechazo", "")
            ultimas_sugerencias = evaluacion.get("sugerencias", "")

            print(f"Score: {score}/10 | Aprobado: {aprobado}")

            if aprobado:
                guardar_evaluacion(
                    contenido_id, score, True,
                    texto_actual if intento > 1 else None,
                    intento
                )
                notificar_aprobado(pregunta, score, detalles)
                print(f"\n✓ Contenido aprobado en intento {intento}")
                return

            print(f"Rechazado: {ultima_razon}")

            if intento < MAX_INTENTOS:
                texto_actual = regenerar_contenido(
                    pregunta, categoria, ultima_razon, ultimas_sugerencias
                )

        except ErrorInfraestructura:
            raise  # Relanzar para que main.py lo capture

        except ErrorContenido as e:
            print(f"Error de contenido en intento {intento}: {e}")
            ultima_razon = str(e)

        intento += 1

    # Agotó los intentos
    guardar_evaluacion(contenido_id, 0, False, intentos=MAX_INTENTOS)
    notificar_error_contenido("Agente 2 — Editor", pregunta, ultima_razon, MAX_INTENTOS)
    print(f"\n✗ Contenido rechazado después de {MAX_INTENTOS} intentos")

if __name__ == "__main__":
    correr_agente()