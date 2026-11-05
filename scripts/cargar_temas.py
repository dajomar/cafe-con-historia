import os
import sys
import json
import pathlib
import requests
from dotenv import load_dotenv
from supabase import create_client

# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = pathlib.Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OLLAMA_URL   = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434") + "/api/generate"
MODELO       = "llama3.1"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# TEMAS NUEVOS
# ============================================================

TEMAS_NUEVOS = [
    # Geopolítica
    {"pregunta": "¿Por qué EE.UU. tiene bases militares en todo el mundo?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Alemania fue dividida después de la Segunda Guerra Mundial?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Cuba lleva más de 60 años con el mismo sistema político?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué hay tensiones entre Grecia y Turquía en el Mediterráneo?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Kosovo declaró su independencia de Serbia?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Irán y EE.UU. son enemigos desde 1979?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Arabia Saudita e Irán son rivales regionales?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué México perdió la mitad de su territorio ante EE.UU.?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Panamá fue separada de Colombia?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Bolivia no tiene salida al mar?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Corea del Norte es uno de los países más cerrados del mundo?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Turquía tiene una relación tan tensa con la Unión Europea?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué existe el conflicto entre Marruecos y el Sahara Occidental?", "categoria": "Geopolitica"},

    # Guerras y conflictos
    {"pregunta": "¿Por qué ocurrió la Primera Guerra Mundial?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué Hitler llegó al poder en Alemania?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué EE.UU. lanzó bombas atómicas sobre Japón?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué ocurrió la Guerra de Vietnam y qué dejó?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué fracasó la invasión de Bahía de Cochinos en Cuba?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué ocurrió la Guerra de las Malvinas?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué ocurrió el genocidio en Ruanda?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué la URSS invadió Afganistán?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué EE.UU. invadió Irak en 2003?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué ocurrió la Guerra de Corea?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué Alemania nazi pudo conquistar Europa tan rápido?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué ocurrió la Revolución Francesa?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué ocurrió la Guerra del Chaco entre Bolivia y Paraguay?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué los romanos destruyeron Cartago?", "categoria": "Guerras"},

    # Imperios y colonialismo
    {"pregunta": "¿Por qué el Imperio Romano colapsó?", "categoria": "Imperios"},
    {"pregunta": "¿Por qué España colonizó América Latina y no otro país europeo?", "categoria": "Imperios"},
    {"pregunta": "¿Por qué el Imperio Británico llegó a dominar el 25% del mundo?", "categoria": "Imperios"},
    {"pregunta": "¿Por qué el Imperio Otomano colapsó después de la Primera Guerra Mundial?", "categoria": "Imperios"},
    {"pregunta": "¿Por qué África fue colonizada por Europa en el siglo XIX?", "categoria": "Imperios"},
    {"pregunta": "¿Por qué los aztecas fueron derrotados por pocos españoles?", "categoria": "Imperios"},
    {"pregunta": "¿Por qué el Imperio Mongol fue el más grande de la historia terrestre?", "categoria": "Imperios"},
    {"pregunta": "¿Por qué el Imperio Inca colapsó tan rápido ante los españoles?", "categoria": "Imperios"},
    {"pregunta": "¿Por qué la descolonización de África fue tan violenta en el siglo XX?", "categoria": "Imperios"},
    {"pregunta": "¿Por qué la independencia de India de Gran Bretaña fue tan sangrienta?", "categoria": "Imperios"},

    # Economía
    {"pregunta": "¿Por qué ocurrió la Gran Depresión de 1929?", "categoria": "Economia"},
    {"pregunta": "¿Por qué los países nórdicos son los más felices y prósperos del mundo?", "categoria": "Economia"},
    {"pregunta": "¿Por qué Japón se convirtió en potencia económica tras la derrota en la guerra?", "categoria": "Economia"},
    {"pregunta": "¿Por qué Alemania volvió a ser la economía más fuerte de Europa?", "categoria": "Economia"},
    {"pregunta": "¿Por qué el petróleo controla la política mundial?", "categoria": "Economia"},
    {"pregunta": "¿Por qué Corea del Sur pasó de ser pobre a ser potencia tecnológica?", "categoria": "Economia"},
    {"pregunta": "¿Por qué India se está convirtiendo en la economía más grande del mundo?", "categoria": "Economia"},
    {"pregunta": "¿Por qué la crisis financiera de 2008 afectó a todo el mundo?", "categoria": "Economia"},
    {"pregunta": "¿Por qué Suiza es tan rica siendo un país tan pequeño?", "categoria": "Economia"},
    {"pregunta": "¿Por qué Singapur pasó de ser un puerto pobre a un centro financiero mundial?", "categoria": "Economia"},
    {"pregunta": "¿Por qué los países del Golfo Pérsico tienen tanto dinero?", "categoria": "Economia"},
    {"pregunta": "¿Por qué la deuda externa arruinó a tantos países latinoamericanos?", "categoria": "Economia"},
    {"pregunta": "¿Por qué Argentina fue rica en 1900 y dejó de serlo?", "categoria": "Economia"},

    # Cultura y sociedad
    {"pregunta": "¿Por qué los países latinoamericanos son tan religiosos?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué el tango nació en Argentina y Uruguay?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué Halloween se celebra cada vez más en América Latina?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué el idioma español tiene tantos acentos y variantes?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué la gastronomía mexicana es Patrimonio de la Humanidad?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué el fútbol generó una guerra entre El Salvador y Honduras?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué el catolicismo llegó a América Latina y no el protestantismo?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué los romanos construyeron el Coliseo?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué la Iglesia Católica tuvo tanto poder político en Europa medieval?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué se inventó la imprenta y cómo cambió el mundo?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué el Renacimiento comenzó en Italia?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué la Ilustración cambió la forma de pensar del mundo occidental?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué el rock and roll fue considerado peligroso en sus inicios?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué Hollywood domina la industria cinematográfica mundial?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué los Juegos Olímpicos modernos nacieron en 1896?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué el béisbol es el deporte nacional en varios países latinoamericanos?", "categoria": "Cultura"},

    # Ciencia y tecnología
    {"pregunta": "¿Por qué la Revolución Industrial comenzó en Inglaterra?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué la carrera espacial fue una guerra entre EE.UU. y la URSS?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué se inventó la bomba atómica y qué consecuencias tuvo?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué Silicon Valley se convirtió en el centro tecnológico del mundo?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué las vacunas son uno de los mayores logros de la humanidad?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué el descubrimiento de los antibióticos cambió la historia de la medicina?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué se construyó el canal de Panamá y quién pagó el precio real?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué la exploración espacial es también una carrera geopolítica?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué el cambio climático es también un problema político?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué la inteligencia artificial está cambiando el mercado laboral?", "categoria": "Ciencia"},

    # Derechos y movimientos sociales
    {"pregunta": "¿Por qué tardó tanto el movimiento sufragista en lograr el voto femenino?", "categoria": "Derechos"},
    {"pregunta": "¿Por qué Martin Luther King fue asesinado?", "categoria": "Derechos"},
    {"pregunta": "¿Por qué el apartheid en Sudáfrica duró tantas décadas?", "categoria": "Derechos"},
    {"pregunta": "¿Por qué los movimientos indígenas en América Latina están resurgiendo?", "categoria": "Derechos"},
    {"pregunta": "¿Por qué ocurrió el Holocausto y cómo fue posible?", "categoria": "Derechos"},
    {"pregunta": "¿Por qué la esclavitud tardó tanto en ser abolida?", "categoria": "Derechos"},
    {"pregunta": "¿Por qué las dictaduras latinoamericanas contaron con apoyo de EE.UU.?", "categoria": "Derechos"},
    {"pregunta": "¿Por qué la Revolución Mexicana cambió el concepto de identidad nacional?", "categoria": "Derechos"},
    {"pregunta": "¿Por qué Nelson Mandela pasó 27 años en prisión?", "categoria": "Derechos"},
    {"pregunta": "¿Por qué los movimientos guerrilleros surgieron en casi toda América Latina?", "categoria": "Derechos"},

    # Canadá
    {"pregunta": "¿Por qué Canadá recibe más inmigrantes per cápita que casi cualquier país?", "categoria": "Canada"},
    {"pregunta": "¿Por qué los pueblos indígenas de Canadá sufrieron las escuelas residenciales?", "categoria": "Canada"},
    {"pregunta": "¿Por qué Canadá tiene un sistema de salud universal pero EE.UU. no?", "categoria": "Canada"},
    {"pregunta": "¿Por qué Montreal tiene una cultura tan diferente al resto de Canadá?", "categoria": "Canada"},
    {"pregunta": "¿Por qué EE.UU. y Canadá tienen una relación tan asimétrica?", "categoria": "Canada"},
    {"pregunta": "¿Por qué Toronto se convirtió en una de las ciudades más multiculturales del mundo?", "categoria": "Canada"},
    {"pregunta": "¿Por qué los inmigrantes latinoamericanos eligieron Canadá sobre EE.UU.?", "categoria": "Canada"},

    # Migraciones
    {"pregunta": "¿Por qué millones de europeos emigraron a América entre 1880 y 1930?", "categoria": "Migraciones"},
    {"pregunta": "¿Por qué hay tanta diáspora libanesa en América Latina?", "categoria": "Migraciones"},
    {"pregunta": "¿Por qué los chinos construyeron los ferrocarriles de América del Norte y fueron discriminados?", "categoria": "Migraciones"},
    {"pregunta": "¿Por qué los venezolanos son hoy la mayor diáspora de América Latina?", "categoria": "Migraciones"},
    {"pregunta": "¿Por qué hay comunidades judías en casi todos los países del mundo?", "categoria": "Migraciones"},
    {"pregunta": "¿Por qué hay tanta migración latinoamericana hacia Canadá en el siglo XXI?", "categoria": "Migraciones"},

    # Historia antigua y medieval
    {"pregunta": "¿Por qué los egipcios construyeron las pirámides?", "categoria": "Historia"},
    {"pregunta": "¿Por qué Grecia es considerada la cuna de la democracia?", "categoria": "Historia"},
    {"pregunta": "¿Por qué Alejandro Magno conquistó tanto en tan poco tiempo?", "categoria": "Historia"},
    {"pregunta": "¿Por qué Roma pasó de república a imperio?", "categoria": "Historia"},
    {"pregunta": "¿Por qué la Peste Negra cambió para siempre la historia de Europa?", "categoria": "Historia"},
    {"pregunta": "¿Por qué las Cruzadas fracasaron?", "categoria": "Historia"},
    {"pregunta": "¿Por qué los vikingos llegaron a América antes que Colón?", "categoria": "Historia"},
    {"pregunta": "¿Por qué Carlomagno es considerado el padre de Europa?", "categoria": "Historia"},
    {"pregunta": "¿Por qué el Islam se expandió tan rápido en el siglo VII?", "categoria": "Historia"},
    {"pregunta": "¿Por qué los mayas desaparecieron como civilización?", "categoria": "Historia"},
    {"pregunta": "¿Por qué Tenochtitlán era la ciudad más grande del mundo en el siglo XV?", "categoria": "Historia"},
    {"pregunta": "¿Por qué los romanos adoptaron el cristianismo como religión oficial?", "categoria": "Historia"},
    {"pregunta": "¿Por qué Atenas y Esparta eran tan diferentes siendo vecinas?", "categoria": "Historia"},
    {"pregunta": "¿Por qué Cartagena de Indias fue el puerto más importante de América colonial?", "categoria": "Historia"},

    # Religión
    {"pregunta": "¿Por qué el protestantismo dividió a Europa en el siglo XVI?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué la Inquisición duró más de 300 años?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué el Vaticano es un estado independiente?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué el Islam tiene tantas divisiones internas entre sunitas y chiítas?", "categoria": "Cultura"},

    # Estados Unidos
    {"pregunta": "¿Por qué EE.UU. se convirtió en la superpotencia del siglo XX?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué EE.UU. tiene una relación tan contradictoria con América Latina?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué la Guerra Civil estadounidense todavía genera divisiones hoy?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué los latinos son la minoría más grande de EE.UU.?", "categoria": "Migraciones"},
    {"pregunta": "¿Por qué la inmigración es un tema tan polarizante en EE.UU.?", "categoria": "Geopolitica"},

    # Asia
    {"pregunta": "¿Por qué Japón atacó Pearl Harbor?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué la Revolución Cultural china fue una tragedia histórica?", "categoria": "Historia"},
    {"pregunta": "¿Por qué los Tigres Asiáticos crecieron tan rápido en el siglo XX?", "categoria": "Economia"},
    {"pregunta": "¿Por qué Vietnam venció primero a Francia y luego a EE.UU.?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué Japón se modernizó tan rápido en el siglo XIX con la Era Meiji?", "categoria": "Historia"},

    # Medio Oriente
    {"pregunta": "¿Por qué Irán tuvo una revolución islámica en 1979?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué Siria colapsó en una guerra civil?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué Israel y sus vecinos árabes han tenido tantas guerras?", "categoria": "Guerras"},

    # África
    {"pregunta": "¿Por qué África tiene tantas fronteras artificiales?", "categoria": "Imperios"},
    {"pregunta": "¿Por qué Etiopía nunca fue colonizada por Europa?", "categoria": "Historia"},
    {"pregunta": "¿Por qué el Congo tiene tantos recursos y tanta pobreza?", "categoria": "Economia"},
    {"pregunta": "¿Por qué la esclavitud transatlántica duró más de 300 años?", "categoria": "Historia"},
    {"pregunta": "¿Por qué Sudáfrica tiene una de las mayores desigualdades del mundo?", "categoria": "Economia"},

    # América Latina
    {"pregunta": "¿Por qué las independencias latinoamericanas no trajeron igualdad social?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué los caudillos dominaron la política latinoamericana del siglo XIX?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué el narcotráfico se convirtió en poder político en Colombia y México?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué Chile tuvo el golpe de Estado más famoso de América Latina?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué Cuba resistió el embargo de EE.UU. por más de 60 años?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué Haití es el país más pobre del hemisferio occidental?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué la Revolución Cubana inspiró a toda América Latina?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué Colombia tuvo la guerrilla más larga de América Latina?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué Perú tuvo la experiencia de Sendero Luminoso?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué la derecha y la izquierda en América Latina son tan polarizadas?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué los inmigrantes italianos transformaron la cultura de Argentina y Uruguay?", "categoria": "America Latina"},
    {"pregunta": "¿Por qué la minería destruyó el medio ambiente en la historia de América Latina?", "categoria": "America Latina"},

    # Comunicación y medios
    {"pregunta": "¿Por qué la radio fue el primer medio de comunicación masiva?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué la televisión cambió la política para siempre?", "categoria": "Cultura"},
    {"pregunta": "¿Por qué las redes sociales aceleraron las revoluciones del siglo XXI?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué la prensa libre es una conquista histórica reciente?", "categoria": "Derechos"},

    # Medio ambiente e historia
    {"pregunta": "¿Por qué la Amazonía es considerada el pulmón del mundo?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué el Canal de Suez cambió el comercio mundial?", "categoria": "Economia"},
    {"pregunta": "¿Por qué las guerras del agua serán el conflicto del siglo XXI?", "categoria": "Ciencia"},
    {"pregunta": "¿Por qué la desaparición de civilizaciones antiguas suele relacionarse con el clima?", "categoria": "Historia"},

    # Guerra Fría
    {"pregunta": "¿Por qué la Guerra Fría entre EE.UU. y la URSS nunca llegó a ser caliente?", "categoria": "Guerras"},
    {"pregunta": "¿Por qué la URSS colapsó en 1991?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué el Muro de Berlín duró 28 años?", "categoria": "Geopolitica"},
    {"pregunta": "¿Por qué la crisis de los misiles en Cuba puso al mundo al borde de la guerra nuclear?", "categoria": "Guerras"},
]

# ============================================================
# PASO 1 — INSERTAR TEMAS (evitando duplicados)
# ============================================================

TONOS    = ["pesado", "curioso", "reflexivo", "inspirador"]
REGIONES = ["america_latina", "norteamerica", "europa", "asia", "africa", "global"]
EPOCAS   = ["antigua", "medieval", "moderna", "contemporanea", "actual"]

def insertar_temas():
    print("\n" + "=" * 50)
    print("PASO 1 — Insertando temas")
    print("=" * 50)

    # Obtener preguntas existentes para evitar duplicados
    existentes = supabase.table("temas").select("pregunta").execute()
    preguntas_existentes = {t["pregunta"] for t in existentes.data}

    nuevos = [t for t in TEMAS_NUEVOS if t["pregunta"] not in preguntas_existentes]

    if not nuevos:
        print("Todos los temas ya existen en la base de datos.")
        return 0

    print(f"Temas a insertar: {len(nuevos)} (de {len(TEMAS_NUEVOS)} totales)")
    print(f"Omitidos por duplicado: {len(TEMAS_NUEVOS) - len(nuevos)}")

    resultado = supabase.table("temas").insert(nuevos).execute()
    insertados = len(resultado.data)
    print(f"✓ {insertados} temas insertados correctamente")
    return insertados

# ============================================================
# PASO 2 — CLASIFICAR TEMAS SIN CLASIFICAR
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
        fin    = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            resultado = json.loads(texto[inicio:fin])

            if resultado.get("tono")   not in TONOS:    resultado["tono"]   = "reflexivo"
            if resultado.get("region") not in REGIONES: resultado["region"] = "global"
            if resultado.get("epoca")  not in EPOCAS:   resultado["epoca"]  = "contemporanea"

            return resultado
        return None
    except Exception as e:
        print(f"  Error clasificando: {e}")
        return None

def clasificar_temas():
    print("\n" + "=" * 50)
    print("PASO 2 — Clasificando temas con Llama")
    print("=" * 50)

    resultado = supabase.table("temas")\
        .select("id, pregunta, categoria, tono, region, epoca")\
        .is_("tono", "null")\
        .execute()

    temas = resultado.data
    print(f"Temas sin clasificar: {len(temas)}")

    if not temas:
        print("Todos los temas ya están clasificados.")
        return

    exitosos = 0
    fallidos  = 0

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

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("CAFÉ CON HISTORIA — Cargar temas")
    print("=" * 50)

    insertados = insertar_temas()
    clasificar_temas()

    print("\n¡Listo! Temas disponibles para el pipeline.")
