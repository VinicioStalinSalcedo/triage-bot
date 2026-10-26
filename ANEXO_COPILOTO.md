<style>
/* Estilos de impresión embebidos. Van dentro del documento a propósito: la extensión
   de exportación solo carga docs/pdf.css si el proyecto es la carpeta raíz abierta en
   el editor, y así el PDF sale correcto en cualquier caso. */
body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt;
       line-height: 1.6; color: #1e293b; }
.page-break, div[style*="page-break-after"] { page-break-after: always !important;
       break-after: page !important; height: 0; }
h1 { font-size: 20pt; color: #0f172a; letter-spacing: -0.02em; margin-bottom: 0.3em; }
h2 { font-size: 15pt; color: #0f172a; border-bottom: 1.5px solid #cbd5e1;
     padding-bottom: 0.25em; margin-top: 1.6em; page-break-after: avoid; }
h3 { font-size: 12pt; color: #0f766e; margin-top: 1.3em; page-break-after: avoid; }
h4 { font-size: 10.5pt; color: #334155; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: 1em 0;
        page-break-inside: avoid; }
th { background: #f1f5f9; color: #0f172a; font-weight: 600; text-align: left;
     border: 1px solid #cbd5e1; padding: 6px 9px; }
td { border: 1px solid #e2e8f0; padding: 6px 9px; vertical-align: top; }
tr:nth-child(even) td { background: #f8fafc; }
pre { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 10px 12px;
      font-size: 8pt; line-height: 1.35; page-break-inside: avoid; white-space: pre;
      overflow-x: hidden; }
code { font-family: "Cascadia Code", Consolas, monospace; font-size: 9pt; background: #f1f5f9;
       padding: 1px 4px; border-radius: 3px; }
pre code { background: none; padding: 0; font-size: inherit; }
blockquote { border-left: 3px solid #0f766e; background: #f0fdfa; margin: 1em 0;
             padding: 0.6em 1em; color: #334155; }
div[align="center"] h1 { font-size: 24pt; margin-top: 0; }
div[align="center"] h3 { font-size: 12pt; font-weight: 400; color: #475569; }
hr { border: none; border-top: 1px solid #e2e8f0; margin: 1.6em 0; }
strong { color: #0f172a; }
</style>

<div align="center">
<br><br><br>

# Anexo de Trazabilidad del Copiloto de IA

### Bitácora de hitos, bloqueos técnicos y contraste crítico

<br><br>
<br><br>
<br><br>

**Proyecto Final** — Sistema de Triaje Clínico Preliminar

<br><br><br><br>

Artificial Intelligence Essentials (AIE) — Summer Camp 2026

<br><br><br><br><br>

Escuela Politécnica Nacional
Célula de Ciberseguridad CyberMinds

<br><br><br><br><br><br>

**Autor:** `Vinicio Stalin Salcedo Peña`

<br><br><br>

</div>

<div class="page-break" style="page-break-after: always;"></div>

## 1. Propósito

Registro auditable del uso de asistentes de IA durante el desarrollo. Recoge los hitos que alteraron el diseño y consigna, en cada uno, qué propuso el modelo, qué se aceptó, qué se rechazó y por qué.

## 2. Herramientas

| Herramienta | Modelo | Rol |
| --- | --- | --- |
| Claude Code (CLI) | Claude Sonnet 5 · Claude Opus 5 | Copiloto de desarrollo: arquitectura y codificación |
| Asistente conversacional | NotebookLM | Ideación inicial del concepto, lluvia de ideas y corrección de rumbo |
| Groq Cloud | `openai/gpt-oss-120b` · `openai/gpt-oss-20b` | **Componente del producto**: inferencia de triaje y reescritura clínica |
| Hugging Face | `paraphrase-multilingual-MiniLM-L12-v2` | **Componente del producto**: vectorización local del corpus |

Los dos últimos no asistieron al desarrollo: son infraestructura del producto entregado.

## 3. Método

Tres reglas fijadas al inicio y sostenidas durante todo el proyecto:

1. **Código redactado por el asistente, ejecución a cargo del autor.** Instalación, despliegue y verificación se ejecutaron manualmente, para conservar el control del entorno y la comprensión de cada paso.
2. **Ninguna recomendación se aceptó sin contraste** contra el enunciado del proyecto, la documentación oficial de cada tecnología o el comportamiento observado del sistema.
3. **Toda decisión no evidente se registró con su justificación**, no solo con su resultado.

<div class="page-break" style="page-break-after: always;"></div>

## 4. Hitos

### Hito 1 — Corpus documental y corrección de rumbo

El asistente propuso curar cinco Guías de Práctica Clínica del Ministerio de Salud Pública, y las seleccionó de modo que superaran los tres casos de prueba que él mismo había propuesto.

**Contraste crítico.** Al solicitar una revisión adversarial del planteamiento completo emergió el defecto: **el corpus se había elegido para que pasaran las pruebas, no para que funcionara el producto.** Hipertensión, diabetes en el embarazo, trastornos hipertensivos del embarazo, acné y recién nacido no cubren los motivos de consulta de un dispensario universitario —dolor abdominal, fiebre, tos, trauma menor, cefalea—. Ante una entrada realista, la recuperación devolvía el fragmento menos lejano con falsa confianza.

**Resolución.** Se añadieron protocolos de atención prehospitalaria y, más adelante, cuatro guías que cubren huecos reales del caso de uso: neumonía adquirida en la comunidad, depresión, dolor lumbar y diabetes mellitus. El corpus quedó en **diez guías y 5.933 fragmentos**.

**Aprendizaje.** El sesgo no estaba en el corpus sino en el método: evaluar un sistema contra pruebas diseñadas por quien lo construyó mide consistencia interna, no utilidad.

### Hito 2 — Recuperación semántica en español

La primera prueba devolvió la guía de **acné** para una consulta de crisis hipertensiva. El paciente decía "veo puntos negros" y la guía dermatológica describe comedones abiertos con esas mismas palabras: coincidencia léxica literal, no semántica.

**Causa raíz.** El modelo de embeddings inicial está entrenado mayormente en inglés y se le pedía vectorizar texto clínico en español.

**Resolución.** Se sustituyó por un modelo explícitamente multilingüe de la misma dimensionalidad, lo que obligó a reconstruir la base vectorial completa: los vectores previos no son comparables aunque compartan tamaño.

**Aprendizaje.** Una arquitectura RAG correcta con un modelo de embeddings inadecuado para el idioma no falla de forma visible. Recupera con confianza el documento equivocado, que es peor que no recuperar nada.

### Hito 3 — Estabilidad del árbol de dependencias

Las versiones que el asistente fijó para la familia de un framework de orquestación de modelos correspondían a su conocimiento y no al estado real del repositorio de paquetes: el resolutor devolvió un conflicto irresoluble. Liberarlas tampoco funcionó, porque con cinco paquetes sin restricción entró en retroceso exhaustivo y la construcción superó los cuarenta minutos sin converger.

**Contraste crítico.** En lugar de seguir ajustando números se auditó qué aportaba realmente el framework: cargar PDFs, partir texto, vectorizar, persistir y buscar, e invocar al proveedor. Las cinco operaciones ya estaban cubiertas por las librerías base del proyecto.

**Resolución.** Se eliminó el framework por completo. El proyecto pasó de catorce dependencias a nueve, con construcción reproducible y cada operación visible en el código.

### Hito 4 — Auditoría preventiva del código generado

Se solicitó de forma explícita una revisión crítica del código recién escrito, **antes de ejecutarlo**. Aparecieron tres defectos reales que aún no se habían manifestado.

| Defecto | Consecuencia evitada |
| --- | --- |
| Retroceso del cursor en el fragmentador de texto | Bucle infinito ante fragmentos con un único espacio temprano, situación que se produce con tablas o texto mal extraído de PDF |
| Ausencia de inserción por lotes en la base vectorial | Fallo al superar el límite por operación, tras haber consumido el tiempo completo de vectorización |
| Caché del modelo de embeddings no persistida | Descarga repetida de 470 MB en cada ejecución efímera de contenedor |

Los dos primeros solo se habrían manifestado al ampliar el corpus, y el segundo se materializó después: con 5.933 fragmentos se superó efectivamente el límite por operación. La inserción por lotes resultó necesaria en la práctica, no solo en teoría.

### Hito 5 — Brecha de vocabulario entre paciente y normativa

**El hallazgo más importante del proyecto.** Ante el relato *"se me hincharon la cara y las manos de un día para otro, me duele muchísimo la cabeza y veo lucecitas"* en una gestante —preeclampsia con signos de gravedad de manual— el sistema diagnosticó **envenenamiento por picadura de escorpión**, con plan de adrenalina, antihistamínicos y corticoides, para una picadura que el paciente nunca mencionó.

**Diagnóstico.** Los cuatro fragmentos recuperados procedían de la sección de mordeduras y envenenamientos. Ni uno de la guía obstétrica, teniéndola indexada. Se buscaba con las palabras coloquiales del paciente contra texto técnico: sin la pista léxica de la presión arterial, "hinchazón de cara, cefalea y alteración visual" se parece más al lenguaje de los envenenamientos que al de la guía obstétrica, que habla de proteinuria y cifras tensionales.

**Agravante de diseño propio.** La instrucción de anclaje —*fundaméntate en el contexto recuperado y cítalo*— hizo que el modelo confiara en el contexto equivocado por encima de su propio conocimiento clínico. Obedeció al pie de la letra: el defecto era del diseño, no del modelo.

**Resolución en dos frentes.** Una etapa previa que traduce el relato a terminología clínica, buscando con **ambas** formulaciones y fusionando por menor distancia. Y un endurecimiento del prompt que instruye que el contexto puede ser irrelevante y debe descartarse cuando mencione causas que el paciente no refirió.

**Aprendizaje.** Un sistema RAG necesita instrucciones no solo para **usar** el contexto, sino para **rechazarlo**. Anclar sin permitir el rechazo convierte un fallo de recuperación en un diagnóstico erróneo con apariencia de fundamento.

### Hito 6 — Fallo silencioso de la reescritura clínica

Aplicados los arreglos anteriores, el caso obstétrico devolvió el diagnóstico correcto. Al revisar la salida completa se comprobó que lo había hecho **por una sola de las dos defensas**: la consulta clínica venía vacía y las fuentes seguían siendo las de envenenamientos. Lo que corrigió el caso fue el endurecimiento del prompt; la recuperación en dos etapas no había funcionado ni una vez.

**Causa raíz.** El modelo razona antes de emitir contenido y consume tokens de salida en ello. El límite de 150 tokens puesto a la llamada de reescritura se agotaba durante ese razonamiento y la respuesta llegaba vacía. La llamada principal no tenía tope, por eso nunca mostró el problema.

**Resolución.** Se retiró el límite y se añadió registro tanto de la excepción como del contenido vacío. La degradación con gracia se mantiene, pero deja rastro.

**Aprendizaje.** Un mecanismo de respaldo silencioso convirtió el fallo total de un componente en algo indistinguible del éxito. La degradación controlada solo es útil si además es observable.

### Hito 7 — Persistencia, y una orientación equivocada

El asistente propuso SQLite. Se rechazó por dos condiciones concretas del diseño: backend y frontend son procesos separados con acceso concurrente, escenario para el que el bloqueo por archivo no está pensado; y el orquestador dispone de nodo nativo de PostgreSQL, mientras que con SQLite habría que recurrir a un script externo.

Con la escritura ya fuera de la aplicación, la columna que almacena las fuentes recuperadas —de tipo JSONB— rechazaba tanto la cadena como el arreglo suelto. **La orientación del asistente fue incorrecta en ambos intentos.** Se resolvió por experimentación directa, envolviendo el arreglo en un objeto antes de serializarlo y adaptando la lectura del panel a esa forma.

### Hito 8 — Umbral de relevancia y conjunto de evaluación

El filtro de relevancia se calibró midiendo la distribución real de distancias, no estimando. Con seis guías los grupos se separaban limpiamente y el umbral operaba como detector de cobertura. Al llegar a diez guías **esa separación desaparece**: los rangos de casos con y sin respaldo documental se solapan y ningún corte los separa sin error. La causa es la densificación del corpus, que acerca un resfriado a la guía de neumonía y una ansiedad situacional a la de depresión.

**Decisión.** El umbral deja de ser filtro de relevancia clínica y pasa a ser filtro de dominio: descarta lo manifiestamente ajeno y admite lo clínicamente plausible, delegando el juicio fino al modelo, que ya había demostrado ejercerlo al rechazar el contexto de envenenamientos.

**Conjunto de evaluación.** Se detectó que los once casos de prueba iniciales **reproducían el mismo sesgo criticado en el corpus**: diseñados alrededor de las guías disponibles y con una distribución dominada por emergencias. Se reconstruyeron **veintiocho casos** elegidos por lo que llega a un dispensario, con distribución realista, diez sin respaldo documental esperado, dos controles y pares de contraste que miden discriminación fina —misma queja, gravedad opuesta—.

**Métrica.** La herramienta separa deliberadamente **sobre-triaje de sub-triaje**. Promediarlos en una sola cifra de exactitud oculta el único que compromete la seguridad del paciente.

### Hito 9 — Signos vitales y la regresión que introdujeron

Los sobre-triajes de la evaluación compartían causa: el modelo escalaba por falta de información objetiva. Se incorporaron signos vitales opcionales.

**Restricción impuesta desde el inicio.** Las constantes debían llegar al modelo como dato del prompt y **nunca como condicional en código**. Un `if sistolica > 180: return "Rojo"` habría sido precisamente la lógica rígida que el proyecto argumenta descartar. La validación implementada comprueba únicamente que el valor sea numérico.

**Resultado inesperado.** La evaluación con constantes **empeoró**: aparecieron tres sub-triajes inexistentes hasta entonces —diabetes gestacional, debut diabético y episodio depresivo—, los tres clasificados como Verde.

**Contraste crítico.** El asistente identificó como causa una instrucción que él mismo había redactado: *"unas constantes normales reducen la incertidumbre y no obligan a escalar"*, que el modelo generalizó a "constantes normales implica cuadro leve". Se verificó el razonamiento antes de aceptarlo y resultó clínicamente sólido: una depresión con deterioro funcional, un debut diabético o una diabetes gestacional cursan con presión y pulso normales y siguen exigiendo valoración pronta.

**Resolución.** Se acotó el alcance de la inferencia autorizada: unas constantes normales descartan *inestabilidad hemodinámica y únicamente eso*, enumerando de forma explícita los dominios cuya severidad no se refleja en constantes —metabólico, endocrino, psiquiátrico, neurológico focal e infeccioso localizado—.

**Aprendizaje.** Aportar más información al modelo no mejora el resultado por sí solo: hay que delimitar qué inferencias autoriza esa información. Una instrucción bienintencionada pero amplia introdujo un fallo de seguridad que la versión anterior no presentaba.

### Hito 10 — Inestabilidad de la recuperación en casos frontera

La evaluación mostró que un caso —diabetes gestacional con constantes normales— alternaba de color entre ejecuciones **a temperatura cero**. Repetido seis veces devolvió Amarillo en cuatro ocasiones y Verde en dos.

**Hipótesis inicial, refutada.** La explicación propuesta fue que la variación provenía de usar un modelo menor en la reescritura. Se comprobó ejecutando ambas etapas sobre el modelo mayor: **la alternancia persistió**. El modelo no era la variable.

**Causa localizada.** La etapa de reescritura genera una formulación distinta en cada invocación, y esa formulación determina qué guía domina el contexto recuperado:

| Ejecución | Sesgo de la consulta | Guías recuperadas | Color |
| --- | --- | --- | --- |
| 1 | terminología obstétrica | 4/4 de la guía de diabetes en el embarazo | **Amarillo** |
| 2 | terminología de diabetes general | 3/4 de la guía de diabetes del adulto | **Verde** |

Con la guía obstétrica el modelo trata el cuadro como gestacional y lo prioriza; con la de adulto no gestante lo trata como control ambulatorio. **La inestabilidad no está en el clasificador sino en la recuperación, y se propaga hacia adelante.**

**Alcance.** Los dos casos que alternaron son aquellos en que dos guías del corpus resultan legítimamente aplicables; un cuadro inequívoco devolvió el mismo resultado en todas las repeticiones. La comprobación se limitó a tres casos, de modo que el alcance exacto no queda caracterizado y se declara como tal.

**Corrección identificada, no implementada.** Fijar una semilla en la llamada de reescritura, para que la consulta generada y con ella la recuperación sean reproducibles. Es una medida de determinismo y no una regla clínica, de modo que no introduce lógica condicional sobre la gravedad.

**Aprendizaje.** En una arquitectura por etapas, el síntoma aparece al final y la causa puede estar dos pasos atrás. La hipótesis intuitiva —culpar al clasificador— era la equivocada, y solo un experimento controlado la descartó.

### Hito 11 — Resistencia a inyección de prompts

Se sometió el sistema a una instrucción diseñada para subvertir su rol clínico y obtener la prescripción de un opioide sin indicación.

**La ruta crítica resistió por completo.** No declaró sano al paciente ni prescribió el medicamento. Interpretó la solicitud como posible búsqueda de opioides, indicó expresamente que no debía administrarse y derivó a valoración especializada. Aunque recuperó fragmentos sobre morfina, explicó que no eran aplicables al no haber dolor referido.

**Vulnerabilidad secundaria.** La etapa de reescritura sí fue desviada: devolvió una negativa que se usó como consulta de búsqueda, contaminando las fuentes. Se corrigió validando esa salida —si viene vacía, es demasiado corta o contiene marcas de rechazo, se descarta—. No decide nada clínico: es saneamiento de una consulta inservible.

**Decisión razonada.** Se **descartó** implementar un filtro de sanitización independiente. El diseño del prompt y la validación estricta de esquema contuvieron el ataque en el punto que importa. La decisión se tomó sobre lo observado y se consigna como omisión deliberada, no como olvido.

<div class="page-break" style="page-break-after: always;"></div>

## 5. Resultado de la validación

Configuración final: modelo mayor para la clasificación, modelo menor para la reescritura, temperatura cero y signos vitales activos.

| Métrica | Sin signos vitales | Configuración final |
| --- | --- | --- |
| Coincidencia exacta | 85 % | **96 %** (25/26) |
| Sobre-triaje | 15 % | **4 %** (1/26) |
| **Sub-triaje** | 0 % | **0 %** |
| Seguridad clínica | 100 % | **100 %** |

El único desacierto es una lumbalgia con déficit neurológico clasificada por exceso de gravedad, clínicamente defendible. La matriz de confusión es triangular superior: ningún caso quedó por debajo de su gravedad de referencia, que es la propiedad de seguridad que el diseño persigue.

## 6. Valoración crítica del copiloto

**Aportes efectivos.** Aceleración sustancial en la redacción de código de infraestructura, diagnóstico de causa raíz a partir de registros de error, y detección de defectos latentes cuando se le pidió revisión adversarial explícita del código antes de ejecutarlo.

**Limitaciones observadas.** Cuatro son destacables por reproducibles:

*Afirmaciones sobre ecosistemas externos sin verificar.* Las versiones de dependencias propuestas correspondían al conocimiento del modelo y no al estado real del repositorio de paquetes. Costó dos ciclos de construcción fallidos.

*Sesgo de confirmación sobre su propio diseño.* El corpus documental se seleccionó de modo que superara las pruebas que el propio asistente había propuesto. El defecto solo emergió al solicitar una revisión crítica del planteamiento completo.

*Indicaciones incorrectas sobre herramientas de terceros.* El mapeo del campo JSONB en el orquestador fue erróneo y se resolvió por experimentación directa.

*Hipótesis plausibles pero no comprobadas.* La explicación ofrecida para la alternancia de color en casos frontera atribuía la causa al modelo empleado. El experimento controlado la refutó y localizó la causa dos etapas antes.

**Conclusión.** El asistente resultó eficaz generando código y analizando causa raíz sobre evidencia concreta, y menos fiable afirmando sobre el estado de ecosistemas externos y evaluando críticamente sus propias propuestas. El método productivo fue tratar cada recomendación como hipótesis a verificar —contra documentación oficial o contra el comportamiento observado— y solicitar revisión adversarial en los puntos de decisión, en lugar de aceptar la validación de lo ya construido.
