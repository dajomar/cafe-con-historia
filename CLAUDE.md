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

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Base de datos | Supabase (PostgreSQL) |
| Modelo de lenguaje | Llama 3.1 via Ollama (local) |
| Notificaciones | Slack API |
| Publicación | Facebook Graph API |
| Lenguaje | Python 3.11 |
| Entorno | HP Z420 / Windows 11 Pro |

---

## Estructura del proyecto

```
cafe-con-historia/
├── agents/
│   ├── agente_1_slack.py       # Genera contenido y envía a Slack
│   └── agente_2_facebook.py    # Adapta y publica en Facebook
├── database/
│   └── schema.sql              # Estructura de tablas en Supabase
├── config/
│   └── prompts.py              # Prompts de los agentes
├── utils/
│   └── helpers.py              # Funciones reutilizables
├── .env                        # Credenciales (nunca al repo)
├── .gitignore
├── requirements.txt
├── CLAUDE.md                   # Este archivo
└── README.md
```

---

## Base de datos (Supabase)

**Proyecto:** cafe-con-historia | **Región:** Americas

### Tabla: temas
```sql
id               INTEGER PRIMARY KEY
pregunta         TEXT NOT NULL
categoria        TEXT NOT NULL
publicado        BOOLEAN DEFAULT FALSE
fecha_publicacion TIMESTAMP
plataforma       TEXT
```

### Tabla: contenido
```sql
id                 INTEGER PRIMARY KEY
tema_id            INTEGER REFERENCES temas(id)
contenido_slack    TEXT
contenido_facebook TEXT
fecha_generacion   TIMESTAMP DEFAULT NOW()
modelo_usado       TEXT DEFAULT 'llama3.1'
```

### Categorías
- Geopolitica
- Instituciones
- Cultura
- Economia
- Ciencia
- America Latina

---

## Agentes implementados

### Agente 1 — agente_1_slack.py
**Función:** Escoge tema no publicado → genera contenido largo con Llama → envía a Slack → marca como publicado en Supabase

**Flujo:**
1. Consulta Supabase: `SELECT * FROM temas WHERE publicado = FALSE`
2. Escoge uno aleatoriamente
3. Llama a Ollama con prompt de divulgador histórico
4. Envía a canal #contenido en Slack
5. Guarda en tabla `contenido`
6. Marca tema como `publicado = TRUE`

**Timeout de Ollama:** 600 segundos (CPU lento en hardware actual)

### Agente 2 — agente_2_facebook.py
**Función:** Toma último contenido de Supabase → adapta para Facebook con emojis → publica en página → envía resumen a Slack

**Flujo:**
1. Consulta último registro en tabla `contenido`
2. Llama a Ollama para adaptar a formato Facebook (máx 150 palabras, emojis, hook impactante)
3. Publica via Facebook Graph API v25.0
4. Envía resumen a Slack con Post ID
5. Guarda `contenido_facebook` en Supabase

---

## Variables de entorno (.env)

```
SUPABASE_URL=https://[project-id].supabase.co
SUPABASE_KEY=eyJ...
SLACK_TOKEN=xoxb-...
SLACK_CHANNEL=#contenido
FB_PAGE_TOKEN=EAA...
FB_PAGE_ID=1159270103934855
```

---

## Cómo correr los agentes

```bash
cd D:\proyectos\cafe-con-historia

# Instalar dependencias
pip install supabase python-dotenv slack-sdk requests

# Agente 1
python agents/agente_1_slack.py

# Agente 2
python agents/agente_2_facebook.py
```

---

## Plataformas configuradas

| Plataforma | Detalles |
|---|---|
| Supabase | Proyecto: cafe-con-historia |
| Slack | Canal: #contenido, Bot: CafeConHistoria |
| Facebook | Página: Café con Historia, Page ID: 1159270103934855 |
| Ollama | v0.30.2, modelo: llama3.1:latest (4.9GB), endpoint: http://localhost:11434 |
| Facebook App | cafe-con-historia en developers.facebook.com |

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
- [ ] Evaluar calidad del contenido antes de publicar (Llama como crítico, score mínimo 7/10)
- [ ] Regenerar si no pasa evaluación (máximo 3 intentos)
- [ ] Recolectar métricas de Facebook semanalmente
- [ ] Tabla `metricas` en Supabase
- [ ] Ajustar tono del prompt según engagement

### Automatización
- [ ] Programar Agente 1 a las 12:00 PM diario (Windows Task Scheduler)
- [ ] Programar Agente 2 a las 12:30 PM diario
- [ ] Manejo de errores con notificaciones a Slack

### Pipeline de video (requiere GPU)
- [ ] Adquirir RTX 3060 12GB
- [ ] Instalar ComfyUI + Wan2.1
- [ ] Integrar video al pipeline
- [ ] Publicar en YouTube Shorts y Facebook

### Contenido
- [ ] Ampliar base de datos a 200 temas
- [ ] Agente 0 de noticias recientes via RSS
- [ ] Versión en francés del canal

---

## Arquitectura futura

```
Agente 0 (Noticias)    → genera temas desde RSS → Supabase
Agente 1 (Investigador) → genera contenido largo → Slack
Agente 2 (Facebook)    → adapta y publica → métricas → Slack
Agente 3 (Video)       → guión + Wan2.1 → YouTube Shorts + Facebook
```

---

## Contexto del desarrollador

- David trabaja en IT support en Montreal, originalmente de Colombia
- Background en análisis de datos, SQL, sistemas — relevante para diseño de base de datos
- Objetivo: construir sistema automatizado de contenido que escale sin intervención manual diaria
- Prioridad actual: tener los dos agentes corriendo automáticamente y la página con actividad inicial