# Disciplina

Los seminarios llevan a los estudiantes a un estándar de conducta e integridad académica, y
les importa profundamente el _proceso debido_: una sanción debe ser proporcionada,
consistente y constante. The **Discipline** module gives you a catalog of
reasons and sanctions, an **advisory progressive-discipline matrix** that
suggests the right action by how many times something has happened, and a clean
trail from "an instructor noticed something" to "the student was dismissed and
cannot re-enroll." Nada se fuerza automáticamente excepto una única bandera explícita
desdeñable, cada otra decisión permanece en manos humanas.

## Descripción general

El módulo tiene **tres bloques de construcción**, además de un flujo opcional de reporte de portal de instructor
:

```
Razón Disciplinaria — el catálogo "lo que pasó" (plagio, ausencia, …)
        Lleva una matriz de acciones recomendadas por el número de ocurrencia
Acción Disciplinaria: el catálogo "qué hacemos al respecto" (advertencia … dismissal)

Incidente Disciplinario — un registro de un evento, con la(s) acción(es) aplicadas
```

- Una **razón** es _por qué_ — una categoría reutilizable como _Plagiarismo_ o _Ausencia
  sin excusa_. Cada razón lleva una **matriz consultiva**: "1ª vez → Verbal
  Advertencia, 2ª → Advertencia escrita, 3ª y más allá → Despedida".
- An **Action** is _what you do_ — a sanction like _Verbal Warning_ or
  _Dismissal_, defined once and reused.
- Un **Incidente** vincula una razón a un estudiante en una fecha, registra la evidencia,
  y enumera la(s) acción(es) realmente aplicadas. La matriz **pre-rellena** sugerencias
  por ocurrencia; el adjudicador confirma o anula.

La única consecuencia automática en todo el módulo es una Acción Disciplinaria
marcada **Disceso del Programa de Disparos**: grabar tal acción en un incidente
separa al estudiante del programa (a través de la misma
[columna de separación](withdrawal.md) utilizada por los retiros) y coloca un sostén que
bloquea la rematriculación. Todo lo demás es asesoramiento.

## Ajustes

Los informes disciplinarios del portal del instructor están compuestos por **dos** interruptores —
deben estar encendidos para que un instructor presente un incidente de un curso:

1. **Configuración seminaria → `Los instructores crean Incidente Disciplinario`** — el interruptor global. Cuando
   , cada curso muestra acciones para reportar incidentes disciplinarios en el
   curso y niveles de evaluación.
2. **Disciplinary Reason → `Instructor Portal`** — el interruptor por razón. Only
   reasons marked available to instructors appear in the portal report dialog.

Si el interruptor global está desactivado, el portal no muestra ningún botón de informe y
todos los incidentes son archivados por el personal del escritorio. El diseño de dos conmutadores te permite activar los informes de un portal
ampliamente mientras conservas las razones sensibles (por ejemplo, cualquier
que pueda llevar al despido de la lista de instructores.

## El catálogo

### Razones disciplinarias

Una **Razón Disciplinaria** (Desk → Razón Disciplinaria) es una categoría reutilizable de
violación. Campos:

- **Reason** — the name students and staff see (_Plagiarism_, _Disruptive
  Conduct_, _Unexcused Absence_).
- **Categoría** — _Integridad académica_, _conducta_, _asistencia_, _Financial_ o
  _Otro_. Utilizado para filtrar e informar.
- **Descripción** — una descripción de catálogo de lo que cubre esta razón.
- **Instructor Portal** — when checked, instructors can pick this reason when
  reporting from the portal (the second gate described under
  [Settings](#settings)).
- **Requiere Evaluación** — cuando se selecciona, esta razón vive en el \*\*nivel de evaluación
  \*\*: presentarlo requiere la inscripción _y_ la evaluación específica
  involucrada. Úsalo para cosas vinculadas a un trabajo (plagio en
  un ensayo, engañando un examen). Deje que no se verifique la conducta a nivel de curso
  (interrupción, retraso repetido).
- **Acciones recomendadas** — la matriz asesora (siguiente sección).

#### La matriz progresiva de la disciplina

Dentro de cada razón listas **Acciones Recomendadas** — registros que mapean una ocurrencia
número a la sanción que sugieres:

| Columna                | Significado                                                                                                                             |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Ocurrencia desde**   | Primera ocurrencia de esta fila se aplica a (1 = primer offense).                                    |
| **Ocurrencia a**       | Última aparición a la que se aplica esta fila. **0 significa "y arriba"** (abierto). |
| **Acción Recomendada** | La acción disciplinaria a sugerir.                                                                                      |
| **Nota**               | Guía opcional copiada en el incidente como nota de resultado.                                                           |

Una fila se aplica cuando el número de ocurrencia del estudiante cae entre _de_ y _a_
(incluido), tratando _a = 0_ como "y arriba". Así que una clásica escalera
de tres pasos para el _Plagiarismo_ (con una verbal y dos advertencias escritas) es:

| De | A | Acción Recomendada      |
| -- | - | ----------------------- |
| 1  | 1 | Advertencia verbal      |
| 2  | 3 | Advertencia por escrito |
| 4  | 0 | Despedido               |

El **número de ocurrencia** se calcula automáticamente: es un recuento de
basado en incidentes de este estudiante _por esta misma razón_. El tercer incidente de plagio
para un estudiante aterriza en la fila "3 y superior" y sugiere despedido. This is the
heart of the module: repeated minor offenses escalate on their own, without
anyone having to remember "wasn't this the third time?"

> **Asesoramiento, no automática.** La matriz solo **pre-llena** un incidente
> aplicó acciones. The adjudicator can confirm them, add others, or remove them
> entirely. La matriz es un motor de recomendación, no un motor de aplicación.

### Acciones disciplinarias

A **Disciplinary Action** (Desk → Disciplinary Action) is a sanction you can
apply. El sistema siembra un conjunto de inicio que puede editar o extender: _Advertencia verbal_,
_Advertencia escrita_, _Probación disciplinaria_, _Suspensión_, _Despedido_. Campos:

- **Nombre de la acción** — el nombre de la sanción (único).
- **Severity** — _Informal_, _Formal_, _Probation_, _Suspension_, or
  _Dismissal_. Informacional/para informar.
- **Triggers Program Dismissal** — **the one automatic effect in the module.**
  When an applied action of this type is recorded on an incident, the student is
  dismissed from the program through the shared
  [separation spine](withdrawal.md) and a re-enrollment hold is placed. By
  default only _Dismissal_ carries this flag.
- **Acción del instructor**: cuando se selecciona, los instructores pueden **grabar** esta acción
  ellos mismos desde el portal. Use it for low-stakes sanctions an instructor is
  authorized to hand out on the spot — chiefly **verbal and written warnings**
  that don't need escalation. Déjalo para cualquier cosa que deba ir a un adjudicador
  (prueba, suspensión, despedido).
- **Es Activo**: desmarca para retirar una sanción sin eliminar la historia.
- **Descripción** — lo que significa la sanción.

> **Dos banderas diferentes, dos tareas diferentes.** _Despedida del Programa de Disparos_
> decide si la aplicación de la acción termina o no el programa del estudiante. _Instructor
> Acción_ decide si un instructor de clase (en lugar de un adjudicador)
> puede registrarlo. A Verbal Warning is an _Instructor Action_ and does **not**
> trigger dismissal; a Dismissal triggers dismissal and is **not** an Instructor
> Action.

### Incidentes disciplinarios

Un **Incidente Disciplinario** (Desk → Incidente Disciplinario) registra un evento.
Campos clave:

- **Inscripción al programa** / **Estudiante** — a quién afecta el incidente (el estudiante
  es derivado de la matriculación).
- **Course Enrollment** / **Assessment** — the course (and, for
  _Requires Assessment_ reasons, the specific assessment) involved.
- **Fecha de incidente**, **Razón**, **Número de ocurrencia** (autocomputado).
- **Encabeza** y **Adjunto** — describen lo que sucedió y adjuntan pruebas.
- **Acciones aplicadas**: las sanciones se aplican realmente. Las filas prellenas de la matriz
  están marcadas _fueron sugeridas_; cada fila marca quién la aplicó y cuándo.
- **Estado** — el ciclo de vida del incidente:
  - **Informado** — archivado, esperando una acción.
  - **Acción Tomada** — se registró una sanción autorizada por el instructor.
  - **Escalado** — necesita un adjudicador (por ejemplo, la recomendación es una suspensión
    o despedir que un instructor no pueda grabarse a sí mismo).
  - **Desechado** — una acción aplicada activó la separación del programa.
- **Informado por** — quién lo presentó (establecer automáticamente cuando se reporta desde el portal
  ).
- **Descripción de la Resolución** — un narrativo de las acciones emprendidas.

Cuando eliges una razón y el número de ocurrencia es conocido, la matriz
automáticamente pre-rellena las **Acciones Aplicadas** con las sanciones recomendadas,
marcada como sugerencias, con una petición de _"confirmación o anulación"_. Te quedas en
control: manténgalos, cámbialos, o añade el tuyo propio.

## Informando del portal del instructor

Cuando [los dos switches] (#settings) están activados, los instructores pueden presentar incidentes
sin tocar el escritorio. Hay dos puntos de entrada.

### Informes de nivel de curso

En la tarjeta de un curso (para instructores y moderadores) un botón **Informar sobre el disciplinario
Incidente** abre un diálogo donde el instructor:

1. Selecciona al **estudiante** (el menú desplegable muestra a los estudiantes inscritos del curso con un nombre
   ).
2. Picks a **reason** — only reasons that are _Instructor Portal_ **and** not
   _Requires Assessment_ appear here (course-level conduct).
3. Opcionalmente añade **evidencia** y un **archivo adjunto**.

As soon as student and reason are chosen, the dialog previews _"This will be
occurrence #N"_ and the recommended action. Lo que sucede a continuación depende de la recomendación
(ver [Grabar ahora vs. tarde](#recording-now-vs-later)).

### Informes a nivel de evaluación

While grading a single submission (exam, assignment, quiz, or discussion) a
**Report Disciplinary Incident for this Submission** button opens the same
dialog, but with the **student and assessment fixed** from the submission you
are grading — the instructor only needs to choose a reason (here, only
_Instructor Portal_ **and** _Requires Assessment_ reasons appear, e.g.
plagiarism) and optionally add evidence. This is the natural place to flag
academic-integrity issues the moment you spot them.

### Grabando ahora vs. más tarde

Después de la vista previa, el diálogo se adapta a la acción recomendada:

- Si la recomendación es una **acción del instructor** (por ejemplo, advertencia verbal), el instructor
  ve **dos botones**:
  - **Reporte y Registre Acción** — archive el incidente _y_ registre la sanción
    ahora (estado → _Acción Tomada_). Use it when you handle it on the spot ("I
    spoke to the student").
  - **Reporte sólo** — archiva el incidente ahora y deja la acción para después
    (estado → _Informado_). Úsalo cuando quieras reportar y seguir calificando, o
    cuando alguien más debería decidir.
- Si la recomendación **no** es una acción del instructor, o activaría
  despedido, el instructor ve un solo botón **Informe**. The incident is
  filed and **Escalated** for an adjudicator to handle in Desk. (El mensaje
  confirma que fue reportado.)

### Acciones pendientes (informe ahora, actuar más tarde)

Los incidentes "Solo reportar" no caen en las grietas. La tarjeta \*\*To-Do
\*\* de cada curso muestra una lista de **Disciplinarios — Acciones Pendientes** para los instructores, con una
fila por incidente pendiente (estudiante, razón, ocurrencia, acción recomendada) y un botón
**Acción de registro**. **Cualquier instructor de ese curso** puede grabar la acción
— para que un evaluador pueda reportar un incidente después de horas y el profesor de
registre la sanción a la mañana siguiente o viceversa. Recording the
action moves the incident to _Action Taken_ and removes it from the list.

## Despedido: el único efecto automático

Si una acción aplicada está marcada **Descartar programa de activadores** (por defecto,
_Despedido_), guardando el incidente:

1. Inicia una **separación completa del programa** para el estudiante a través de la
   [separation spine](withdrawal.md), con estado de separación _Descartado_ y categoría
   _Disciplinario_, efectiva en la fecha del incidente.
2. Coloca una **re-inscripción** en el estudiante, así que no puede simplemente registrarse
   , con el incidente registrado como la fuente.
3. Establece el estado del incidente a **descartado**.

This is deliberately the _only_ enforced outcome — and it requires a human to
record a dismissal action on the incident. Las salidas disciplinarias nunca usan la taxonomía
orientada al estudiante [Reasones de Retirados](withdrawal.md) de cara a los estudiantes; la separación
lleva la Razón Disciplinaria en su historia y utiliza una motivación
_Disceso Disciplinario_ dedicada únicamente para satisfacer el registro de separación.

## Ejemplos prácticos

### Ejemplo 1 — Plagiarismo, escalando hasta despidos

**Goal:** plagiarism is a Verbal Warning the first time, a Written Warning the
second, and Dismissal the third.

1. **Crea la razón.** Escritorio → Razón Disciplinaria → Nuevo.
   - Razón: `Plagiarismo`; Categoría: `Academic Integrity`
   - Necesita Evaluación: ✓ (está vinculado a un trabajo)
   - Portal del instructor: ✓ (para que los instructores puedan marcarlo mientras califican)
   - Acción recomendada:
     - 1 → 1 — Advertencia verbal
     - 2 → 2 — Advertencia por escrito
     - 3 → 0 — Despido
2. **Confirm the actions exist.** _Verbal Warning_ and _Written Warning_ should
   be **Instructor Action = ✓**; _Dismissal_ should be **Triggers Program
   Dismissal = ✓** (these come seeded).
3. **First offense.** While grading the essay, the instructor clicks _Report
   Disciplinary Incident for this Submission_, picks `Plagiarism`, sees
   _"Occurrence #1 — Verbal Warning,"_ and clicks **Report & Record Action**.
4. **Third offense.** The same flow now previews _"Occurrence #3 — Dismissal."_
   Because Dismissal is not an instructor action, the instructor only gets
   **Report**, and the incident is **Escalated**. An adjudicator opens it in
   Desk, confirms the Dismissal action, and the student is separated with a
   re-enrollment hold.

### Ejemplo 2 — Experiencias repetidas (nivel del curso, informe ahora / actuar más tarde)

**Goal:** track unexcused absences so a pattern is visible, with warnings the
instructor can hand out.

1. Crea la razón `Ausencia sin excusa` (Categoría `Asistencia`, Portal del Instructor
   , Requiere una Evaluación: 1–2 → Adverbal, 3 → Escrito
   Advertencia.
2. Un asistente docente avisa una tercera ausencia y, desde la tarjeta del curso,
   hace clic en _Informar del incidente disciplinario_, elige al estudiante y la razón, y usa
   **Reporte sólo** (preferirían que el profesor decide).
3. El incidente aparece en **Disciplinario — Acciones pendientes** en el curso
   To-Do. El profesor de registro lo abre, hace clic en **Acción de registro**, y la
   advertencia escrita está en archivo.

### Ejemplo 3 — Una sanción que un instructor no puede dar

**Objetivo:** una violación de conducta cuya acción recomendada es _Probación de
Disciplinario_.

La probación **no** es una acción del instructor. Cuando un instructor lo reporta,
solo ve **Informe**; el incidente es **Escalado**. El decano lo abre en Información,
revisa la evidencia y registra Probación (o anula con una acción
diferente). El instructor hizo el informe; el adjudicador tomó la decisión.

## Día a día para el personal

- **Muestra un incidente en el escritorio.** Escritorio → Incidente Disciplinario → Nuevo. Pick the
  program enrollment and reason; the occurrence number and recommended actions
  fill in. Confirma o anula las **Acciones Aplicadas**, añade evidencia y guarda.
- \*\*Encuentra lo que necesita atención. \* Una vista de lista de _Incidente Disciplinario_ filtrado
  por `status = Reportado` o `status = Escalated` muestra la cola abierta;
  instructores ven los objetos pendientes de sus cursos en cada tarjeta de curso pendiente.
- **Grabar o cambiar una acción.** Abre el incidente, edita la tabla _Acciones Aplicadas_
  y guarda. Grabar una acción de _Despido del Programa de Disparos_ separará
  al alumno: hazlo deliberadamente.
- **Construye la historia de un estudiante.** Filtra _Incidente Disciplinario_ por el estudiante para ver
  cada razón, ocurrencia, acción y estado en el registro.

## Referencia rápida

| Si desea...    | Haga esto                                                                                                                                       |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Añadir un nuevo tipo de violación                              | Crear una Razón Disciplinaria (establecer Categoría; Marcar Portal del Instructor / Requiere Evaluación según sea necesario) |
| Hacer escalar las advertencias automáticamente                 | Añadir filas de Acciones Recomendadas a la razón (use _to = 0_ para "y arriba")                                              |
| Añadir una nueva sanción                                       | Crear una Acción Disciplinaria (establecer la Severidad)                                                                     |
| Dejemos que los instructores impartan una sanción ellos mismos | Tick **Acción del instructor** en esa Acción Disciplinaria                                                                                      |
| Hacer que una sanción termine el programa del estudiante       | Tick **Despido del programa de lanzadores** en esa acción disciplinaria                                                                         |
| Permitir que los instructores informen de cursos               | Activa la Configuración Seminaria → **Disciplinario del Portal** _y_ la razón del **Portal del Instructor**                                     |
| Marcar plagio al calificar                                     | Utilice _Reportar incidente disciplinario para este envío_ en el envío                                                                          |
| Informar ahora y decidir más tarde                             | Usa **Sólo Informes**; registra la acción más tarde desde el curso Hecho                                                                        |
| Grabar una acción pendiente                                    | Abra el curso To-Do → Disciplinario — Acciones pendientes → **Grabar Acción**                                                                   |
| Descartar a un estudiante por causa                            | Registrar una acción de _Despedido_ (Despido del Programa de Triggers) en el incidente                                       |
| Revisar el registro de un estudiante                           | Filtrar Incidente Disciplinario por estudiante                                                                                                  |

## Relacionados

- [Retiro y separación](withdrawal.md) — el flujo de despido disciplinario de la columna vertebral
  ; cómo mantiene el bloque de rematriculación.
- [Grading](grading.md) — where assessment-level reporting lives.
- [Rol de usuario](../administration/user-roles.md) — quién puede presentar incidentes, registrar acciones
  y adjudicar.
