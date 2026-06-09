-- Migración 007: Crear tabla videos para el pipeline de video independiente
-- Ejecutar en Supabase SQL Editor

CREATE TABLE IF NOT EXISTS videos (
    id                SERIAL PRIMARY KEY,
    tema_id           INTEGER REFERENCES temas(id),
    guion             TEXT,
    escenas           JSONB,
    video_path        TEXT,
    video_publicado   BOOLEAN DEFAULT FALSE,
    fb_reel_id        TEXT,
    fecha_generacion  TIMESTAMP DEFAULT NOW(),
    fecha_publicacion TIMESTAMP,
    score_calidad     INTEGER,
    modelo_imagen     TEXT DEFAULT 'gpt-image-1',
    modelo_voz        TEXT DEFAULT 'tts-1-hd'
);

COMMENT ON TABLE videos IS 'Pipeline de video independiente — no modifica el pipeline de texto';
COMMENT ON COLUMN videos.escenas IS 'Array JSON con estructura: [{numero, narracion, descripcion_visual, imagen_path, audio_path}]';
