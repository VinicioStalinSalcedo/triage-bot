-- Schema del historial de triage.
--
-- Se ejecuta automáticamente la primera vez que arranca el contenedor de
-- Postgres (docker-entrypoint-initdb.d). Vive aquí, y no en el código de
-- Flask, porque quien inserta los casos es el nodo Postgres de n8n: si el
-- schema dependiera de que Flask haya arrancado, levantar solo postgres+n8n
-- fallaría con "relation does not exist".

CREATE TABLE IF NOT EXISTS triage_cases (
    id                         SERIAL PRIMARY KEY,

    -- Entrada del paciente
    symptoms_text              TEXT        NOT NULL,
    edad                       INTEGER,
    sexo                       TEXT,
    gestante                   BOOLEAN,

    -- Signos vitales tomados en recepción. Todos opcionales: el triaje debe
    -- funcionar sin ellos. No se validan contra rangos aquí ni en el código:
    -- su interpretación clínica corresponde al modelo, contrastándolos con los
    -- criterios de las guías recuperadas.
    pa_sistolica               INTEGER,
    pa_diastolica              INTEGER,
    frecuencia_cardiaca        INTEGER,
    frecuencia_respiratoria    INTEGER,
    temperatura                NUMERIC(4,1),
    saturacion_oxigeno         INTEGER,

    -- Salida de la IA
    color_triage               TEXT        NOT NULL CHECK (color_triage IN ('Rojo', 'Amarillo', 'Verde')),
    diagnostico_presuntivo     TEXT,
    explicacion_feynman        TEXT,
    propuesta_ia               TEXT,
    justificacion_clinica_rag  TEXT,
    contraindicaciones_alertas TEXT,
    -- Fragmentos de guía MSP que sustentaron el triage, para auditoría.
    fuentes_rag                JSONB,

    -- Decisión del médico (human-in-the-loop)
    plan_final                 TEXT,
    estado                     TEXT        NOT NULL DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Atendido')),
    attended_by                TEXT,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    attended_at                TIMESTAMPTZ
);

-- El panel del médico consulta siempre "pendientes ordenados por gravedad".
CREATE INDEX IF NOT EXISTS idx_triage_cases_pendientes
    ON triage_cases (estado, created_at);
