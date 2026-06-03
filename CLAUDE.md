# Café con Historia — Contexto del proyecto

## Visión
Canal educativo con el enfoque: **"La historia explica el presente"**.
Contenido diario que conecta acontecimientos históricos con situaciones del mundo actual, dirigido a hispanohablantes.

No es un canal de datos curiosos — usa la historia como lente para entender por qué el mundo de hoy funciona como funciona.

**Ejemplos de contenido:**
- ¿Por qué Corea está dividida en dos países?
- ¿Por qué Canadá tiene dos idiomas oficiales?
- ¿Por qué existe la OTAN?
- ¿Por qué Alberta y Saskatchewan quieren separarse de Canadá?
- ¿Por qué América Latina es pobre si tiene tantos recursos?

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Base de datos | Supabase (PostgreSQL) |
| Modelo de lenguaje | Llama 3.1 via Ollama (local) |
| Notificaciones | Slack API |
| Publicación | Facebook Graph API v25.0 |
| Lenguaje | Python 3.11 |
| Entorno | HP Z420 / Windows 11 Pro |

---

## Estructura del proyecto

```
cafe-con-historia/
├── agents/
│   ├── agente_1_investigador.py   # Genera contenido con Llama
│   ├── agente_2_editor.py         # Evalúa calidad (score mín 7/10)
│   └── agente_3_publicador.py     # Publica en Facebook
├── database/
│   └── migrations/
│       ├── 001_crear_tablas_iniciales.sql
│       └── 002_agregar_campos_calidad.sql
├── scripts/
│   ├── insertar_temas.py
│   └── setup_scheduler.ps1
├── utils/
│   └── errores.py                 # Manejo centralizado de errores
├── main.py                        # Orquestador del pipeline
├── CLAUDE.md
├── requirements.txt
├── .env
└── .gitignore
```

---

## Base de datos (Supabase)

**Proyecto:** cafe-con-historia | **Región:** Americas

### Tabla: temas
```sql
id                INTEGER PRIMARY KEY
pregunta          TEXT NOT NULL
categoria         TEXT NOT NULL
publicado         BOOLEAN DEFAULT FALSE
fecha_publicacion TIMESTAMP
plataforma        TEXT
```

### Tabla: contenido
```sql
id                  INTEGER PRIMARY KEY
tema_id             INTEGER REFERENCES temas(id)
contenido_slack     TEXT
contenido_facebook  TEXT
fecha_generacion    TIMESTAMP DEFAULT NOW()
modelo_usado        TEXT DEFAULT 'llama3.1'
score_calidad       INTEGER
intentos_generacion INTEGER DEFAULT 1
aprobado            BOOLEAN DEFAULT FALSE
```

### Categorías
- Geopolitica
- Instituciones
- Cultura
- Economia
- Ciencia
- America Latina

---

## Pipeline de agentes

### Flujo completo
```
main.py
  → verificar_infraestructura() — Ollama + token Facebook
  → Agente 1 — Investigador
  → Agente 2 — Editor crítico
  → Agente 3 — Publicador
```

### Agente 1 — agente_1_investigador.py
Escoge tema no publicado → genera contenido con Llama → guarda en Supabase → notifica en Slack

- Timeout Ollama: 600 segundos
- Detecta rechazos de Llama y reintenta (máx 3 intentos)
- Marca tema como `publicado = TRUE` al guardar

### Agente 2 — agente_2_editor.py
Evalúa el contenido largo contra 5 estándares de calidad usando Llama como crítico

**Estándares:** Integridad, Estructura histórica, Engagement, Credibilidad, Personalidad visual
**Score mínimo:** 7/10
**Intentos:** máximo 3, regenera con instrucciones específicas si falla
**Aprobado:** guarda `aprobado = TRUE` en Supabase y notifica score en Slack

### Agente 3 — agente_3_publicador.py
Toma contenido aprobado → adapta para Facebook → evalúa post → publica → notifica

**Estándares Facebook:** Hook, Longitud, Emojis, Pregunta final, Hashtags, Tono, Integridad
**Score mínimo:** 7/10
**Intentos:** máximo 3

---

## Manejo de errores (utils/errores.py)

Tres tipos de error con comportamiento diferente:

| Tipo | Canal Slack | Comportamiento |
|---|---|---|
| `ErrorInfraestructura` | #infraestructura | Detiene el pipeline completo |
| `ErrorContenido` | #errores | Reintenta hasta MAX_INTENTOS |
| `ErrorNegocio` | #errores | Notifica pero continúa |

**Errores de infraestructura:**
- Token de Facebook expirado (código 190)
- Ollama no responde
- Supabase no disponible

**Verificaciones previas en main.py:**
- `verificar_ollama()` — antes de correr cualquier agente
- `verificar_token_facebook()` — avisa N días antes de expirar

---

## Variables de entorno (.env)

```
# Supabase
SUPABASE_URL=https://[project-id].supabase.co
SUPABASE_KEY=eyJ...

# Slack
SLACK_TOKEN=xoxb-...
SLACK_CHANNEL=#contenido
SLACK_CANAL_ERRORES=#errores
SLACK_CANAL_INFRA=#infraestructura

# Facebook
FB_PAGE_TOKEN=EAA...
FB_PAGE_ID=1159270103934855
FB_TOKEN_EXPIRA=YYYY-MM-DD
FB_TOKEN_AVISO_DIAS=5

# Ollama
OLLAMA_ENDPOINT=http://localhost:11434
```

---

## Cómo correr el pipeline

```bash
cd D:\proyectos\cafe-con-historia

# Pipeline completo (recomendado)
python main.py

# Agentes individuales
python agents/agente_1_investigador.py
python agents/agente_2_editor.py
python agents/agente_3_publicador.py
```

**Scheduler:** tarea programada en Windows Task Scheduler llamada `CafeConHistoria`
**Hora:** 12:00 PM diario
**Configurar:** `.\scripts\setup_scheduler.ps1` (como administrador)

---

## Plataformas configuradas

| Plataforma | Detalles |
|---|---|
| Supabase | Proyecto: cafe-con-historia |
| Slack | Canales: #contenido, #errores, #infraestructura. Bot: CafeConHistoria |
| Facebook | Página: Café con Historia. Page ID: 1159270103934855 |
| Ollama | v0.30.2, modelo: llama3.1:latest (4.9GB) |
| Facebook App | cafe-con-historia en developers.facebook.com |

---

## Token de Facebook

El token expira cada 60 días. Ver guía completa en:
`guia-renovacion-token-facebook.docx`

**Resumen:**
1. Graph API Explorer → User Token → `oauth/access_token?grant_type=fb_exchange_token&...`
2. Con el token largo → `me/accounts` → copiar access_token de Café con Historia
3. Actualizar `FB_PAGE_TOKEN` y `FB_TOKEN_EXPIRA` en `.env`

---

## Hardware actual

| Componente | Especificación |
|---|---|
| CPU | Intel Xeon E5-1620 v2 @ 3.70GHz |
| RAM | 32 GB DDR3 |
| GPU | NVIDIA Quadro K620 (2GB VRAM) — NO compatible con modelos de video IA |
| GPU recomendada | RTX 3060 12GB (~$250 CAD usada) para habilitar Wan2.1 |
| OS | Windows 11 Pro 23H2 |

---

## Tareas pendientes

### Mejoras a los agentes
- [ ] Recolectar métricas de Facebook semanalmente (likes, comentarios, shares)
- [ ] Tabla `metricas` en Supabase — migración 003
- [ ] Ajustar tono del prompt según posts con mayor engagement

### Contenido
- [ ] Ampliar base de datos a 200 temas
- [ ] Agente 0 de noticias recientes via RSS
- [ ] Versión en francés del canal

### Pipeline de video (requiere GPU)
- [ ] Adquirir RTX 3060 12GB
- [ ] Instalar ComfyUI + Wan2.1
- [ ] Integrar video al pipeline
- [ ] Publicar en YouTube Shorts y Facebook

---

## Arquitectura futura

```
Agente 0 (Noticias)     → genera temas desde RSS → Supabase
Agente 1 (Investigador) → genera contenido largo → Slack
Agente 2 (Editor)       → evalúa calidad → aprueba o regenera
Agente 3 (Publicador)   → adapta → evalúa post → publica Facebook
Agente 4 (Video)        → guión + Wan2.1 → YouTube Shorts + Facebook
```

---

## Contexto del desarrollador

- David, IT support en Montreal, originalmente de Colombia
- Background en análisis de datos, SQL, sistemas
- Objetivo: sistema automatizado de contenido que escale sin intervención manual diaria
- El CLAUDE.md debe actualizarse con cada cambio significativo al proyecto