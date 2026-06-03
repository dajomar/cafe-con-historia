-- ============================================================
-- Café con Historia — Migración 004
-- Fecha: Junio 2026
-- Descripción: Crear tabla de métricas de engagement de Facebook
-- ============================================================
 
CREATE TABLE IF NOT EXISTS metricas (
    id             SERIAL PRIMARY KEY,
    contenido_id   INTEGER REFERENCES contenido(id),
    fb_post_id     TEXT,
    likes          INTEGER DEFAULT 0,
    comentarios    INTEGER DEFAULT 0,
    shares         INTEGER DEFAULT 0,
    alcance        INTEGER DEFAULT 0,
    fecha_consulta TIMESTAMP DEFAULT NOW()
);
 