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
| Generación de imágenes | OpenAI gpt-image-1 |
| Text-to-Speech | OpenAI tts-1-hd (voz: onyx) |
| Ensamblaje de video | ffmpeg |
| Notificaciones | Slack API |
| Publicación texto | Facebook Graph API v25.0 — endpoint /feed y /photos |
| Publicación video | Facebook Graph API v25.0 — endpoint /video_reels |
| Lenguaje | Python 3.11 |
| Entorno | HP Z420 / Windows 11 Pro |
| Control de versiones | GitHub — github.com/dajomar/cafe-con-historia |

---

## Estructura del proyecto

```
cafe-con-historia/
├── agents/                            # Pipeline de texto (posts Facebook)
│   ├── agente_0_noticias.py           # Lee RSS y genera temas inspirados en noticias
│   ├── agente_1_investigador.py       # Selecciona tema con diversidad y genera contenido
│   ├── agente_2_editor.py             # Verifica hechos + evalúa calidad editorial
│   ├── agente_3_publicador.py         # Adapta para Facebook, evalúa post y publica
│   └── agente_imagen.py               # Genera imagen con gpt-image-1 para el post
├── agents_video/                      # Pipeline de video (Reels Facebook) — independiente
│   ├── agente_v1_guion.py             # Genera guión + divide en 6-8 escenas con Llama
│   ├── agente_v2_imagenes.py          # Genera imagen por escena con gpt-image-1
│   ├── agente_v3_video.py             # TTS + ensambla video con ffmpeg (Ken Burns)
│   └── agente_v4_publica.py           # Publica como Reel en Facebook
├── database/
│   ├── 001_crear_tablas_iniciales.sql
│   ├── 002_agregar_campos_calidad.sql
│   ├── 003_agregar_campos_diversidad.sql
│   ├── 004_crear_tabla_metricas.sql
│   ├── 005_agregar_campos_noticia.sql
│   ├── 006_agregar_campos_imagen.sql   # imagen_url, imagen_prompt en contenido
│   └── 007_agregar_tabla_videos.sql    # tabla videos para el pipeline de video
├── output/
│   └── videos/                        # Videos generados (gitignore)
│       └── {tema_id}/
│           ├── escena_01.png
│           ├── audio_escena_01.mp3
│           ├── clip_01.mp4
│           └── video_final.mp4
├── assets/
│   └── musica.mp3                     # Música de fondo para videos (opcional)
├── images/                            # Imágenes para posts de texto (gitignore)
├── scripts/
│   ├── insertar_temas.py
│   ├── clasificar_temas.py            # Clasifica temas con Llama (tono, region, epoca)
│   └── setup_scheduler.ps1            # Configura Windows Task Scheduler
├── utils/
│   └── errores.py                     # Manejo centralizado de errores
├── main.py                            # Orquestador del pipeline de texto
├── main_video.py                      # Orquestador del pipeline de video
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
imagen_url          TEXT          -- ruta local de imagen generada con gpt-image-1
imagen_prompt       TEXT          -- prompt completo enviado a gpt-image-1
```

### Tabla: videos (pipeline de video independiente)
```sql
id                SERIAL PRIMARY KEY
tema_id           INTEGER REFERENCES temas(id)
guion             TEXT                      -- guión completo de 45-60 segundos
escenas           JSONB                     -- [{numero, narracion, descripcion_visual, imagen_path, audio_path}]
video_path        TEXT                      -- ruta local del video_final.mp4
video_publicado   BOOLEAN DEFAULT FALSE
fb_reel_id        TEXT                      -- ID del Reel en Facebook
fecha_generacion  TIMESTAMP DEFAULT NOW()
fecha_publicacion TIMESTAMP
score_calidad     INTEGER
modelo_imagen     TEXT DEFAULT 'gpt-image-1'
modelo_voz        TEXT DEFAULT 'tts-1-hd'
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

## Pipeline de texto (posts Facebook)

### Flujo completo
```
main.py
  → verificar_infraestructura() — Ollama + token Facebook
  → Agente 0 — Noticias (lunes, miércoles, viernes)
  → Agente 1 — Investigador
  → Agente 2 — Editor crítico
  → Agente Imagen — gpt-image-1 (no fatal: si falla, publica sin imagen)
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

### Agente Imagen — agente_imagen.py
Genera imagen con gpt-image-1 para acompañar el post de texto.
- Llama traduce el contexto del tema a prompt visual en inglés
- Estilo visual según tono (Opción D — Híbrido):
  - `pesado` → fotorrealista dramático
  - `curioso` → ilustración histórica colorida
  - `reflexivo` → cinematic suave
  - `inspirador` → luminoso y épico
- Tamaño: 1024x1536 (portrait), quality: high
- Guarda imagen en `images/` y registra ruta en tabla `contenido`
- Es un paso **no fatal**: si falla, Agente 3 publica sin imagen

### Agente 3 — agente_3_publicador.py
Adapta el contenido aprobado para Facebook (400-600 palabras, emojis, hook, hashtags).
Evalúa el post antes de publicar (score mínimo 7/10, máx 3 intentos).
Si hay imagen disponible: publica via `/photos` endpoint con imagen adjunta.
Si no hay imagen: publica via `/feed` como post de solo texto.
Detecta errores de infraestructura de Facebook (token expirado, permisos) y los separa de errores de contenido.

---

## Pipeline de video (Reels Facebook)

### Flujo completo
```
main_video.py  — orquestador INDEPENDIENTE, no importa nada de main.py
  → verificar_infraestructura() — OPENAI_API_KEY + Ollama
  → Agente V1 — Guión
  → Agente V2 — Imágenes
  → Agente V3 — Video (TTS + ffmpeg)
  → Agente V4 — Publicador Reels
```

### Agente V1 — agente_v1_guion.py
- Selecciona tema no usado en tabla `videos` (cualquier tema, sin filtro de publicado)
- Genera guión narrativo de 45-60 segundos con Llama
- Divide en 6-8 escenas con narración y descripción visual por escena
- Guarda en tabla `videos` con estructura JSONB de escenas

### Agente V2 — agente_v2_imagenes.py
- Toma video de tabla `videos` con guión pero sin video_path
- Por cada escena: Llama genera prompt en inglés → gpt-image-1 genera imagen (1024x1536)
- Guarda imágenes en `output/videos/{tema_id}/escena_NN.png`
- Actualiza campo `escenas` en Supabase después de cada imagen (tolerante a fallos parciales)

### Agente V3 — agente_v3_video.py
- Requiere ffmpeg instalado en el sistema
- Por cada escena: OpenAI TTS (tts-1-hd, voz onyx) genera audio → ffmpeg crea clip con Ken Burns
- 4 variantes de Ken Burns según número de escena (zoom-in centro, top-left, top-right, bottom-center)
- Ensambla: clips → video_sin_audio.mp4 | audios → narracion.mp3
- Mix final: video + narración + música de fondo (assets/musica.mp3 a 15% volumen, opcional)
- Output: `output/videos/{tema_id}/video_final.mp4` — MP4 1080x1920, 30fps

### Agente V4 — agente_v4_publica.py
- Publica el MP4 como Reel en Facebook via Graph API v25.0
- Flujo en 3 pasos: start (iniciar sesión) → upload (subir binario) → finish (publicar)
- Caption: reutiliza `contenido_facebook` del pipeline de texto si existe, o genera con Llama
- Actualiza `video_publicado=True` y `fb_reel_id` en Supabase

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

**Verificaciones previas en main_video.py:**
- `OPENAI_API_KEY` definido en .env
- `verificar_ollama()` — Llama necesario para guión y prompts visuales

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
OLLAMA_MODEL=llama3.1:8b

# OpenAI (imágenes + TTS)
OPENAI_API_KEY=sk-...
OPENAI_IMAGE_MODEL=gpt-image-1       # o gpt-image-1.5, gpt-image-2
OPENAI_TTS_MODEL=tts-1-hd            # modelo TTS
OPENAI_TTS_VOZ=onyx                  # onyx | nova | echo | alloy | fable | shimmer

# Video (opcional)
MUSICA_PATH=/ruta/a/musica.mp3       # si no se define, usa assets/musica.mp3
```

---

## Cómo correr los pipelines

```bash
# Conectarse a la PC desde el Mac
ssh david@192.168.2.66
D:
cd proyectos\cafe-con-historia
git pull

# Pipeline de texto (posts)
python main.py

# Pipeline de video (Reels)
python main_video.py

# Agentes individuales — texto
python agents/agente_0_noticias.py
python agents/agente_1_investigador.py
python agents/agente_2_editor.py
python agents/agente_imagen.py
python agents/agente_3_publicador.py

# Agentes individuales — video
python agents_video/agente_v1_guion.py
python agents_video/agente_v2_imagenes.py
python agents_video/agente_v3_video.py
python agents_video/agente_v4_publica.py
```

**Schedulers:** Windows Task Scheduler
- `CafeConHistoria` → `python main.py` — 12:00 PM diario
- `CafeConHistoriaVideo` → `python main_video.py` — frecuencia a definir (recomendado: 3x semana)

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
ssh david@192.168.2.66

# Sin contraseña (SSH keys)
ssh-keygen -t ed25519 -C "cafe-con-historia"
ssh-copy-id david@192.168.2.66
```

VS Code Remote SSH: instala extensión "Remote - SSH" → conectar a `david@192.168.2.66`

---

## Plataformas configuradas

| Plataforma | Detalles |
|---|---|
| Supabase | Proyecto: cafe-con-historia |
| Slack | Canales: #contenido, #errores, #infraestructura. Bot: CafeConHistoria |
| Facebook | Página: Café con Historia. Page ID: 1159270103934855 |
| Ollama | v0.30.2, modelo: llama3.1:latest (4.9GB) |
| OpenAI | Modelos: gpt-image-1 (imágenes), tts-1-hd (voz) |
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

### Pipeline de texto
- [ ] Agente 4 — Distribuidor en grupos de Facebook (latinos en Canadá/USA, geopolítica, historia)
- [ ] Agente 5 — Engagement: responde comentarios con Llama
- [ ] Agente 6 — Analista semanal: reporte de métricas y recomendaciones
- [ ] Human-in-the-loop via Slack buttons para revision_manual
- [ ] Memoria de engagement: leer métricas de Facebook y ajustar selección de temas
- [ ] Agente 0: agregar más fuentes RSS

### Pipeline de video
- [ ] Probar pipeline completo en la PC y validar calidad del video
- [ ] Configurar scheduler separado para main_video.py
- [ ] Agregar transiciones crossfade entre escenas en Agente V3
- [ ] Optimizar velocidad de ensamblaje (ffmpeg preset ultrafast para pruebas)
- [ ] Agregar música de fondo (assets/musica.mp3)

### Contenido
- [ ] Ampliar base de datos a 200 temas
- [ ] Versión en francés del canal

---

## Arquitectura completa

```
Pipeline de texto (daily 12pm):
  Agente 0 (Noticias L/M/V) → temas de actualidad → Supabase
  Agente 1 (Investigador)   → prioriza noticias → diversidad 7 días → genera contenido
  Agente 2 (Editor)         → verifica hechos → evalúa calidad → aprueba o detiene
  Agente Imagen             → gpt-image-1 → imagen para el post (no fatal)
  Agente 3 (Publicador)     → adapta Facebook → evalúa post → publica con/sin imagen

Pipeline de video (independiente):
  Agente V1 (Guión)         → tema sin video → guión 45-60s → 6-8 escenas
  Agente V2 (Imágenes)      → gpt-image-1 → 1 imagen por escena (1024x1536)
  Agente V3 (Video)         → TTS onyx → Ken Burns → ffmpeg → MP4 1080x1920
  Agente V4 (Publicador)    → Facebook Reels API → Reel publicado

Pendiente:
  Agente 4 (Distribuidor)   → comparte en grupos relevantes
  Agente 5 (Engagement)     → responde comentarios con Llama
  Agente 6 (Analista)       → reporte semanal → ajusta estrategia
```

---

## Notas de desarrollo

- Siempre crear archivo de migración SQL antes de ejecutar cambios en Supabase
- Migraciones van en `database/` con número secuencial (001, 002, ...)
- El `.env` nunca va al repositorio — está en `.gitignore`
- Actualizar este CLAUDE.md con cada cambio significativo al proyecto
- Commits descriptivos: `feat:`, `fix:`, `refactor:`, `migracion:`
- Los dos pipelines son completamente independientes — no comparten módulos entre sí
- `utils/errores.py` es el único módulo compartido entre ambos pipelines
