

import os
from dotenv import load_dotenv
from supabase import create_client

# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv("D:\\proyectos\\cafe-con-historia\\.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# TEMAS INICIALES
# ============================================================

TEMAS_INICIALES = [
    # Geopolítica
    {"pregunta": "¿Por qué Corea está dividida en dos países?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué China y Taiwán tienen tensiones?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué existe el conflicto entre Israel y Palestina?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Rusia invadió Ucrania?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Alberta y Saskatchewan quieren separarse de Canadá?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Quebec quiere independizarse de Canadá?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué existe el conflicto en Kashmir?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué hay tensiones entre India y Pakistán?", "categoria": "Geopolitica"},

    # Instituciones
    {"pregunta": "¿Por qué existe la OTAN?", "categoria": "Instituciones"},
    {"pregunta": "¿Por qué existe la ONU?", "categoria": "Instituciones"},
    {"pregunta": "¿Por qué existe el Fondo Monetario Internacional?", "categoria": "Instituciones"},
    {"pregunta": "¿Por qué existe la Unión Europea?", "categoria": "Instituciones"},
    {"pregunta": "¿Por qué existe el G7?", "categoria": "Instituciones"},

    # Cultura y sociedad
    {"pregunta": "¿Por qué Canadá tiene dos idiomas oficiales?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué usamos el calendario gregoriano?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué en el Reino Unido manejan por la izquierda?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué el inglés es el idioma internacional?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué existe el fútbol como deporte global?", "categoria": "Cultura"},

    # Economía global
    {"pregunta": "¿Por qué el dólar es la moneda de reserva mundial?", "categoria": "Economia"},
    {"pregunta": "¿Por qué Arabia Saudita tiene tanto poder?", "categoria": "Economia"},
    {"pregunta": "¿Por qué China se convirtió en la fábrica del mundo?", "categoria": "Economia"},
    {"pregunta": "¿Por qué hay tanta desigualdad entre el norte y el sur global?", "categoria": "Economia"},

    # Ciencia y tecnología
    {"pregunta": "¿Por qué funciona el GPS?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué existe internet?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué usamos el sistema métrico?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué Estados Unidos no usa el sistema métrico?", "categoria": "Ciencia"},

    # América Latina
    {"pregunta": "¿Por qué América Latina es pobre si tiene tantos recursos?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué Colombia tuvo 50 años de conflicto armado?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué Venezuela colapsó económicamente?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué hay tanta migración latinoamericana hacia Estados Unidos?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué Brasil habla portugués y el resto de Latinoamérica habla español?", "categoria": "America Latina"},

    # Canadá
    {"pregunta": "¿Por qué Canadá se confederó en 1867?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Canadá tiene una monarquía constitucional?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Montreal es la ciudad más grande de Quebec?", "categoria": "Geopolitica"},
]

# ============================================================
# FUNCIONES
# ============================================================

def insertar_temas():
    print(f"Insertando {len(TEMAS_INICIALES)} temas...")
    resultado = supabase.table("temas").insert(TEMAS_INICIALES).execute()
    print(f"✓ {len(resultado.data)} temas insertados correctamente")

def listar_temas():
    resultado = supabase.table("temas").select("*").execute()
    print(f"\nTemas en la base de datos: {len(resultado.data)}")
    for tema in resultado.data:
        estado = "✓" if tema["publicado"] else "○"
        print(f"  {estado} [{tema['categoria']}] {tema['pregunta']}")

def temas_pendientes():
    resultado = supabase.table("temas").select("*").eq("publicado", False).execute()
    print(f"\nTemas pendientes de publicar: {len(resultado.data)}")
    return resultado.data

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Setup inicial")
    print("=" * 50)

    insertar_temas()
    listar_temas()
    temas_pendientes()

    print("\n¡Base de datos lista!")