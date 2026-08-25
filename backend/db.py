"""Acceso a PostgreSQL para los casos de triage.

Responsabilidad deliberada: este módulo NO inserta casos nuevos. Esa inserción
la hace el nodo Postgres de n8n directamente (ver PROMPTS.md, decisión Postgres
vs SQLite: elegimos Postgres justamente para que n8n use su nodo nativo en vez
de un hack de Execute Command). Flask (app.py) solo llama a init_db() al
arrancar para garantizar que la tabla exista. El dashboard de Streamlit es
quien lee la lista de pendientes y registra la firma del médico.
"""
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

_PRIORITY_ORDER = """
    CASE color_triage
        WHEN 'Rojo' THEN 1
        WHEN 'Amarillo' THEN 2
        WHEN 'Verde' THEN 3
        ELSE 4
    END
"""


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS triage_cases (
                    id SERIAL PRIMARY KEY,
                    symptoms_text TEXT NOT NULL,
                    color_triage TEXT NOT NULL,
                    diagnostico_presuntivo TEXT,
                    explicacion_feynman TEXT,
                    propuesta_ia TEXT,
                    plan_final TEXT,
                    justificacion_clinica_rag TEXT,
                    contraindicaciones_alertas TEXT,
                    estado TEXT NOT NULL DEFAULT 'Pendiente',
                    attended_by TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    attended_at TIMESTAMPTZ
                );
            """)


def get_pending_cases() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT * FROM triage_cases
                WHERE estado = 'Pendiente'
                ORDER BY {_PRIORITY_ORDER}, created_at ASC;
            """)
            return cur.fetchall()


def get_case(case_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM triage_cases WHERE id = %s;", (case_id,))
            return cur.fetchone()


def sign_case(case_id: int, plan_final: str, attended_by: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE triage_cases
                SET estado = 'Atendido', plan_final = %s, attended_by = %s, attended_at = now()
                WHERE id = %s;
                """,
                (plan_final, attended_by, case_id),
            )
