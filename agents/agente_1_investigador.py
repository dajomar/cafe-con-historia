import os
import sys
import random
import requests
from datetime import datetime, timedelta
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
VENTANA_DIAS    = 7

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
slack    = WebClient(token=SLACK_TOKEN)

# ============================================================
# PASO 1 — Obtener historial de los últimos 7 días
# ============================================================

def obtener_historial():
    """Retorna los temas publicados en los últimos VENTANA_DIAS días"""
    fecha_limite = (datetime.now() - timedelta(days=VENTANA_DIAS)).isoformat()
    try:
        resultado = supabase.table("temas")\
            .select("tono, region, epoca")\
            .eq("publicado", True)\
            .gte("fecha_publicacion", fecha_limite)\
            .execute()
        return resultado.data
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo obtener historial de Supabase: {e}")

def calcular_dimensiones_usadas(historial):
    """Extrae las dimensiones usadas en el historial"""
    return {
        "tonos":    [t["tono"]   for t in historial if t.get("tono")],
        "regiones": [t["region"] for t in historial if t.get("region")],
        "epocas":   [t["epoca"]  for t in historial if t.get("epoca")],
    }

# ============================================================
# PASO 2 — Selección inteligente con diversidad
# ============================================================

def calcular_diferencias(tema, usadas):
    """Cuenta cuántas dimensiones son diferentes al historial reciente"""
    diferencias = 0
    ultimos_tonos    = usadas["tonos"][-2:]    if usadas["tonos"]    else []
    ultimas_regiones = usadas["regiones"][-2:] if usadas["regiones"] else []
    ultimas_epocas   = usadas["epocas"][-2:]   if usadas["epocas"]   else []

    if tema.get("tono")   not in ultimos_tonos:    diferencias += 1
    if tema.get("region") not in ultimas_regiones: diferencias += 1
    if tema.get("epoca")  not in ultimas_epocas:   diferencias += 1

    return diferencias

def escoger_tema():
    """
    Selecciona un tema con lógica de prioridad y diversidad:
    0. Prioriza temas de fuente 'noticia' generados hoy (Agente 0)
    1. Intenta encontrar temas con 2+ dimensiones diferentes
    2. Si no hay, relaja a 1 dimensión diferente
    3. Si no hay, escoge cualquier tema disponible y notifica
    """
    print("Analizando historial de los últimos 7 días...")

    try:
        # Prioridad: temas de noticias generados hoy por el Agente 0
        hoy = datetime.now().date().isoformat()
        resultado_noticia = supabase.table("temas")\
            .select("*")\
            .eq("publicado", False)\
            .eq("fuente", "noticia")\
            .eq("fecha_noticia", hoy)\
            .execute()

        if resultado_noticia.data:
            tema = resultado_noticia.data[0]
            print(f"✓ Tema de actualidad encontrado para hoy: {tema['pregunta']}")
            return tema, "noticia_actualidad"

        # Obtener todos los temas históricos disponibles
        resultado = supabase.table("temas")\
            .select("*")\
            .eq("publicado", False)\
            .execute()
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo conectar a Supabase: {e}")

    temas_disponibles = resultado.data

    if not temas_disponibles:
        raise ErrorNegocio("No hay temas pendientes en la base de datos. Agrega más temas.")

    # Obtener historial
    historial = obtener_historial()
    usadas    = calcular_dimensiones_usadas(historial)

    print(f"Temas disponibles: {len(temas_disponibles)}")
    print(f"Historial últimos {VENTANA_DIAS} días: {len(historial)} publicaciones")
    print(f"Tonos recientes: {usadas['tonos'][-3:]}")
    print(f"Regiones recientes: {usadas['regiones'][-3:]}")
    print(f"Épocas recientes: {usadas['epocas'][-3:]}")

    # Intentar con 2+ dimensiones diferentes
    candidatos_2 = [t for t in temas_disponibles if calcular_diferencias(t, usadas) >= 2]
    if candidatos_2:
        tema = random.choice(candidatos_2)
        print(f"✓ Tema seleccionado con 2+ dimensiones diferentes")
        return tema, "diversidad_alta"

    # Relajar a 1 dimensión diferente
    candidatos_1 = [t for t in temas_disponibles if calcular_diferencias(t, usadas) >= 1]
    if candidatos_1:
        tema = random.choice(candidatos_1)
        print(f"⚠ Tema seleccionado con 1 dimensión diferente — diversidad limitada")
        notificar_canal(
            CANAL_CONTENIDO,
            f"⚠️ *Diversidad limitada hoy*\n"
            f"No se encontró tema con 2+ dimensiones diferentes. "
            f"Se seleccionó con 1 dimensión diferente."
        )
        return tema, "diversidad_baja"

    # Sin diversidad disponible — escoger cualquiera
    tema = random.choice(temas_disponibles)
    print(f"✗ Sin diversidad disponible — tema aleatorio")
    notificar_canal(
        CANAL_CONTENIDO,
        f"⚠️ *Sin diversidad disponible*\n"
        f"Todos los temas disponibles comparten dimensiones con el historial reciente. "
        f"Se seleccionó aleatoriamente. Considera agregar más temas variados."
    )
    return tema, "sin_diversidad"

# ============================================================
# PASO 3 — Generar contenido con Llama
# ============================================================

def generar_contenido(pregunta, categoria, tono, region, epoca):
    print(f"Generando contenido con {MODELO}...")

    contexto_tono = {
        "pesado":     "El tono debe ser serio y reflexivo, apropiado para temas difíciles.",
        "curioso":    "El tono debe ser sorprendente y entretenido, destacando lo inesperado.",
        "reflexivo":  "El tono debe invitar a la reflexión profunda sobre la condición humana.",
        "inspirador": "El tono debe ser positivo y motivador, destacando logros humanos."
    }.get(tono, "")

    prompt = f"""Eres un divulgador experto de historia y geografía del canal educativo "Café con Historia".
Tu enfoque es: "La historia explica el presente".
Tu misión es crear contenido educativo, veraz y accesible para hispanohablantes.

Responde esta pregunta con rigor histórico y tono conversacional:
PREGUNTA: {pregunta}
CATEGORÍA: {categoria}
REGIÓN: {region}
ÉPOCA HISTÓRICA: {epoca}
INDICACIÓN DE TONO: {contexto_tono}

Tu respuesta DEBE:
1. Empezar con un hook impactante que genere curiosidad inmediata
2. Explicar el contexto histórico con al menos una fecha o época concreta
3. Conectar explícitamente ese pasado con lo que vemos hoy en día
4. Usar tono conversacional — como explicarle a un amigo tomando un café
5. Tener entre 200 y 300 palabras
6. Terminar con una pregunta que invite a reflexionar
7. Incluir entre 3 y 7 emojis relevantes y coherentes con el tono del tema

IMPORTANTE: Este es contenido educativo legítimo sobre historia y geografía mundial.
Responde directamente con el contenido, sin introducción ni meta-comentarios."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=600)
        data = respuesta.json()
        contenido = data.get("response", "").strip()

        if not contenido:
            raise ErrorContenido("Llama devolvió una respuesta vacía")

        frases_rechazo = ["lo siento", "no puedo", "no es apropiado", "contenido falso", "no me es posible"]
        if any(frase in contenido.lower() for frase in frases_rechazo):
            raise ErrorContenido(f"Llama rechazó el prompt: {contenido[:200]}")

        print(f"Contenido generado: {len(contenido)} caracteres")
        return contenido

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al generar contenido")
    except (ErrorInfraestructura, ErrorContenido):
        raise
    except Exception as e:
        raise ErrorContenido(f"Error generando contenido: {e}")

# ============================================================
# PASO 4 — Guardar en Supabase
# ============================================================

def guardar_contenido(tema_id, contenido_slack):
    try:
        supabase.table("contenido").insert({
            "tema_id":       tema_id,
            "contenido_slack": contenido_slack,
            "modelo_usado":  MODELO,
            "aprobado":      False
        }).execute()

        supabase.table("temas").update({
            "publicado":          True,
            "fecha_publicacion":  datetime.now().isoformat(),
            "plataforma":         "pipeline"
        }).eq("id", tema_id).execute()

        print("✓ Contenido guardado en Supabase")
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo guardar en Supabase: {e}")

# ============================================================
# PASO 5 — Notificar a Slack
# ============================================================

def notificar_contenido_generado(pregunta, categoria, tono, region, epoca, contenido, nivel_diversidad):
    iconos = {
        "diversidad_alta":    "🟢",
        "diversidad_baja":    "🟡",
        "sin_diversidad":     "🔴",
        "noticia_actualidad": "📰"
    }
    icono = iconos.get(nivel_diversidad, "⚪")

    etiqueta = "Actualidad" if nivel_diversidad == "noticia_actualidad" else nivel_diversidad.replace('_', ' ')

    mensaje = f"""☕ *Café con Historia — Contenido generado*
*{pregunta}*
_{categoria} | {tono} | {region} | {epoca}_
{icono} {etiqueta}

{contenido}

---
_Pendiente de aprobación por el Agente 2_
_Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"""

    notificar_canal(CANAL_CONTENIDO, mensaje)

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente 1 (Investigador)")
    print("=" * 50)

    tema, nivel_diversidad = escoger_tema()

    pregunta  = tema["pregunta"]
    categoria = tema["categoria"]
    tono      = tema.get("tono", "reflexivo")
    region    = tema.get("region", "global")
    epoca     = tema.get("epoca", "contemporanea")
    tema_id   = tema["id"]

    print(f"\nTema: {pregunta}")
    print(f"Clasificación: {tono} | {region} | {epoca}")

    intento      = 1
    ultima_razon = ""

    while intento <= MAX_INTENTOS:
        print(f"\n--- Intento {intento}/{MAX_INTENTOS} ---")

        try:
            contenido = generar_contenido(pregunta, categoria, tono, region, epoca)
            guardar_contenido(tema_id, contenido)
            notificar_contenido_generado(pregunta, categoria, tono, region, epoca, contenido, nivel_diversidad)
            print(f"\n✓ Contenido generado y guardado en intento {intento}")
            return

        except ErrorInfraestructura:
            raise

        except ErrorContenido as e:
            print(f"Error de contenido en intento {intento}: {e}")
            ultima_razon = str(e)

        intento += 1

    notificar_error_contenido("Agente 1 — Investigador", pregunta, ultima_razon, MAX_INTENTOS)
    print(f"\n✗ No se pudo generar contenido después de {MAX_INTENTOS} intentos")

if __name__ == "__main__":
    correr_agente()