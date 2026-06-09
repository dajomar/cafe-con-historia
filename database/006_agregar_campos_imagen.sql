-- Migración 006: Agregar campos de imagen generada con DALL-E 3
-- Ejecutar en Supabase SQL Editor

ALTER TABLE contenido ADD COLUMN imagen_url    TEXT;
ALTER TABLE contenido ADD COLUMN imagen_prompt TEXT;

COMMENT ON COLUMN contenido.imagen_url    IS 'Ruta local de la imagen generada con DALL-E 3';
COMMENT ON COLUMN contenido.imagen_prompt IS 'Prompt completo enviado a DALL-E 3 (en inglés)';
