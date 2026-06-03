-- ============================================================
-- Café con Historia — Migración 002
-- Fecha: Junio 2026
-- Descripción: Agregar campos de calidad y aprobación al contenido
-- ============================================================

ALTER TABLE contenido ADD COLUMN score_calidad INTEGER;
ALTER TABLE contenido ADD COLUMN intentos_generacion INTEGER DEFAULT 1;
ALTER TABLE contenido ADD COLUMN aprobado BOOLEAN DEFAULT FALSE;