-- ============================================================
-- Café con Historia — Migración 001
-- Fecha: Junio 2026
-- Descripción: Creación de tablas iniciales
-- ============================================================

-- Tabla de temas
-- Contiene las preguntas históricas que los agentes van a responder
CREATE TABLE IF NOT EXISTS temas (
    id                SERIAL PRIMARY KEY,
    pregunta          TEXT NOT NULL,
    categoria         TEXT NOT NULL,
    publicado         BOOLEAN DEFAULT FALSE,
    fecha_publicacion TIMESTAMP,
    plataforma        TEXT
);

-- Tabla de contenido generado
-- Guarda el contenido que cada agente genera para cada tema
CREATE TABLE IF NOT EXISTS contenido (
    id                  SERIAL PRIMARY KEY,
    tema_id             INTEGER REFERENCES temas(id),
    contenido_slack     TEXT,
    contenido_facebook  TEXT,
    fecha_generacion    TIMESTAMP DEFAULT NOW(),
    modelo_usado        TEXT DEFAULT 'llama3.1'
);
