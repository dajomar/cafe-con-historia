import os
import json
import requests
from dotenv import load_dotenv
from supabase import create_client

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv("D:\\proyectos\\cafe-con-historia\\.env")

SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY")
OLLAMA_URL    = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434") + "/api/generate"
MODELO        = "llama3.1"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# VALORES VÁLIDOS
# ============================================================

TONOS    = ["pesado", "curioso", "reflexivo", "inspirador"]
REGIONES = ["america_latina", "norteamerica", "europa", "asia", "africa", "global"]
EPOCAS   = ["antigua", "medieval", "moderna", "contemporanea", "actual"]

# ============================================================
# CLASIFICAR UN TEMA CON LLAMA
# ============================================================

def clasificar_tema(pregunta, categoria):
    prompt = f"""Eres un clasificador de contenido educativo del canal "Café con Historia".
Clasifica este tema según tres dimensiones.

TEMA: {pregunta}
CATEGORÍA: {categoria}

DIMENSIONES:

1. TONO — ¿Qué emoción principal genera este tema?
   - pesado: temas de guerra, conflicto, tragedia, crisis
   - curioso: datos sorprendentes, hechos poco conocidos, inventos
   - reflexivo: temas filosóficos, sociales, identitarios
   - inspirador: logros humanos, superación, avances positivos

2. REGIÓN — ¿A qué región del mundo se refiere principalmente?
   - america_latina
   - norteamerica
   - europa
   - asia
   - africa
   - global (si aplica a todo el mundo)

3. ÉPOCA — ¿A qué período histórico pertenece el origen del tema?
   - antigua: antes del año 500
   - medieval: 500 - 1500
   - moderna: 1500 - 1900
   - contemporanea: 1900 - 2000
   - actual: después del año 2000

Responde ÚNICAMENTE con un JSON con este formato exacto:
{{
  "tono": "<valor>",
  "region": "<valor>",
  "epoca": "<valor>",
  "razon": "<explicación breve de 1 línea>"
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

            # Validar valores
            if resultado.get("tono") not in TONOS:
                resultado["tono"] = "reflexivo"
            if resultado.get("region") not in REGIONES:
                resultado["region"] = "global"
            if resultado.get("epoca") not in EPOCAS:
                resultado["epoca"] = "contemporanea"

            return resultado
        return None
    except Exception as e:
        print(f"  Error clasificando: {e}")
        return None

# ============================================================
# CLASIFICAR TODOS LOS TEMAS
# ============================================================

def clasificar_todos():
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Clasificador de temas")
    print("=" * 50)

    # Obtener temas sin clasificar
    resultado = supabase.table("temas")\
        .select("id, pregunta, categoria, tono, region, epoca")\
        .is_("tono", "null")\
        .execute()

    temas = resultado.data
    print(f"\nTemas sin clasificar: {len(temas)}")

    if not temas:
        print("Todos los temas ya están clasificados.")
        return

    exitosos = 0
    fallidos = 0

    for i, tema in enumerate(temas):
        print(f"\n[{i+1}/{len(temas)}] {tema['pregunta'][:60]}...")

        clasificacion = clasificar_tema(tema["pregunta"], tema["categoria"])

        if clasificacion:
            supabase.table("temas").update({
                "tono":   clasificacion["tono"],
                "region": clasificacion["region"],
                "epoca":  clasificacion["epoca"]
            }).eq("id", tema["id"]).execute()

            print(f"  ✓ tono={clasificacion['tono']} | region={clasificacion['region']} | epoca={clasificacion['epoca']}")
            print(f"  → {clasificacion.get('razon', '')}")
            exitosos += 1
        else:
            print(f"  ✗ No se pudo clasificar — asignando valores por defecto")
            supabase.table("temas").update({
                "tono":   "reflexivo",
                "region": "global",
                "epoca":  "contemporanea"
            }).eq("id", tema["id"]).execute()
            fallidos += 1

    print(f"\n{'='*50}")
    print(f"Clasificación completada:")
    print(f"  ✓ Exitosos: {exitosos}")
    print(f"  ✗ Con valores por defecto: {fallidos}")
    print(f"{'='*50}")

if __name__ == "__main__":
    clasificar_todos()