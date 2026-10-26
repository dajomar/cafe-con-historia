# Café con Historia — Contexto del proyecto

## Visión
Canal educativo con el enfoque: **"La historia explica el presente"**.
Contenido diario que conecta acontecimientos históricos con situaciones del mundo actual, dirigido a hispanohablantes — especialmente latinos en Canadá/USA y profesionales de 30-45 años que leen noticias y quieren contexto histórico.

No es un canal de datos curiosos — usa la historia como lente para entender por qué el mundo de hoy funciona como funciona.

**Eslogan:** "Donde el pasado cobra vida"

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
| Control de versiones | GitHub — github.com/dajomar/cafe-con-historia |

---

## Estructura del proyecto

```
cafe-con-historia/
├── agents/
│   ├── agente_0_noticias.py       # Lee RSS y genera temas históricos inspirados en noticias
│   ├── agente_1_investigador.py   # Selecciona tema con diversidad y genera contenido
│   ├── agente_2_editor.py         # Verifica hechos + evalúa calidad editorial
│   └── agente_3_publicador.py     # Adapta para Facebook, evalúa post y publica
├── database/
│   └── migrations/
│       ├── 001_crear_tablas_iniciales.sql
│       ├── 002_agregar_campos_calidad.sql
│       ├── 003_agregar_campos_diversidad.sql
│       ├── 004_crear_tabla_metricas.sql
│       └── 005_agregar_campos_noticia.sql
├── scripts/
│   ├── insertar_temas.py
│   ├── clasificar_temas.py        # Clasifica temas con Llama (tono, region, epoca)
│   └── setup_scheduler.ps1        # Configura Windows Task Scheduler
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

**Proyecto:** cafe-con-historia | **Región:** Americas | **Page ID Facebook:** 1159270103934855

### Tabla: temas
```sql
id                INTEGER PRIMARY KEY
pregunta          TEXT NOT NULL
categoria         TEXT NOT NULL
publicado         BOOLEAN DEFAULT FALSE
fecha_publicacion TIMESTAMP
plataforma        TEXT
tono              TEXT          -- pesado | curioso | reflexivo | inspirador
region            TEXT          -- america_latina | norteamerica | europa | asia | africa | global
epoca             TEXT          -- antigua | medieval | moderna | contemporanea | actual
fuente            TEXT DEFAULT 'historico'  -- historico | noticia
url_noticia       TEXT
fecha_noticia     DATE
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

### Tabla: metricas (lista para usar cuando haya datos)
```sql
id             INTEGER PRIMARY KEY
contenido_id   INTEGER REFERENCES contenido(id)
fb_post_id     TEXT
likes          INTEGER DEFAULT 0
comentarios    INTEGER DEFAULT 0
shares         INTEGER DEFAULT 0
alcance        INTEGER DEFAULT 0
fecha_consulta TIMESTAMP DEFAULT NOW()
```

---

## Pipeline de agentes

### Flujo completo
```
main.py
  → verificar_infraestructura() — Ollama + token Facebook
  → Agente 0 — Noticias (lunes, miércoles, viernes)
  → Agente 1 — Investigador
  → Agente 2 — Editor crítico
  → Agente 3 — Publicador
```

### Agente 0 — agente_0_noticias.py
Corre lunes, miércoles y viernes. Lee RSS de BBC Mundo, Deutsche Welle y France 24.
Selecciona la noticia más relevante para Café con Historia y genera una pregunta histórica inspirada en ella.
Guarda en Supabase con `fuente='noticia'` y `fecha_noticia=hoy`.
Si falla, el pipeline continúa con temas históricos normales.

### Agente 1 — agente_1_investigador.py
Lógica de selección de tema con dos prioridades:
1. Si hay tema de `fuente='noticia'` de hoy → lo usa primero
2. Si no → aplica lógica de diversidad de 7 días (2+ dimensiones diferentes de tono/región/época)

Genera contenido con Llama usando el tono, región y época del tema.
Detecta rechazos de Llama y reintenta (máx 3 intentos).
Notifica en Slack con indicador de diversidad: 🟢 alta | 🟡 baja | 🔴 sin diversidad | 📰 actualidad

### Agente 2 — agente_2_editor.py
Dos fases separadas:

**Fase 1 — Verificación factual** (historiador escéptico):
- Busca errores graves y verificables: fechas completamente incorrectas, nombres equivocados, eventos que nunca ocurrieron
- NO marca simplificaciones narrativas ni matices académicos como errores
- Veredictos: `aprobado` → continúa | `revision_manual` → detiene y notifica en #errores | `rechazado` → detiene

**Fase 2 — Evaluación editorial** (solo si pasa verificación):
- Evalúa 5 criterios: integridad, estructura histórica, engagement, credibilidad, personalidad visual
- Score mínimo: 7/10 | Máximo 3 intentos | Regenera con instrucciones específicas si falla

### Agente 3 — agente_3_publicador.py
Adapta el contenido aprobado para Facebook (máx 150 palabras, emojis, hook, hashtags).
Evalúa el post antes de publicar (score mínimo 7/10, máx 3 intentos).
Detecta errores de infraestructura de Facebook (token expirado, permisos) y los separa de errores de contenido.

---

## Manejo de errores (utils/errores.py)

| Tipo | Canal Slack | Comportamiento |
|---|---|---|
| `ErrorInfraestructura` | #infraestructura | Detiene el pipeline completo |
| `ErrorContenido` | #errores | Reintenta hasta MAX_INTENTOS |
| `ErrorNegocio` | #errores | Notifica pero continúa |

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

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_TTS_MODEL=tts-1-hd
OPENAI_TTS_VOZ=onyx

# Flags de funcionalidades
GENERAR_IMAGENES=true   # true | false — activa/desactiva el agente de imágenes
```

---

## Cómo correr el pipeline

```bash
# Conectarse a la PC desde el Mac
ssh usuario@TU_IP_LOCAL
D:
cd proyectos\cafe-con-historia
git pull

# Pipeline completo
python main.py

# Agentes individuales
python agents/agente_0_noticias.py
python agents/agente_1_investigador.py
python agents/agente_2_editor.py
python agents/agente_3_publicador.py
```

**Scheduler:** Windows Task Scheduler — tarea `CafeConHistoria`
**Hora:** 12:00 PM diario
**Agente 0:** corre automáticamente lunes, miércoles y viernes

---

## Token de Facebook

Expira cada 60 días. Ver guía completa en `guia-renovacion-token-facebook.docx`.

Proceso rápido:
1. Graph API Explorer → User Token con permisos: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`
2. Intercambiar: `oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=TOKEN`
3. Con el token largo → `me/accounts` → copiar `access_token` de Café con Historia
4. Actualizar `FB_PAGE_TOKEN` y `FB_TOKEN_EXPIRA` en `.env`

---

## Conexión SSH Mac → PC

Ver guía completa en `guia-ssh-mac-pc.docx`.

```bash
# Conectar
ssh usuario@TU_IP_LOCAL

# Sin contraseña (SSH keys)
ssh-keygen -t ed25519 -C "cafe-con-historia"
ssh-copy-id usuario@TU_IP_LOCAL
```

VS Code Remote SSH: instala extensión "Remote - SSH" → conectar a `usuario@TU_IP_LOCAL`

---

## Plataformas configuradas

| Plataforma | Detalles |
|---|---|
| Supabase | Proyecto: cafe-con-historia |
| Slack | Canales: #contenido, #errores, #infraestructura. Bot: CafeConHistoria |
| Facebook | Página: Café con Historia. Page ID: 1159270103934855 |
| Ollama | v0.30.2, modelo: llama3.1:latest (4.9GB) |
| Facebook App | cafe-con-historia en developers.facebook.com |
| GitHub | github.com/dajomar/cafe-con-historia |

---

## Hardware

| Componente | Especificación |
|---|---|
| CPU | Intel Xeon E5-1620 v2 @ 3.70GHz |
| RAM | 32 GB DDR3 |
| GPU actual | NVIDIA Quadro K620 (2GB VRAM) — NO compatible con modelos de video IA |
| GPU pendiente | RTX 3060 12GB (~$250 CAD usada en Kijiji Montreal) |
| OS | Windows 11 Pro 23H2 |
| Mac | MacBook con M1 — usado para trabajar remotamente via SSH |

---

## Tareas pendientes

### Agentes por construir
- [ ] Agente 4 — Distribuidor en grupos de Facebook (latinos en Canadá/USA, geopolítica, historia)
- [ ] Agente 5 — Engagement: responde comentarios con Llama
- [ ] Agente 6 — Analista semanal: reporte de métricas y recomendaciones
- [ ] Human-in-the-loop via Slack buttons para revision_manual

### Mejoras a agentes existentes
- [ ] Memoria de engagement: leer métricas de Facebook y ajustar selección de temas
- [ ] Agente 0: agregar más fuentes RSS

### Pipeline de video (requiere GPU)
- [ ] Adquirir RTX 3060 12GB
- [ ] Instalar ComfyUI + Wan2.1
- [ ] Integrar generación de video al pipeline

### Contenido
- [ ] Ampliar base de datos a 200 temas
- [ ] Versión en francés del canal

---

## Arquitectura completa planeada

```
Agente 0 (Noticias L/M/V) → temas inspirados en actualidad → Supabase
Agente 1 (Investigador)   → prioriza noticias → diversidad 7 días → genera contenido
Agente 2 (Editor)         → verifica hechos → evalúa calidad → aprueba o detiene
Agente 3 (Publicador)     → adapta Facebook → evalúa post → publica
Agente 4 (Distribuidor)   → comparte en grupos relevantes
Agente 5 (Engagement)     → responde comentarios con Llama
Agente 6 (Analista)       → reporte semanal → ajusta estrategia
```

---

## Notas de desarrollo

- Siempre crear archivo de migración SQL antes de ejecutar cambios en Supabase
- Migraciones van en `database/migrations/` con número secuencial
- El `.env` nunca va al repositorio — está en `.gitignore`
- Actualizar este CLAUDE.md con cada cambio significativo al proyecto
- Commits descriptivos: `feat:`, `fix:`, `refactor:`, `migracion:`