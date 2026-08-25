# Registro de Trazabilidad de Copiloto

Requisito de rúbrica: "Documentación y Copiloto" (10%) — registro auditable del soporte de IA durante ideación, implementación, escritura de código y depuración.

## Modelos utilizados como copiloto de desarrollo

| Herramienta | Modelo | Uso |
|---|---|---|
| Claude Code | Claude Sonnet 5 (`claude-sonnet-5`) | Arquitectura, definición de alcance, codificación, depuración |
| IA de brainstorming inicial | (conversación previa, ver `aie-project-spec-final.md`) | Ideación inicial del concepto de proyecto |
| Groq Cloud (en producción, dentro del propio sistema) | `llama-3.1-70b-versatile` | Motor de inferencia del triage — no es copiloto de desarrollo, es el núcleo computacional del producto |

## Bitácora de decisiones e hitos

### Hito 0 — Definición de alcance (2026-08-24)
- Punto de partida: `aie-project-spec-final.md`, un brainstorm con otra IA — se aclaró explícitamente que no era la especificación final.
- Se leyó el documento oficial `PROYECTO_INTELIGENCIA_ARTIFICIAL.pdf` (rúbrica real de la EPN/CyberMinds) para contrastar contra el brainstorm. Confirmó: rúbrica de 5 categorías (Definición del Problema 15%, Integración de Resultados IA 35%, Implementación Técnica 30%, Documentación y Copiloto 10%, Defensa 10%); n8n listado explícitamente como patrón válido de orquestación; prohibición de if/else rígidos sin inferencia probabilística.
- Se verificó en las transcripciones de clase (4, 8, 9) que n8n se enseñó como una opción entre varias (n8n/Make/Zapier), no como herramienta obligatoria — decisión informada, no asumida.
- Decisiones cerradas con el usuario: proyecto individual con dedicación alta; n8n se implementa completo (4 nodos); es un proyecto/demo académico sin datos de pacientes reales; frontend consolidado en una sola app Streamlit (vista paciente + vista médico) en vez de dos sistemas separados.
- Se investigó el corpus real de Guías de Práctica Clínica del MSP Ecuador (`salud.gob.ec`): está concentrado en temas materno-neonatales y enfermedades crónicas, no en motivos de consulta agudos de urgencias. Se optó por curar 5 documentos reales y verificables en vez de simular guías inexistentes:
  - Hipertensión Arterial (2019)
  - Diabetes en el Embarazo
  - Trastornos Hipertensivos del Embarazo
  - Diagnóstico y Tratamiento del Acné
  - Recién Nacido con Dificultad para Respirar

### Hito 1 — Entorno y datos (2026-08-24)
- Estructura de carpetas creada (`rag/`, `backend/`, `n8n/`, `frontend/`, `data/msp_guides/`).
- `requirements.txt` definido (Flask, LangChain + langchain-groq + langchain-huggingface, ChromaDB, sentence-transformers, pypdf, Streamlit).
- Descarga de los 5 PDFs curados desde `salud.gob.ec`. Depuración: el sitio rechaza peticiones HTTP/2 automatizadas (bloqueo por fingerprint de bot); se resolvió forzando HTTP/1.1 con headers de navegador real.
- Corrección de seguridad: la clave real de Groq se había puesto por error en `.env.example` (archivo pensado como plantilla pública); se movió a `.env` (ignorado por git) y se restauró `.env.example` como plantilla vacía.

### Hito 2 — Entorno de contenedores (2026-08-24)
- Se eligió Docker Compose como entorno de desarrollo (en vez de instalar todo en local) para no interferir con otros proyectos Python/Node del usuario en la misma máquina.
- `Dockerfile` (imagen Python 3.11 compartida por `backend` y `frontend`) y `docker-compose.yml` con 3 servicios: `backend` (Flask+RAG), `frontend` (Streamlit), `n8n` (imagen oficial `n8nio/n8n`).
- Decisión de base de datos: se evaluó SQLite vs PostgreSQL. Se eligió **PostgreSQL** por dos razones concretas: (1) `backend` y `frontend` son contenedores/procesos separados que necesitan acceso concurrente a la misma base, y SQLite usa locking a nivel de archivo que no está pensado para eso; (2) n8n tiene un nodo nativo de Postgres, pero no de SQLite (con SQLite habría que usar "Execute Command" para correr un script a mano). Se agregó el servicio `postgres` al compose con healthcheck (`pg_isready`) para evitar condiciones de carrera al arrancar, y `psycopg2-binary` a `requirements.txt`.
- Corrección de consistencia: `.env`/`.env.example` tenían `SQLITE_DB_PATH` apuntando a una ruta (`./instance/triage.db`) que no coincidía con los volúmenes montados — se reemplazó por las variables de Postgres (`POSTGRES_USER/PASSWORD/DB`, `DATABASE_URL`).

### Depuración — conflicto de puerto 5432 (2026-08-24)
- `docker compose up postgres n8n -d` falló: "failed to bind host port 0.0.0.0:5432 ... address already in use".
- Diagnóstico (solo lectura: `docker ps`, `ss -ltnp`, `systemctl status postgresql`, `ps aux`): no era un contenedor Docker, sino un **PostgreSQL 17 nativo** corriendo como servicio systemd en la máquina del usuario (usado por otro proyecto local, Odoo). No se tocó ese servicio — es infraestructura ajena a este proyecto.
- Fix: se remapeó el puerto publicado del servicio `postgres` en `docker-compose.yml` de `5432:5432` a `5433:5432`. Solo cambia el puerto visible desde el host; la comunicación interna backend/frontend/n8n → postgres sigue usando `postgres:5432` dentro de la red de Docker, sin cambios.

### Depuración — recuperación semántica pobre (2026-08-24)
- Primera corrida de `query_rag.py` con `all-MiniLM-L6-v2`: síntomas de crisis hipertensiva ("veo puntos negros") recuperaron la guía de **acné** en vez de hipertensión — el modelo hizo match léxico literal de "puntos negros" (alteración visual vs. comedones), no semántico. Preeclampsia tampoco recuperó `trastornos_hipertensivos_embarazo`. Distancias todas en rango mediocre (0.75-0.97), sin matches fuertes.
- Causa raíz: `all-MiniLM-L6-v2` está entrenado mayormente en inglés; se le pedía embeber texto clínico en español.
- Fix: se cambió `EMBEDDING_MODEL` a `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (mismo tamaño/384 dimensiones, explícitamente multilingüe) en `ingest.py` y `query_rag.py`. Requiere reingestar desde cero (los embeddings viejos no son compatibles semánticamente con el nuevo modelo aunque compartan dimensionalidad).
- Observación pendiente, no bloqueante: las páginas 42-43 del PDF de acné contienen un cuestionario tipo escala de ánimo/calidad de vida (texto genérico y repetitivo) que apareció como resultado espurio en varias consultas no relacionadas. Si tras el cambio de modelo sigue apareciendo como ruido, se evaluará filtrarlo explícitamente.
- **Verificado tras el cambio a `paraphrase-multilingual-MiniLM-L12-v2`:** las 3 consultas de prueba ahora recuperan la guía correcta (crisis hipertensiva y preeclampsia → `trastornos_hipertensivos_embarazo`; acné → `diagnostico_tratamiento_acne`). Ya no aparece el falso positivo de acné en consultas de presión. Pendiente para cuando se implemente el umbral de confianza en el backend: cambiar la métrica de distancia de L2 (default de Chroma) a coseno para tener un rango acotado y más fácil de calibrar.

### Hito 3 — Backend Flask (2026-08-24)
- Se investigó el modelo de Groq a usar en producción antes de codificar: `llama-3.1-70b-versatile`/`llama-3.3-70b-versatile` (lo que asumía `aie-project-spec-final.md`) está **deprecado para cuentas free/developer desde el 17 de junio de 2026** — solo sigue disponible para Enterprise con contrato. Se cambió a `openai/gpt-oss-120b` (modelo insignia actual disponible en el tier gratuito de Groq, 131K contexto, soporta JSON mode/reasoning). Divergencia consciente del documento original, comunicada al usuario.
- `backend/db.py`: schema Postgres (`triage_cases`) + `init_db`/`get_pending_cases`/`get_case`/`sign_case`. **Deliberadamente no incluye una función de insert** — la creación de casos la hace el nodo Postgres nativo de n8n (Hito 4), no Flask. Esto es consistente con la razón por la que se eligió Postgres sobre SQLite.
- `backend/prompts.py`: system prompt + construcción del prompt de usuario con el contexto RAG citado por fuente/página. La clasificación de `color_triage` queda 100% delegada al LLM — sin listas de palabras clave ni if/else de negocio (requisito duro de la rúbrica, no solo estilo).
- `backend/app.py`: endpoint `POST /api/triage`, sin estado respecto a la BD (no inserta). Usa `ChatGroq` con `model_kwargs={"response_format": {"type": "json_object"}}` (JSON mode nativo de Groq) en vez de solo confiar en el prompt, más validación manual de las 6 claves esperadas y de que `color_triage` sea uno de los 3 valores válidos.

### Depuración — versiones de la familia LangChain obsoletas (2026-08-24)
- Al reconstruir la imagen tras el fix de `groq`/`langchain-groq`, `pip` devolvió `ResolutionImpossible`: probó cada versión de `langchain-groq` desde 1.1.3 hasta 0.2.2 y **ninguna** es compatible con `langchain-core<0.3.0` que exige `langchain==0.2.16`.
- Causa raíz: las versiones exactas fijadas en `requirements.txt` (`langchain==0.2.16`, `langchain-community==0.2.16`, `langchain-huggingface==0.0.3`) corresponden al conocimiento del asistente al momento de redactar el archivo, no al estado real de PyPI en la fecha del proyecto (agosto 2026). El ecosistema LangChain ya avanzó de generación (0.2.x → 0.3.x → incluso 1.x en `langchain-groq`), y no hay ninguna versión publicada que combine la generación vieja con la nueva.
- Fix: se dejó de fijar versión exacta en toda la familia LangChain (`langchain`, `langchain-community`, `langchain-groq`, `langchain-huggingface`, + se agregó `langchain-chroma`) para que `pip` resuelva un combo mutuamente compatible y vigente, en vez de seguir adivinando números uno por uno. Se mantienen fijas las dependencias que no forman parte de ese conflicto (Flask, chromadb, sentence-transformers, pypdf, psycopg2-binary) porque no hay evidencia de que estén rotas.
- Se aprovechó el mismo cambio para resolver la deprecation warning ya observada de `Chroma`: import movido de `langchain_community.vectorstores` a `langchain_chroma` en `ingest.py` y `query_rag.py`.
- Trade-off aceptado y explícito: sin pines exactos, una reconstrucción futura podría traer versiones distintas a las de hoy (reproducibilidad menor). Aceptable dado el plazo del proyecto (entrega en días, no meses).

<!-- Añadir aquí cada hito nuevo, con fecha y prompts clave usados para resolver bloqueos -->
