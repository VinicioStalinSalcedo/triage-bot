# Triaje Clínico Preliminar Asistido por IA

**Proyecto final — Artificial Intelligence Essentials (AIE), Summer Camp 2026**
Escuela Politécnica Nacional · Célula de Ciberseguridad CyberMinds · Quito, Ecuador

Sistema de triaje preliminar que recibe síntomas en lenguaje natural, los clasifica por
urgencia mediante inferencia semántica anclada en Guías de Práctica Clínica oficiales del
Ministerio de Salud Pública del Ecuador, y entrega al médico un pre-diagnóstico con una
propuesta de plan que este edita y firma antes de que llegue al paciente.

---

## 1. Definición del problema

### Contexto

En un dispensario de atención primaria, el orden de atención lo determina, en la práctica,
el orden de llegada. Quien decide la prioridad es personal administrativo o de enfermería
que debe interpretar, en segundos y sin historia clínica previa, un relato desestructurado:
*"me duele la cabeza y veo lucecitas"*.

El problema no es la falta de criterio médico, sino que ese criterio se aplica **después**
de la cola, no antes. Una gestante con signos de preeclampsia y un paciente con acné
esperan el mismo turno.

### Impacto

El error de triaje es asimétrico. Sobrestimar la gravedad de un caso leve cuesta tiempo de
consulta. Subestimar una emergencia —una preeclampsia, un síndrome coronario, un ictus—
cuesta ventanas terapéuticas que no se recuperan. Esa asimetría es una decisión de diseño
explícita de este sistema (ver §5).

### Por qué requiere IA y no un formulario con reglas

Un formulario de casillas obliga al paciente a autodiagnosticarse antes de ser atendido:
solo puede marcar los síntomas que alguien anticipó. Un árbol de decisiones sobre palabras
clave falla ante la variabilidad del lenguaje real — "veo lucecitas", "veo puntitos",
"se me nubla la vista" y "veo como flashes" describen el mismo escotoma.

La clasificación aquí exige **comprensión semántica** de un texto no estructurado y su
contraste contra normativa clínica. En este proyecto ninguna condición de código decide la
gravedad: el color de triaje lo infiere el modelo de lenguaje a partir del relato y del
contexto normativo recuperado.

### Alcance declarado

Es un **apoyo a la decisión**, no un sistema de diagnóstico autónomo. Ninguna salida llega
al paciente sin que un profesional la revise, edite y firme. El paciente recibe únicamente
su enrutamiento —a dónde ir y con qué urgencia—, nunca el diagnóstico presuntivo ni la
receta borrador.

---

## 2. Qué hace el sistema

1. El paciente describe lo que siente en sus propias palabras y, opcionalmente, aporta
   edad, sexo y estado gestacional.
2. El relato se traduce a terminología clínica y se buscan por similitud semántica los
   fragmentos pertinentes de las guías del MSP.
3. Un LLM clasifica la urgencia en **Rojo / Amarillo / Verde**, emite un diagnóstico
   presuntivo, una explicación en lenguaje llano y una propuesta de conducta, todo con
   salida JSON estricta.
4. El caso se persiste y el paciente recibe su instrucción de enrutamiento.
5. El médico de turno ve la cola ordenada por gravedad, revisa el análisis completo con
   sus fuentes, **edita** la propuesta y **firma**.

| Color | Significado | Qué produce la IA |
|---|---|---|
| 🔴 Rojo | Emergencia crítica | Plan de estabilización inmediata y derivación |
| 🟡 Amarillo | Urgencia intermedia | Plan de estabilización y derivación |
| 🟢 Verde | Atención primaria simple | Borrador de receta con dosificación |

---

## 3. Arquitectura

```
Paciente (Streamlit) ──► n8n Webhook ──► HTTP Request ──► Flask /api/triage
                                                               │
                                          ┌────────────────────┴────────────────────┐
                                          │  1. Reescritura a lenguaje clínico      │
                                          │  2. Búsqueda vectorial (ChromaDB)       │
                                          │  3. Inferencia + JSON estricto (Groq)   │
                                          └────────────────────┬────────────────────┘
                                                               │
                                       n8n nodo Postgres ──► INSERT triage_cases
                                                               │
                                       n8n Switch ──► respuesta según color
                                                               │
                     Médico (Streamlit) ◄── PostgreSQL ── edita ── firma ── "Atendido"
```

El detalle completo, con el flujo de datos campo por campo, está en
[ARCHITECTURE.md](ARCHITECTURE.md).

### Stack

| Componente | Tecnología | Rol |
|---|---|---|
| Orquestación | n8n 2.35 | Webhook, llamada al backend, persistencia, enrutamiento |
| Inferencia | Groq · `openai/gpt-oss-120b` | Clasificación y generación con JSON mode |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` | Vectorización local del corpus y las consultas |
| Base vectorial | ChromaDB (coseno) | Recuperación semántica sobre 3.664 fragmentos |
| Backend | Flask | API de inferencia, sin estado |
| Base de datos | PostgreSQL 16 | Historial y estados de atención |
| Interfaz | Streamlit | Vista del paciente y panel del médico |
| Entorno | Docker Compose | Cuatro servicios aislados |

---

## 4. Corpus documental

Seis Guías de Práctica Clínica oficiales del MSP del Ecuador, descargadas de
`salud.gob.ec` y `aplicaciones.msp.gob.ec`:

| Guía | Fragmentos |
|---|---|
| Protocolos de Atención Prehospitalaria para Emergencias Médicas | 1.257 |
| Trastornos Hipertensivos del Embarazo | 624 |
| Recién Nacido con Dificultad para Respirar | 586 |
| Hipertensión Arterial (2019) | 473 |
| Diagnóstico y Tratamiento del Acné | 420 |
| Diabetes en el Embarazo | 304 |

### Limitaciones conocidas del corpus

El índice público de guías del MSP se concentra en salud materno-neonatal, enfermedades
crónicas y emergencias prehospitalarias. **No cubre buena parte de la consulta ambulatoria
frecuente** —trauma musculoesquelético menor, infecciones urinarias no gestacionales,
patología respiratoria alta.

Ante esos casos el sistema **no inventa respaldo normativo**: el filtro de relevancia
descarta los fragmentos que no superan el umbral, la respuesta declara explícitamente que
ninguna guía era aplicable, y el panel del médico muestra una advertencia para que revise
con mayor atención. Es una limitación declarada, no un defecto oculto.

---

## 5. Decisiones de diseño

**El paciente no recibe el diagnóstico.** Solo su enrutamiento. El diagnóstico presuntivo
y la receta borrador viajan al panel del médico. Evita que una hipótesis no validada llegue
como si fuera un dictamen.

**Flask no escribe en la base de datos.** El backend es un motor de inferencia sin estado;
quien persiste es el nodo Postgres de n8n. La orquestación y la persistencia viven en la
capa de orquestación, no dentro del modelo.

**Ante la duda, se escala.** El prompt instruye preferir el color más grave cuando la
información es insuficiente. Esto produce sobre-triaje deliberado —una sospecha de
apendicitis sin signos vitales se clasifica Rojo— y se acepta por la asimetría de costos
descrita en §1.

**Recuperación en dos etapas.** El relato del paciente se traduce a terminología clínica
antes de buscar, y se consulta con ambas versiones. Sin este paso, *"se me hinchó la cara
y veo lucecitas"* recuperaba la sección de envenenamientos en lugar de la de preeclampsia
(ver `PROMPTS.md`).

**El umbral de relevancia está calibrado, no elegido.** El valor de `MAX_DISTANCE` sale de
medir la distribución real de distancias del corpus, separando aciertos de ruido.

**El Switch determinista no contradice la prohibición de if/else.** La *clasificación* es
inferencia probabilística del LLM. Actuar de forma determinista sobre una decisión ya
inferida es ingeniería correcta: lo prohibido es que la condición decida la gravedad.

---

## 6. Puesta en marcha

### Requisitos
Docker y Docker Compose. Una clave de [Groq Cloud](https://console.groq.com) (gratuita).

### Pasos

```bash
cp .env.example .env          # y coloque su GROQ_API_KEY
docker compose build
docker compose up -d
docker compose run --rm backend python rag/ingest.py    # construye la base vectorial
```

La ingesta tarda unos minutos: descarga el modelo de embeddings y vectoriza el corpus.

Después, importe `n8n/triage_flow.json` en n8n (`http://localhost:5678`), configure la
credencial de PostgreSQL (host `postgres`, puerto `5432`, base `triage`) y publique el
workflow.

| Servicio | URL |
|---|---|
| Interfaz (paciente y médico) | http://localhost:8501 |
| API de triaje | http://localhost:5000/api/triage |
| n8n | http://localhost:5678 |
| PostgreSQL | localhost:5433 |

### Verificación

```bash
curl -s -X POST http://localhost:5000/api/triage -H "Content-Type: application/json" \
  -d '{"symptoms":"Se me hincharon la cara y las manos, me duele muchísimo la cabeza y veo lucecitas","edad":28,"sexo":"femenino","gestante":true}'
```

Debe devolver `color_triage: "Rojo"` con diagnóstico de preeclampsia y fuentes de la guía
de trastornos hipertensivos del embarazo.

---

## 7. Estructura del repositorio

```
├── rag/
│   ├── config.py           Modelo, colección, métrica y umbral de relevancia
│   ├── ingest.py           Extracción, fragmentación, embeddings y persistencia
│   └── query_rag.py        Búsqueda semántica con filtro de relevancia
├── backend/
│   ├── app.py              API Flask: reescritura, recuperación e inferencia
│   ├── prompts.py          Prompts de reescritura clínica y de triaje
│   └── db.py               Lectura de la cola y registro de la firma médica
├── frontend/dashboard.py   Vista del paciente y panel del médico
├── db/init.sql             Esquema de PostgreSQL
├── n8n/triage_flow.json    Workflow de orquestación exportado
├── data/msp_guides/        Corpus documental del MSP
├── ARCHITECTURE.md         Diagrama y flujo de datos detallado
└── PROMPTS.md              Trazabilidad de copiloto: decisiones y depuraciones
```

---

## 8. Advertencia

Prototipo académico. No constituye consejo médico ni sustituye la valoración de un
profesional de la salud. Los datos utilizados en las pruebas son ficticios.
