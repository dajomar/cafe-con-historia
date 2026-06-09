import os
import sys
import traceback
import pathlib
from datetime import datetime
from dotenv import load_dotenv

# ============================================================
# CONFIGURACIÓN
# ============================================================



SLACK_TOKEN     = os.getenv("SLACK_TOKEN")
CANAL_CONTENIDO = os.getenv("SLACK_CHANNEL", "#contenido")
CANAL_INFRA     = os.getenv("SLACK_CANAL_INFRA", "#infraestructura")
CANAL_ERRORES   = os.getenv("SLACK_CANAL_ERRORES", "#errores")
BASE_DIR = pathlib.Path(__file__).parent

load_dotenv(BASE_DIR / ".env")

# Días donde corre el Agente 0 (0=lunes, 2=miércoles, 4=viernes)
DIAS_AGENTE_0 = [0, 2, 4]

sys.path.insert(0, str(BASE_DIR / "utils"))
sys.path.insert(0, str(BASE_DIR / "agents"))

from errores import (
    ErrorInfraestructura,
    ErrorNegocio,
    verificar_ollama,
    verificar_token_facebook,
    notificar_infra,
    notificar_canal
)

# ============================================================
# LOGGING
# ============================================================

def log(mensaje):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{timestamp}] {mensaje}"
    print(linea)
    with open(BASE_DIR / "pipeline.log", "a", encoding="utf-8") as f:
        f.write(linea + "\n")

# ============================================================
# NOTIFICACIONES
# ============================================================

def notificar_inicio(con_agente_0):
    agente_0_txt = " + Agente 0 (Noticias)" if con_agente_0 else ""
    notificar_canal(
        CANAL_CONTENIDO,
        f"☕ *Café con Historia* — Pipeline iniciado{agente_0_txt}\n"
        f"_{datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    )

def notificar_exito():
    notificar_canal(
        CANAL_CONTENIDO,
        f"✅ *Pipeline completado exitosamente*\n"
        f"_{datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    )

# ============================================================
# VERIFICACIONES PREVIAS
# ============================================================

def verificar_infraestructura():
    log("Verificando infraestructura...")

    try:
        verificar_ollama()
        log("✓ Ollama corriendo")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA — Ollama: {e}")
        notificar_infra(str(e))
        sys.exit(1)

    try:
        verificar_token_facebook()
        log("✓ Token de Facebook verificado")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA — Facebook token: {e}")
        notificar_infra(str(e))
        sys.exit(1)

    log("✓ Infraestructura lista")

# ============================================================
# EJECUTAR AGENTES
# ============================================================

def ejecutar_agente(nombre, modulo_nombre):
    log(f"Iniciando {nombre}...")
    import importlib
    agente = importlib.import_module(modulo_nombre)
    importlib.reload(agente)
    agente.correr_agente()
    log(f"✓ {nombre} completado")

# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def main():
    log("=" * 50)
    log("CAFÉ CON HISTORIA — Pipeline iniciado")
    log("=" * 50)

    # Verificar infraestructura ANTES de todo
    verificar_infraestructura()

    # Determinar si hoy toca el Agente 0
    dia_semana = datetime.now().weekday()
    correr_agente_0 = dia_semana in DIAS_AGENTE_0
    log(f"Día de semana: {dia_semana} | Agente 0: {'Sí' if correr_agente_0 else 'No'}")

    notificar_inicio(correr_agente_0)

    # Agente 0 — Noticias (lunes, miércoles, viernes)
    if correr_agente_0:
        try:
            ejecutar_agente("Agente 0 — Noticias", "agente_0_noticias")
        except ErrorInfraestructura as e:
            log(f"ERROR INFRAESTRUCTURA en Agente 0: {e}")
            notificar_infra(f"Agente 0 — Noticias\n{str(e)}")
            sys.exit(1)
        except ErrorNegocio as e:
            # Error de negocio en Agente 0 no detiene el pipeline
            log(f"AVISO en Agente 0: {e}")
            notificar_canal(CANAL_ERRORES, f"ℹ️ *Agente 0 sin noticias relevantes hoy*\n{str(e)}")
        except Exception as e:
            # Error inesperado en Agente 0 no detiene el pipeline
            log(f"ERROR inesperado en Agente 0: {e}")
            notificar_canal(CANAL_ERRORES, f"⚠️ *Error en Agente 0*\n```{traceback.format_exc()[:300]}```")

    # Agente 1 — Investigador
    try:
        ejecutar_agente("Agente 1 — Investigador", "agente_1_investigador")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente 1: {e}")
        notificar_infra(f"Agente 1 — Investigador\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR en Agente 1: {e}")
        notificar_canal(CANAL_ERRORES, f"🚨 *Error en Agente 1*\n```{traceback.format_exc()[:500]}```")
        sys.exit(1)

    # Agente 2 — Editor crítico
    try:
        ejecutar_agente("Agente 2 — Editor", "agente_2_editor")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente 2: {e}")
        notificar_infra(f"Agente 2 — Editor\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR en Agente 2: {e}")
        notificar_canal(CANAL_ERRORES, f"🚨 *Error en Agente 2*\n```{traceback.format_exc()[:500]}```")
        sys.exit(1)

    # Agente Imagen — Generación de imagen con DALL-E 3
    # No es fatal: si falla, el Agente 3 publica sin imagen
    try:
        ejecutar_agente("Agente Imagen — DALL-E 3", "agente_imagen")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente Imagen: {e}")
        notificar_infra(f"Agente Imagen — DALL-E 3\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        log(f"AVISO — Agente Imagen falló, se publicará sin imagen: {e}")
        notificar_canal(CANAL_ERRORES, f"⚠️ *Agente Imagen falló* — se publicará sin imagen\n```{str(e)[:300]}```")

    # Agente 3 — Publicador
    try:
        ejecutar_agente("Agente 3 — Publicador", "agente_3_publicador")
    except ErrorInfraestructura as e:
        log(f"ERROR INFRAESTRUCTURA en Agente 3: {e}")
        notificar_infra(f"Agente 3 — Publicador\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR en Agente 3: {e}")
        notificar_canal(CANAL_ERRORES, f"🚨 *Error en Agente 3*\n```{traceback.format_exc()[:500]}```")
        sys.exit(1)

    log("Pipeline completado exitosamente")
    notificar_exito()

if __name__ == "__main__":
    main()