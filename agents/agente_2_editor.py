import os
import sys
import json
import requests
import pathlib
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from slack_sdk import WebClient


BASE_DIR = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "utils"))

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

load_dotenv(BASE_DIR / ".env")

SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
SLACK_TOKEN     = os.getenv("SLACK_TOKEN")
CANAL_CONTENIDO = os.getenv("SLACK_CHANNEL", "#contenido")
CANAL_ERRORES   = os.getenv("SLACK_CANAL_ERRORES", "#errores")
OLLAMA_URL      = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434") + "/api/generate"
MODELO          = "llama3.1"
MAX_INTENTOS    = 3
SCORE_MINIMO    = 7

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# ESTÁNDARES DE CALIDAD EDITORIAL
# ============================================================

ESTANDARES_EDITORIAL = """
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
            .select("*, temas(pregunta, categoria, tono, region, epoca)")\
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
# PASO 2 — VERIFICACIÓN FACTUAL (historiador escéptico)
# ============================================================

def verificar_hechos(pregunta, contenido_texto):
    print("Verificando hechos como historiador escéptico...")

    prompt = f"""Eres un verificador de hechos para el canal educativo "Café con Historia".
Este es contenido de divulgación histórica — NO es una tesis académica.
Las simplificaciones narrativas y los matices históricos SON ACEPTABLES y no deben marcarse como errores.

TEMA: {pregunta}

CONTENIDO A VERIFICAR:
{contenido_texto}

Busca ÚNICAMENTE errores graves y verificables:
1. Fechas completamente incorrectas — ejemplo: decir que algo ocurrió en 1800 cuando fue en 1950
2. Nombres completamente equivocados — ejemplo: atribuir un evento a la persona incorrecta
3. Eventos que nunca ocurrieron — afirmaciones inventadas sin base histórica
4. Afirmaciones que contradicen hechos universalmente aceptados y documentados

NO marques como error:
- Simplificaciones narrativas propias de la divulgación popular
- Matices históricos que podrían debatirse académicamente
- Omisión de detalles secundarios
- Diferentes interpretaciones válidas de un mismo evento

Responde ÚNICAMENTE con un JSON:
{{
  "tiene_errores": <true o false>,
  "nivel_confianza": <"alto" | "medio" | "bajo">,
  "errores_detectados": [
    {{
      "fragmento": "<texto exacto con error grave>",
      "problema": "<descripción del error grave y verificable>",
      "sugerencia": "<corrección específica>"
    }}
  ],
  "veredicto": "<aprobado | revision_manual | rechazado>",
  "razon": "<explicación breve>"
}}

Valores de veredicto:
- aprobado: sin errores graves, contenido válido para divulgación
- revision_manual: hay al menos un error grave y verificable que requiere corrección
- rechazado: el contenido tiene múltiples errores graves que lo hacen inpublicable

Si no detectas errores graves, devuelve tiene_errores=false, errores_detectados=[] y veredicto=aprobado.
Responde SOLO con el JSON."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        texto = data.get("response", "").strip()

        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            return json.loads(texto[inicio:fin])
        raise ErrorContenido(f"Llama no respondió con JSON válido en verificación factual")

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde en verificación factual")
    except json.JSONDecodeError as e:
        raise ErrorContenido(f"Error parseando JSON de verificación: {e}")
    except (ErrorInfraestructura, ErrorContenido):
        raise
    except Exception as e:
        raise ErrorContenido(f"Error en verificación factual: {e}")

def notificar_revision_manual(pregunta, contenido, verificacion):
    """Notifica en #errores para revisión manual con los problemas específicos"""
    errores = verificacion.get("errores_detectados", [])
    lista_errores = ""
    for e in errores:
        lista_errores += f"\n• *Fragmento:* _{e.get('fragmento', '')}_\n  *Problema:* {e.get('problema', '')}\n  *Sugerencia:* {e.get('sugerencia', '')}\n"

    mensaje = f"""🔍 *Revisión manual requerida — Verificación factual*
*Tema:* {pregunta}
*Nivel de confianza:* {verificacion.get('nivel_confianza', 'desconocido')}
*Razón:* {verificacion.get('razon', '')}

*Posibles errores detectados:*
{lista_errores}

*Contenido completo:*
{contenido[:800]}...

_Revisa y decide si publicar manualmente._"""

    notificar_canal(CANAL_ERRORES, mensaje)

# ============================================================
# PASO 3 — Evaluación editorial
# ============================================================

def evaluar_contenido(pregunta, contenido_texto):
    print("Evaluando calidad editorial con Llama...")

    prompt = f"""Eres un editor crítico y exigente del canal educativo "Café con Historia".
Tu trabajo es evaluar si el siguiente contenido cumple los estándares de calidad del canal.
Este es contenido educativo legítimo sobre historia y geografía mundial.

PREGUNTA DEL TEMA: {pregunta}

CONTENIDO A EVALUAR:
{contenido_texto}

ESTÁNDARES DE CALIDAD:
{ESTANDARES_EDITORIAL}

Evalúa el contenido contra cada estándar y responde ÚNICAMENTE con un JSON:
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

Score mínimo para aprobar: {SCORE_MINIMO}/10.
Responde SOLO con el JSON."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        texto = data.get("response", "").strip()

        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            return json.loads(texto[inicio:fin])
        raise ErrorContenido(f"Llama no respondió con JSON válido en evaluación editorial")

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde en evaluación editorial")
    except json.JSONDecodeError as e:
        raise ErrorContenido(f"Error parseando JSON editorial: {e}")
    except (ErrorInfraestructura, ErrorContenido):
        raise
    except Exception as e:
        raise ErrorContenido(f"Error en evaluación editorial: {e}")

# ============================================================
# PASO 4 — Regenerar contenido
# ============================================================

def regenerar_contenido(pregunta, categoria, tono, region, epoca, razon_rechazo, sugerencias):
    print(f"Regenerando contenido — Razón: {razon_rechazo}")

    contexto_tono = {
        "pesado":     "El tono debe ser serio y reflexivo.",
        "curioso":    "El tono debe ser sorprendente y entretenido.",
        "reflexivo":  "El tono debe invitar a la reflexión profunda.",
        "inspirador": "El tono debe ser positivo y motivador."
    }.get(tono, "")

    prompt = f"""Eres un divulgador experto de historia y geografía del canal "Café con Historia".
Tu enfoque es: "La historia explica el presente".
Este es contenido educativo legítimo sobre historia y geografía mundial.

El contenido anterior fue rechazado por: {razon_rechazo}
Sugerencias para mejorar: {sugerencias}

Genera un nuevo contenido corrigiendo los problemas mencionados:
PREGUNTA: {pregunta}
CATEGORÍA: {categoria}
REGIÓN: {region}
ÉPOCA: {epoca}
TONO: {contexto_tono}

Tu respuesta DEBE:
1. Empezar con un hook impactante
2. Incluir fechas o épocas históricas concretas y verificables
3. Conectar el pasado con el presente explícitamente
4. Tono conversacional, entre 400 y 600 palabras
5. Terminar con una pregunta reflexiva
6. Incluir entre 3 y 7 emojis coherentes con el tono

Responde directamente, sin meta-comentarios."""

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
        raise ErrorInfraestructura("Ollama no responde al regenerar")
    except (ErrorInfraestructura, ErrorContenido):
        raise
    except Exception as e:
        raise ErrorContenido(f"Error regenerando: {e}")

# ============================================================
# PASO 5 — Guardar evaluación
# ============================================================

def guardar_evaluacion(contenido_id, score, aprobado, contenido_nuevo=None, intentos=1):
    try:
        update = {
            "score_calidad":       score,
            "aprobado":            aprobado,
            "intentos_generacion": intentos
        }
        if contenido_nuevo:
            update["contenido_slack"] = contenido_nuevo

        supabase.table("contenido").update(update).eq("id", contenido_id).execute()
        print(f"✓ Evaluación guardada — Score: {score}/10 | Aprobado: {aprobado}")
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo guardar evaluación en Supabase: {e}")

# ============================================================
# PASO 6 — Notificar aprobación
# ============================================================

def notificar_aprobado(pregunta, score, evaluacion, verificacion):
    nivel_confianza = verificacion.get("nivel_confianza", "alto")
    icono_confianza = {"alto": "🟢", "medio": "🟡", "bajo": "🔴"}.get(nivel_confianza, "⚪")

    mensaje = f"""✅ *Contenido aprobado — listo para publicar*
*{pregunta}*

📊 *Score editorial: {score}/10*
• Integridad: {evaluacion.get('integridad', 'N/A')}/10
• Estructura histórica: {evaluacion.get('estructura_historica', 'N/A')}/10
• Engagement: {evaluacion.get('engagement', 'N/A')}/10
• Credibilidad: {evaluacion.get('credibilidad', 'N/A')}/10
• Personalidad visual: {evaluacion.get('personalidad_visual', 'N/A')}/10

{icono_confianza} *Verificación factual: {nivel_confianza}*

_El Agente 3 publicará este contenido en Facebook_"""

    notificar_canal(CANAL_CONTENIDO, mensaje)

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente 2 (Editor Crítico)")
    print("=" * 50)

    contenido = obtener_contenido_pendiente()

    pregunta     = contenido["temas"]["pregunta"]
    categoria    = contenido["temas"]["categoria"]
    tono         = contenido["temas"].get("tono", "reflexivo")
    region       = contenido["temas"].get("region", "global")
    epoca        = contenido["temas"].get("epoca", "contemporanea")
    contenido_id = contenido["id"]
    texto_actual = contenido["contenido_slack"]

    # ── VERIFICACIÓN FACTUAL (una sola vez, antes de evaluar) ──
    print("\n[Verificación factual]")
    try:
        verificacion = verificar_hechos(pregunta, texto_actual)
        veredicto    = verificacion.get("veredicto", "aprobado")
        nivel        = verificacion.get("nivel_confianza", "alto")

        print(f"Veredicto factual: {veredicto} | Confianza: {nivel}")

        if veredicto == "rechazado":
            # Error grave — no publicar, notificar para revisión manual
            notificar_revision_manual(pregunta, texto_actual, verificacion)
            guardar_evaluacion(contenido_id, 0, False, intentos=1)
            print("\n✗ Contenido rechazado por errores factuales graves — revisión manual requerida")
            return

        if veredicto == "revision_manual":
            # Dudas menores — notificar pero continuar con evaluación editorial
            notificar_revision_manual(pregunta, texto_actual, verificacion)
            print("⚠ Dudas factuales menores notificadas — continuando con evaluación editorial")

    except ErrorInfraestructura:
        raise
    except ErrorContenido as e:
        # Si falla la verificación factual, continuar con advertencia
        print(f"⚠ No se pudo verificar hechos: {e} — continuando sin verificación")
        verificacion = {"nivel_confianza": "desconocido", "veredicto": "aprobado"}

    # ── EVALUACIÓN EDITORIAL ──
    intento             = 1
    ultima_razon        = ""
    ultimas_sugerencias = ""

    while intento <= MAX_INTENTOS:
        print(f"\n--- Intento editorial {intento}/{MAX_INTENTOS} ---")

        try:
            evaluacion = evaluar_contenido(pregunta, texto_actual)

            score    = evaluacion.get("score", 0)
            aprobado = evaluacion.get("aprobado", False) and score >= SCORE_MINIMO
            detalles = evaluacion.get("evaluacion", {})
            ultima_razon        = evaluacion.get("razon_rechazo", "")
            ultimas_sugerencias = evaluacion.get("sugerencias", "")

            print(f"Score editorial: {score}/10 | Aprobado: {aprobado}")

            if aprobado:
                guardar_evaluacion(
                    contenido_id, score, True,
                    texto_actual if intento > 1 else None,
                    intento
                )
                notificar_aprobado(pregunta, score, detalles, verificacion)
                print(f"\n✓ Contenido aprobado en intento {intento}")
                return

            print(f"Rechazado editorialmente: {ultima_razon}")

            if intento < MAX_INTENTOS:
                texto_actual = regenerar_contenido(
                    pregunta, categoria, tono, region, epoca,
                    ultima_razon, ultimas_sugerencias
                )

        except ErrorInfraestructura:
            raise

        except ErrorContenido as e:
            print(f"Error de contenido en intento {intento}: {e}")
            ultima_razon = str(e)

        intento += 1

    guardar_evaluacion(contenido_id, 0, False, intentos=MAX_INTENTOS)
    notificar_error_contenido("Agente 2 — Editor", pregunta, ultima_razon, MAX_INTENTOS)
    print(f"\n✗ Contenido rechazado después de {MAX_INTENTOS} intentos")

if __name__ == "__main__":
    correr_agente()