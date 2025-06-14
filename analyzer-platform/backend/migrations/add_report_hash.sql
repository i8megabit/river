-- Migration: Add report_hash field to system_reports table
-- Date: 2024-12-27
-- Description: Добавление поля report_hash для предотвращения дублирования отчетов

BEGIN;

-- Добавляем поле report_hash в таблицу system_reports
ALTER TABLE system_reports 
ADD COLUMN IF NOT EXISTS report_hash VARCHAR(64);

-- Обновляем существующие записи, генерируя временные хеши на основе hostname и created_at
UPDATE system_reports 
SET report_hash = SUBSTR(MD5(hostname || COALESCE(created_at::text, '')), 1, 16)
WHERE report_hash IS NULL;

-- Добавляем ограничение NOT NULL после заполнения данных
ALTER TABLE system_reports 
ALTER COLUMN report_hash SET NOT NULL;

-- Создаем уникальный индекс для report_hash
CREATE UNIQUE INDEX IF NOT EXISTS idx_system_reports_report_hash 
ON system_reports(report_hash);

-- Создаем составной индекс для быстрого поиска по hostname и report_hash
CREATE INDEX IF NOT EXISTS idx_system_reports_hostname_hash 
ON system_reports(hostname, report_hash);

COMMIT; 