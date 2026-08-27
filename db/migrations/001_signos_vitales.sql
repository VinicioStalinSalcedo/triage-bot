-- Añade los signos vitales a una base ya creada.
--
-- db/init.sql solo se ejecuta cuando el volumen de PostgreSQL se crea por
-- primera vez, así que una instalación existente no recibe las columnas
-- nuevas. Este script las incorpora sin perder los casos ya registrados.
--
--   docker compose exec -T postgres psql -U triage -d triage \
--     < db/migrations/001_signos_vitales.sql

ALTER TABLE triage_cases
    ADD COLUMN IF NOT EXISTS pa_sistolica            INTEGER,
    ADD COLUMN IF NOT EXISTS pa_diastolica           INTEGER,
    ADD COLUMN IF NOT EXISTS frecuencia_cardiaca     INTEGER,
    ADD COLUMN IF NOT EXISTS frecuencia_respiratoria INTEGER,
    ADD COLUMN IF NOT EXISTS temperatura             NUMERIC(4,1),
    ADD COLUMN IF NOT EXISTS saturacion_oxigeno      INTEGER;
