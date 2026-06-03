-- ============================================================
-- Café con Historia — Migración 003
-- Fecha: Junio 2026
-- Descripción: Agregar campos de diversidad a la tabla temas
-- ============================================================
 
ALTER TABLE temas ADD COLUMN tono TEXT;
ALTER TABLE temas ADD COLUMN region TEXT;
ALTER TABLE temas ADD COLUMN epoca TEXT;
 
-- Valores esperados:
-- tono: 'pesado' | 'curioso' | 'reflexivo' | 'inspirador'
-- region: 'america_latina' | 'norteamerica' | 'europa' | 'asia' | 'africa' | 'global'
-- epoca: 'antigua' | 'medieval' | 'moderna' | 'contemporanea' | 'actual'
 