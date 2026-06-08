import os
import sys
import json
import requests
import pathlib
import xml.etree.ElementTree as ET
from datetime import datetime, date
from dotenv import load_dotenv
from supabase import create_client

BASE_DIR = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "utils"))

from errores import (
    ErrorInfraestructura,
    ErrorContenido,
    ErrorNegocio,
    notificar_canal,
    notificar_error_negocio
)

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv(BASE_DIR / ".env")

SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
CANAL_CONTENIDO = os.getenv("SLACK_CHANNEL", "#contenido")
OLLAMA_URL      = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434") + "/api/generate"
MODELO          = "llama3.1"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# FUENTES RSS
# ============================================================

FUENTES_RSS = [
    {"nombre": "BBC Mundo",        "url": "https://feeds.bbci.co.uk/mundo/rss.xml"},
    {"nombre": "Deutsche Welle",   "url": "https://rss.dw.com/rdf/rss-es-all"},
    {"nombre": "France 24",        "url": "https://www.france24.com/es/rss"},
]

# Categorías relevantes para Café con Historia
CATEGORIAS_RELEVANTES = [
    "política", "guerra", "conflicto", "historia", "economía",
    "sociedad", "cultura", "geopolítica", "internacional",
    "crisis", "elecciones", "acuerdo", "tensión", "independencia"
]

# ============================================================
# PASO 1 — Leer noticias de RSS
# ============================================================

def leer_rss(url, nombre):
    print(f"  Leyendo {nombre}...")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        respuesta = requests.get(url, timeout=15, headers=headers)
        respuesta.raise_for_status()

        root = ET.fromstring(respuesta.content)
        noticias = []

        # Parsear items del RSS
        for item in root.iter("item"):
            titulo = item.findtext("title", "").strip()
            descripcion = item.findtext("description", "").strip()
            link = item.findtext("link", "").strip()
            fecha = item.findtext("pubDate", "").strip()

            if titulo and len(titulo) > 10:
                noticias.append({
                    "titulo": titulo,
                    "descripcion": descripcion[:300] if descripcion else "",
                    "link": link,
                    "fecha": fecha,
                    "fuente": nombre
                })

        print(f"  → {len(noticias)} noticias encontradas")
        return noticias[:10]  # Solo las 10 más recientes

    except requests.ConnectionError:
        print(f"  ✗ No se pudo conectar a {nombre}")
        return []
    except ET.ParseError:
        print(f"  ✗ Error parseando RSS de {nombre}")
        return []
    except Exception as e:
        print(f"  ✗ Error leyendo {nombre}: {e}")
        return []

def obtener_todas_noticias():
    todas = []
    for fuente in FUENTES_RSS:
        noticias = leer_rss(fuente["url"], fuente["nombre"])
        todas.extend(noticias)
    return todas

# ============================================================
# PASO 2 — Filtrar noticias relevantes con Llama
# ============================================================

def seleccionar_noticia_relevante(noticias):
    print("Seleccionando noticia más relevante para Café con Historia...")

    lista_noticias = ""
    for i, n in enumerate(noticias[:20]):
        lista_noticias += f"{i+1}. [{n['fuente']}] {n['titulo']}\n   {n['descripcion'][:150]}\n\n"

    prompt = f"""Eres el editor de "Café con Historia", canal educativo donde "La historia explica el presente".

Analiza estas noticias recientes y selecciona la MÁS RELEVANTE para el canal — aquella que mejor se preste para conectar con un evento histórico profundo.

Criterios de selección:
- Conflictos geopolíticos con raíces históricas
- Tensiones entre países o regiones con historia compleja
- Crisis económicas o políticas con contexto histórico rico
- Eventos culturales o sociales con origen histórico interesante
- Evita: deportes, farándula, tecnología sin contexto histórico, desastres naturales simples

NOTICIAS DISPONIBLES:
{lista_noticias}

Responde ÚNICAMENTE con un JSON:
{{
  "numero": <número de la noticia seleccionada>,
  "razon": "<por qué esta noticia se presta para Café con Historia>",
  "angulo_historico": "<qué pregunta histórica inspira esta noticia>"
}}

Responde SOLO con el JSON."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=120)
        data = respuesta.json()
        texto = data.get("response", "").strip()

        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            resultado = json.loads(texto[inicio:fin])
            numero = resultado.get("numero", 1) - 1
            if 0 <= numero < len(noticias):
                noticia = noticias[numero]
                noticia["angulo_historico"] = resultado.get("angulo_historico", "")
                noticia["razon_seleccion"] = resultado.get("razon", "")
                return noticia
        return noticias[0] if noticias else None

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al seleccionar noticia")
    except Exception as e:
        print(f"Error seleccionando noticia: {e}")
        return noticias[0] if noticias else None

# ============================================================
# PASO 3 — Generar tema histórico inspirado en la noticia
# ============================================================

def generar_tema_historico(noticia):
    print("Generando tema histórico inspirado en la noticia...")

    prompt = f"""Eres el editor de "Café con Historia", canal educativo donde "La historia explica el presente".

Esta noticia de hoy inspiró una reflexión histórica:
NOTICIA: {noticia['titulo']}
DESCRIPCIÓN: {noticia['descripcion']}
ÁNGULO HISTÓRICO SUGERIDO: {noticia.get('angulo_historico', '')}

Tu tarea es generar UNA pregunta histórica profunda inspirada en esta noticia.
La pregunta debe:
1. Referirse al origen histórico del evento — no a la noticia en sí
2. Ser atemporal — válida hoy y en 5 años
3. Tener el formato "¿Por qué...?" o "¿Cómo...?" o "¿Cuándo...?"
4. Conectar el pasado con el presente implícitamente

Ejemplos del estilo correcto:
- Noticia sobre Venezuela → "¿Por qué Venezuela colapsó económicamente?"
- Noticia sobre Kashmir → "¿Por qué India y Pakistán llevan 70 años en conflicto?"
- Noticia sobre Brexit → "¿Por qué el Reino Unido nunca se sintió parte de Europa?"

Clasifica también el tema:
- categoria: Geopolitica | Instituciones | Cultura | Economia | Ciencia | America Latina
- tono: pesado | curioso | reflexivo | inspirador
- region: america_latina | norteamerica | europa | asia | africa | global
- epoca: antigua | medieval | moderna | contemporanea | actual

Responde ÚNICAMENTE con un JSON:
{{
  "pregunta": "<la pregunta histórica>",
  "categoria": "<categoría>",
  "tono": "<tono>",
  "region": "<región>",
  "epoca": "<época>"
}}

Responde SOLO con el JSON."""

    payload = {"model": MODELO, "prompt": prompt, "stream": False}

    try:
        respuesta = requests.post(OLLAMA_URL, json=payload, timeout=120)
        data = respuesta.json()
        texto = data.get("response", "").strip()

        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            return json.loads(texto[inicio:fin])
        raise ErrorContenido("Llama no generó JSON válido para el tema")

    except requests.ConnectionError:
        raise ErrorInfraestructura("Ollama no responde al generar tema")
    except json.JSONDecodeError as e:
        raise ErrorContenido(f"Error parseando tema: {e}")

# ============================================================
# PASO 4 — Verificar que el tema no existe ya
# ============================================================

def tema_ya_existe(pregunta):
    try:
        resultado = supabase.table("temas")\
            .select("id")\
            .ilike("pregunta", f"%{pregunta[:30]}%")\
            .execute()
        return len(resultado.data) > 0
    except Exception:
        return False

# ============================================================
# PASO 5 — Guardar tema en Supabase
# ============================================================

def guardar_tema(tema_data, noticia):
    try:
        supabase.table("temas").insert({
            "pregunta":      tema_data["pregunta"],
            "categoria":     tema_data["categoria"],
            "tono":          tema_data["tono"],
            "region":        tema_data["region"],
            "epoca":         tema_data["epoca"],
            "publicado":     False,
            "fuente":        "noticia",
            "url_noticia":   noticia.get("link", ""),
            "fecha_noticia": date.today().isoformat()
        }).execute()
        print(f"✓ Tema guardado: {tema_data['pregunta']}")
    except Exception as e:
        raise ErrorInfraestructura(f"No se pudo guardar tema en Supabase: {e}")

# ============================================================
# PASO 6 — Notificar a Slack
# ============================================================

def notificar_tema_generado(tema_data, noticia):
    mensaje = f"""📰 *Agente 0 — Tema de actualidad generado*

*Noticia del día:*
_{noticia['titulo']}_ — {noticia['fuente']}

*Tema histórico generado:*
*{tema_data['pregunta']}*
_{tema_data['categoria']} | {tema_data['tono']} | {tema_data['region']} | {tema_data['epoca']}_

_El Agente 1 priorizará este tema hoy_"""

    notificar_canal(CANAL_CONTENIDO, mensaje)

# ============================================================
# AGENTE PRINCIPAL
# ============================================================

def correr_agente():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Agente 0 (Noticias)")
    print("=" * 50)

    # Paso 1 — Leer noticias
    print("\n[1] Leyendo fuentes RSS...")
    noticias = obtener_todas_noticias()

    if not noticias:
        raise ErrorNegocio("No se pudieron obtener noticias de ninguna fuente RSS.")

    print(f"Total noticias obtenidas: {len(noticias)}")

    # Paso 2 — Seleccionar la más relevante
    print("\n[2] Seleccionando noticia relevante...")
    noticia = seleccionar_noticia_relevante(noticias)

    if not noticia:
        raise ErrorNegocio("No se pudo seleccionar una noticia relevante.")

    print(f"Noticia seleccionada: {noticia['titulo']}")

    # Paso 3 — Generar tema histórico
    print("\n[3] Generando tema histórico...")
    tema_data = generar_tema_historico(noticia)

    if not tema_data or not tema_data.get("pregunta"):
        raise ErrorContenido("No se pudo generar un tema histórico válido.")

    print(f"Tema generado: {tema_data['pregunta']}")

    # Paso 4 — Verificar que no existe
    if tema_ya_existe(tema_data["pregunta"]):
        raise ErrorNegocio(f"Tema similar ya existe en la base de datos: {tema_data['pregunta']}")

    # Paso 5 — Guardar
    print("\n[4] Guardando tema en Supabase...")
    guardar_tema(tema_data, noticia)

    # Paso 6 — Notificar
    notificar_tema_generado(tema_data, noticia)

    print(f"\n✓ Agente 0 completado exitosamente")
    print(f"Tema: {tema_data['pregunta']}")

if __name__ == "__main__":
    correr_agente()