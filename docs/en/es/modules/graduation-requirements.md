# Requisitos de Graduación

El Program Audit siempre ha respondido a la pregunta: _"¿este estudiante ha obtenido
suficientes créditos y aprobado los cursos requeridos?"_ Pero muchos seminarios gradúan
estudiantes contra una lista más larga: asistencias a capilla, entrevistas de ordenación,
cartas de recomendación, declaraciones doctrinales, horas de prácticas, una tesis o
trabajo final. El módulo de **Requisitos de Graduación** captura todo lo que
_no_ es un curso, permite a la secretaría crearlo desde Desk sin código y alimenta
el resultado en la misma página Program Audit que estudiantes y asesores ya
usan.

## Descripción general

Piense en la graduación como **dos vías paralelas**:

| Vía                                            | Dónde se configura                                              | Qué responde                                                                                                                                               |
| ---------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Académico** — créditos y cursos obligatorios | Program → tabla Courses                                         | ¿El estudiante ha aprobado los cursos correctos y acumulado suficientes créditos?                                                                          |
| **Requisitos de Graduación** — todo lo demás   | Program Graduation Requirement (este módulo) | ¿El estudiante también ha cumplido con la evidencia no relacionada con cursos (cartas, asistencias, proyectos, declaraciones firmadas)? |

Ambas vías se consolidan en la página Program Audit. Un estudiante es
`graduation_eligible` solo cuando **todos los elementos obligatorios activos** en
**ambas** vías están en verde. Las dos vías se evalúan de forma independiente: un
estudiante al que le falte una asistencia a capilla no queda bloqueado para registrarse en
cursos, y un estudiante que aún no ha terminado su último curso no queda
bloqueado para enviar sus cartas de recomendación.

## Las tres capas

El módulo está construido en tres capas. Pasará la mayor parte del tiempo en las dos primeras.

```
1. Biblioteca      — Graduation Requirement Item        (defínalo una vez, reutilícelo en cualquier lugar)
                    │
2. Política        — Program Graduation Requirement     (vincular a un programa, con fechas)
                    │
3. Instancia       — Student Graduation Requirement     (una fila por estudiante, congelada al matricularse)
```

### Capa 1 — La Biblioteca

Un **Graduation Requirement Item** declara _qué tipo de elemento existe en el
seminario_. Lo define una vez, con instrucciones para los estudiantes, y lo reutiliza
a través de tantos programas como desee.

Cada elemento de la biblioteca elige **uno** de cuatro tipos:

- **Event Attendance** — se cumple cuando un estudiante asiste a un
  [Event](../modules/academic-calendar.md) específico. Ejemplo: _"Retiro de Formación Espiritual
  2027"_. Elige **Evento por Estudiante** si cada estudiante debe mostrar
  individualmente; dejar que no se marque si una única ocurrencia (un evento único
  todos asisten juntos) satisface a la compañía.
- **Asistencia al Chapel** — asistencia _basada en el contador_ a los servicios del capellán recurrente
  , realizada automáticamente a medida que los estudiantes **verifican** desde
  el portal. Estableces cuántos servicios son requeridos (por ejemplo, 30); el requisito
  se vuelve verde al momento en que el número de facturación de un estudiante alcanza ese número
  . A diferencia de la asistencia al evento, **no** creas un registro por un servicio
  : el capellán se organiza cada capellán una vez, los estudiantes auto facturan,
  y el sistema mantiene el funcionamiento en cuenta. See
  [Worked example 1](#example-1-chapel-attendance-self-check-in) for the full
  setup.
- **Manual Verification** — se cumple cuando el personal confirma que el estudiante hizo
  lo requerido, opcionalmente con evidencia en archivo del estudiante, del personal o
  de ambos. Ejemplo: _"Declaración Doctrinal firmada"_, _"Entrevista de ordenación"_.
- **Linked Document** — se cumple cuando otro documento del sistema
  alcanza un estado específico. You pick the document from a curated list (see
  [Allowed documents](#allowed-documents)). Example: a _Recommendation Letter_
  moves to `Approved`, a _Culminating Project_ moves to `Completed`, or an
  _Internship_ moves to `Completed`.

Dos indicadores controlan la evidencia en los elementos de Manual Verification:

- **Evidence Submitted by Student** — ofrece al estudiante un botón de carga en
  su página de auditoría. Úselo para cosas como un formulario de acuse de recibo firmado
  que el propio estudiante adjunta.
- **Evidence Required by Staff** — el personal debe adjuntar un archivo al marcar el
  elemento como Fulfilled. Úselo para elementos que debe conservar en el expediente (una declaración
  doctrinal firmada, actas escaneadas del concilio de ordenación).

Estos dos indicadores son independientes. Una declaración doctrinal podría requerir _ambos_
(el estudiante carga el PDF firmado y el personal carga su nota de verificación de identidad). Una orientación de nuevo estudiante normalmente requiere _ninguna de las dos_ — el personal
solo marca Completo.

> **Why two flags?** Some items, like a new-student orientation, are simple —
> staff ticks a box. Otros, como una proposición doctrinal, necesitan un documento
> escrito del estudiante _y_ una verificación de identidad del personal. Un par de campos
> pueden modelar ambos.

#### Blocks Graduation Request

Si su seminario usa el flujo de [Graduation Request](graduation-request.md),
cada elemento de biblioteca tiene un indicador más — **Blocks Graduation Request**
(visible solo cuando `Mandatory` está marcado). Cuando está definido, el estudiante no puede
ni siquiera _presentar_ una Graduation Request hasta que este requisito esté `Fulfilled` o
`Waived`. Úselo para prerrequisitos estrictos que la Secretaría Académica quiere
verificar por adelantado: cartas de recomendación, tesis, declaraciones doctrinales.
Los elementos sin ese indicador igualmente se siguen para la elegibilidad de graduación,
pero el estudiante puede presentar la solicitud y el paso de revisión académica
detectará cualquier pendiente.

### Capa 2 — La Política

Un **Program Graduation Requirement** vincula elementos de biblioteca a un Program con
fechas de vigencia. Esta es la principal pantalla de autoría de la Secretaría Académica.

Campos en el encabezado de la política:

- **Program** — a qué programa se aplica esta política.
- **Active from / Active until** — la ventana del año de catálogo. Un estudiante que se matricula el 2026-09-01 toma la política cuya ventana contiene esa
  fecha.
- **Is Active** — control para marcar un borrador (o reemplazada) frente a una política publicada.

Dentro de la política, enumere los **elementos de requisito del programa** (las filas de la política).
Cada fila elige un elemento de biblioteca y agrega metadatos de vinculación específicos del programa:

- **Activation Mode** — _cuándo_ el requisito pasa a estar "pendiente" para un
  estudiante matriculado. Véase más abajo.
- **Is Mandatory** — ¿no cumplir esta fila bloquea la graduación, o es
  opcional/informativa?
- **Cantidad requerida** - el recuento que el estudiante debe alcanzar. Para **Chapel
  Atendencia** es el número de servicios a los que debe registrarse (p. ej. 30); para
  **Verificación manual** es el número de instancias (por ejemplo, registros
  de 8 horas de servicio). La Asistencia al Evento y el Documento Enlazado siempre cuentan como 1.

#### Modos de activación

Un requisito puede quedar pendiente _el día que el estudiante se matricula_ — o solo tras algún
disparador. The modes:

- **Always Active** — pendiente desde el primer día. Úselo para cualquier cosa que el estudiante pueda empezar en cualquier momento (asistencia a capilla, declaración doctrinal).
- **After Requirement** — due only after one _other_ requirement in this same
  policy has been fulfilled or waived. Use this for prerequisite chains:
  _"Ordination Interview"_ becomes due only after _"Doctrinal Statement"_ is
  fulfilled. To require more than one prerequisite, chain requirements (each
  pointing at the previous one).
- **Credits Passed** — due only once the student's total passed credits
  reach a number you set.
- **Course Passed** — due only once the student has **passed** the course you
  set (e.g. _"Thesis"_ becomes due only after the student passes _"Writing a
  Thesis"_). A single passing attempt satisfies the gate **permanently** —
  even for a repeatable course, and regardless of any other attempt. **Course
  Passed and After Requirement are mutually exclusive on one row;** to gate on
  _both_ a course and a prior requirement, chain two requirements — the first
  using Course Passed, the second using After Requirement pointing at the first.
- **On Document Status** — pendiente solo después de que un documento relacionado alcance un
  estado dado. El `link_doctype` del elemento de biblioteca y el `linked_doc_status`
  seleccionado juntos definen la compuerta.
- **Time Offset** — pendiente en relación con un ancla de fecha. Elija un ancla
  (Expected Graduation Date, Last Term Starts, Program Starts), un valor de desfase
  y una unidad (Days o Academic Term). _"Recital de último año — pendiente 60 días
  antes de Expected Graduation Date"_ es offset = -60, unit = Days, anchor =
  Expected Graduation Date.

#### Scoping a requirement to an emphasis

By default a policy row applies to **every** student in the program. To make a
requirement apply only to students on a particular emphasis (e.g. _"Counseling
Internship"_ for the Counseling emphasis), set **Applies to Emphasis** to one of
the program's emphases (Program Tracks marked as emphasis). The row then
materializes only for students who have declared that emphasis. Advisory-only
emphases never count. Leave the field empty to apply the requirement to everyone.
To apply one requirement to several emphases, add it once per emphasis — a
student who holds more than one of them still gets a single row.

Because an emphasis can be declared _after_ enrollment, an emphasis-scoped
requirement is added to a student's audit the moment they declare the matching
emphasis — not only at enrollment. If a student later **drops** the emphasis, the
requirement is **not** removed automatically (they may already have started or
completed it); instead it appears on the **Orphan Graduation Requirements** report
for a registrar to Cancel, Waive, or Withdraw. To avoid changing the requirement
set out from under an in-flight graduation, **emphasis changes are blocked once a
Graduation Request exists** — delete or cancel the graduation request first, then
change the emphasis.

Una fila cuya activación aún no se ha disparado aparece en la auditoría como
_Not Yet Active_, y aunque sea obligatoria **no** bloquea la elegibilidad
de graduación — es "aún no es su problema". Una vez activa, una fila obligatoria sin cumplir bloquea la graduación.

### Capa 3 — La Instancia (instantánea)

Cuando se envía un Program Enrollment, el sistema **toma una instantánea** de la política activa
en filas por estudiante llamadas **Student Graduation Requirements**
(SGR). Una fila SGR por fila de política, multiplicada por la cantidad para los elementos de
Manual Verification. **Chapel Attendance** is the exception — it stays a
_single_ row carrying the required count and a live "attended" tally (e.g.
_22 / 30_) rather than splitting into one slot per service.

Esta instantánea queda **congelada para ese estudiante.** Que una secretaría publique una nueva
política en 2027 **no** cambia retroactivamente los requisitos de un
estudiante que se matriculó en 2025. Este es el contrato del año de catálogo: es la regla que los seminarios honran tradicionalmente y se aplica por construcción.

El **Program Enrollment** también almacena la política que tomó
(`graduation_policy`) para que quien revise el expediente pueda rastrear exactamente en
qué año de catálogo está el estudiante.

Si la secretaría realmente necesita migrar a un estudiante a la política actual
(p. ej., el estudiante lo solicitó o un regulador lo exigió), existe una acción
permitida **Resnapshot** en el Program Enrollment. De forma predeterminada
conserva cualquier fila que ya estuviera eximida; la acción queda registrada.

## Ejemplos prácticos

### Ejemplo 1 — Atención al Chapel (auto check-in)

**Objetivo:** cada estudiante debe asistir a 30 servicios del capellán en todo el programa,
grabado por estudiantes que se registran a sí mismos.

1. **Cree el elemento de biblioteca.** Desk → Graduation Requirement Item → New.
   - Requirement: `Asistencia a capilla`
   - Tipo: `Asistencia al Chapel`
   - Cantidad predeterminada: `30`
   - Obligatorio: ✓
   - Instrucciones: _"Asista a al menos 30 servicios de capillo. Abra la página de auditoría del programa
     durante el servicio y pulse **Verificar**."_

2. **Agréguelo a la política del programa.** Desk → Program Graduation Requirement
   → abra _MDiv 2026 Catalog_ → añada una fila apuntando a `Chapel Attendance`.
   - Activation Mode: `Always Active`
   - Quantity Required: `30` (o sobrescriba por programa — p. ej., 15 para una
     maestría a tiempo parcial)

3. **At enrollment**, the system materializes a **single** SGR row per
   student that starts at _0 / 30_.

4. **Día a día**, no hay nada que ver con el personal. Mientras cada estudiante verifica
   en un servicio de capilla, su cuenta sube (_1 / 30_, _2 / 30_, …) y el renglón
   se vuelve verde automáticamente en el momento en que alcanza 30. La página
   de la auditoría del programa lo refleja inmediatamente.

#### Programación de capítulos y cómo funciona el check-in

Los servicios de Chapel viven en su propio registro **Chapel** (Desk → Chapel → New). A
chapel is a public event — all students and instructors are invited, and it is
open to the public.

- **Tema, fecha/hora, habitación** — lo que los estudiantes ven, y cuando el check-in es
  permitido.
- **Chapel Team** — the table where the chaplain assigns the preacher,
  worship leader, host, etc., and tracks each person's invitation status.
- **Confirmed** — students can only check in to a chapel once it is
  **Confirmed**. Dejarlo sin marcar mientras usted todavía está planeando el servicio.

**La ventana de facturación** se rige por dos ajustes en _Configuración seminaria →
Chapel & Eventos Oficiales_: cuántos minutos **antes** del inicio y **después**
el check-in final permanece abierto. Establece **ambos a 0** para eliminar completamente el límite de tiempo
(los estudiantes pueden comprobar en cualquier momento en que se confirme el capellón).

\*\* Código de facturación opcional. \* Si _Requiere código de facturación_ está habilitado en Ajustes seminarios
, cada capellán obtiene un código corto legible por humanos (se muestra en el registro Chapel
). Muéstralo en pantalla durante el servicio; los estudiantes deben escribirlo en
facturar, lo que evita que la gente se registre mientras esté ausente.

**Optional Google Calendar sync.** If _Sync chapels with Google Calendar_ is
enabled and an _Official Google Calendar_ is selected in Seminary Settings,
each confirmed chapel is published to that shared calendar (with the chapel
team added), so students and the public can see the schedule. El conmutador está
por defecto — los seminarios que no usan el calendario de Google pueden ignorarlo, y
capeles individuales pueden optar por su propia casilla de verificación _Sincronizar con Google Calendar_
.

### Ejemplo 2 — Tres cartas de recomendación (con casillas con nombre)

**Objetivo:** todo solicitante de graduación presenta tres cartas de recomendación
— _Pastoral_, _Académica_, _Carácter_ — cada una de un tipo diferente
de recomendador, cada una con sus propias instrucciones.

El instinto es usar un solo elemento de biblioteca con `quantity_required = 3`.
**No lo haga.** Cada carta tiene un público diferente e instrucciones diferentes.
En su lugar, cree **tres elementos de biblioteca por separado**:

- _Pastoral Reference Letter_ — Linked Document, destino `Recommendation
      Letter`. Instrucciones: _"Solicítela a su pastor de la iglesia local."_
- _Academic Reference Letter_ — igual. Instrucciones: _"Solicítela a un
  profesor de tu especialidad."_
- _Character Reference Letter_ — igual. Instrucciones: _"Solicítela a
  alguien que le conozca desde hace al menos 5 años y que no sea pariente."_

El estudiante ve tres entradas distintas en la auditoría, cada una con su propia
guía. El doctype Recommendation Letter gestiona el resto: un enlace tokenizado al portal de invitados enviado al recomendador, entrega multicanal
(portal / correo electrónico / carga manual) y un flujo de trabajo que termina en `Approved`.
Cuando la carta es aprobada, la fila SGR pasa a Fulfilled automáticamente.

### Ejemplo 3 — Entrevista de ordenación (después de las cartas)

**Objetivo:** una entrevista de ordenación solo puede programarse _después_ de que ambas
cartas de recomendación estén ingresadas.

1. Cree un elemento de biblioteca Manual Verification _Ordination Interview_
   (Obligatorio, Staff Evidence Required = ✓ con etiqueta _"Acta de la entrevista"_).
2. En la política, añada una fila con **Activation Mode = After
   Requirement** y elija como prerrequisitos las filas de política _Pastoral Reference_ y
   _Academic Reference_.
3. Hasta que ambas cartas estén en estado Fulfilled, la auditoría muestra _"Ordination Interview
   — Not Yet Active"_ y no bloquea la graduación. En el momento en que la segunda
   carta es aprobada, la fila se activa y empieza a contar para la
   elegibilidad.

### Ejemplo 4 — Proyecto de fin de estudios (un doctype vinculado complejo)

**Objetivo:** todo estudiante de MDiv redacta un Proyecto de fin de estudios, defendido en hasta
tres rondas con revisores.

Este es el doctype **Culminating Project**. No necesita modelar el
proyecto usted mismo - viene con el sistema, incluyendo roles de revisor, un plan
de hito escalonado, y su propio flujo de trabajo. Las piezas configurables (proyecto
tipos, hitos, defensas) se describen en
[Proyectos Culminantes: tipos, hitos y defensas](#culminating-projects-types-milestones-and-defenses)
a continuación.

Para conectarlo a un programa:

1. Cree un elemento de biblioteca _Proyecto de fin de estudios_.
   - Type: `Linked Document`
   - Linked Document: `Culminating Project`
   - **Culminating Project Types Allowed**: list the project type(s) a student
     may pick (e.g. _Thesis_, _Summative Paper_).
2. Agréguelo a la política con **Activation Mode = Time Offset**, ancla
   `Last Term Starts`, valor `0`, unidad `Days` — es decir, pendiente una vez que inicia el
   último período.
3. Al matricularse, la fila SGR aparece en la instantánea. El estudiante inicia
   el proyecto desde la página de auditoría (un botón de _Iniciar proyecto_, elegir un tipo
   si se permite más de uno); cuando el proyecto llega a `Completado`, la fila SGR
   se vuelve a completar automáticamente.

### Ejemplo 5 — Declaración doctrinal (firmada por ambas partes)

**Objetivo:** el estudiante firma una declaración doctrinal; la Secretaría Académica
verifica la firma y archiva una copia.

1. Cree un elemento de biblioteca _Doctrinal Statement_.
   - Type: `Manual Verification`
   - Obligatorio: ✓
   - Evidence Submitted by Student: ✓, etiqueta _"Declaración firmada (PDF)"_
   - Evidence Required by Staff: ✓, etiqueta _"Nota de verificación de identidad"_
2. El estudiante carga el PDF firmado en el portal. Su casilla pasa a
   `Submitted`.
3. La secretaría abre la fila SGR, adjunta la nota de verificación y
   hace clic en Fulfilled.

## Culminando proyectos: tipos, hitos y defensas

Un \*Proyecto Senior \* / _Este_ / _Capstone_ está conectado por cable como un requisito de **Documento**
que apunta al **Proyecto Culminante** doctype (Ejemplo 4). Behind
that one requirement sits a small framework you configure once.

### Tipos de proyecto

Un **Tipo de proyecto** (Escritorio → Culminando tipo de proyecto) es una plantilla
reutilizable para un _tipo_ de proyecto — e. . _Este_, _Capstone_, _Summative
Paper_. Cada tipo define:

- **Curso**: un proyecto culminante también es una inscripción real al curso, por lo que
  gana crédito y una calificación como cualquier otro curso. Los nombres de tipo que el Curso
  lo respalda.
- **Hitos** — el plan escalonado que cada proyecto de este tipo sigue (abajo).
- **Reader policy** — the type decides the project's reader _composition_ so it
  isn't re-decided per project (below, under _Readers, committee, and external
  examiners_).

En el elemento de la biblioteca de requerimientos se listan los **tipos de proyecto Culminantes
Permitidos**. If you allow exactly one, the student is auto-assigned it; if you
allow several (e.g. Thesis _or_ Summative Paper), the student chooses one on the
Program Audit page when they start.

### Milestones

Cada Tipo de Proyecto lleva una **plantilla de hitos** — una lista ordenada de pasos.
Para cada paso que establezcas:

- **Por favor** — _Estándar_, _Propuesta_, _Defensa_, o _Envío final_.
- **Vencimiento** — calculado a partir de un **ancla** (proyecto de inicio, fecha de inscripción,
  Graduación esperada, Plazo de comienzo, o el Hito Anterior) más un **offset**
  en días o términos académicos. Así que "Propuesta - 30 días después del inicio del proyecto" o
  "Defensa, un término antes de la graduación esperada" son solo un anclaje + offset.
- **Requiere Envío** - si el estudiante debe subir o no trabajo para este paso.
- **Inicia sesión** — que los roles deben aprobar: **Asesor**, **Segundo Lector**,
  **Tercera Lectura**, **Expansión**. A milestone reaches _Approved_ only once
  every required role has signed, and the project can be marked _Completed_ only
  when all mandatory milestones are approved.

Cuando un estudiante inicia un proyecto, los hitos de plantilla son **instantáneos**
en su proyecto — el mismo contrato de inicio congelado que los requisitos de graduación
. Each snapshot row tracks its own status, due date, sign-offs, and
submission round, and overdue milestones are flagged automatically.

### Defensa (y su evento de calendario)

Un hito de tipo **Defense** puede llevar un evento calendario. En la plantilla
, marca **Crea el Evento** y elige una **Categoría de Eventos** (consulta la siguiente sección
). Luego, desde el banco de trabajo del proyecto, el **asesor** hace clic en **Schedule
Defense**, elige una fecha/hora y ubicación opcional, y el sistema crea un evento
calendario con el estudiante, los lectores y el comité como participantes.

El evento de defensa es _solo calendario_: existe para que todos aparezcan en el
momento adecuado. It does **not** auto-fulfil anything; the defense is recorded by the
readers signing off the Defense milestone, exactly like any other milestone.

Students, advisors, and readers do all of this from the **Culminating Project
workbench** (a portal page) where they see milestones and due dates, upload
submissions, and record sign-offs.

### Academic unit and advisor assignment

A project belongs to an **Academic Unit** (an academic department) that the
student declares when the project is created — the advisor field is no longer
filled by the student. The **department assigns the advisor**: from the project,
use **Assign Advisor**, which offers only **qualified** advisors — instructors
wired with the _Thesis/CP Advisor_ capability who still have capacity. The
project stays in **Draft** until an advisor is assigned, then moves to **Active**;
the advisor's capacity is claimed (and released if you reassign).

By default the advisor picker is a wide net across all academic units, so a dean
can step in. On the Culminating Project Type, tick **Advisor from Project's
Academic Unit** to narrow it to advisors from the project's own department. (See
[Academic Units & Faculty](./academic-units.md) for how advisor pools and
capacity work.)

### Readers, committee, and external examiners

Reader _composition_ is policy, set on the **Culminating Project Type**, not
decided per project. On the type, tick **Apply Policy to Reader Selection** and
set:

- **Readers Required** — how many named readers (beyond the advisor): 0, 1, or 2.
  A project has exactly two named slots (Second and Third Reader); put any
  further reviewers on the committee.
- For each slot, the **reader type** — **Instructor** or **External Examiner** —
  and, for instructor slots, **Allow Instructors from Other Units** (off = must
  be a member of the project's academic unit).

Projects of that type then inherit the composition: each slot's type is fixed,
extra slots are disallowed, and an instructor reader is checked against the unit
rule. With the policy off, staff pick reader types and members freely.

An **External Examiner** is a vetted outside reader, recorded once (Desk →
External Examiner) and reused — Person-backed, with their institution,
qualifications, and an _Invite Again_ note so "do we want them back?" doesn't
live in someone's head. They are deliberately **not** instructors (reduced
access, no teaching). External readers don't sign milestones themselves; the
advisor records their sign-off on their behalf, as for committee members.

The **committee** (managed by the advisor on the workbench) takes internal
instructors or External Examiners; the advisor signs milestones on the
committee's behalf.

## Cómo se manejan los eventos de asistencia

El tipo de requerimiento de **asistencia a eventos** está respaldado por dos partes: una
_categoría_ reutilizable y los _eventos_ fechados creados a partir de él.

### Categorías de eventos (el tipo)

An **Event Custom Category** (Desk → Event Custom Category) describes a _kind_ of
event students attend — e.g. _Convocation_, _Spiritual Formation Retreat_, _Exit
Interview_. Características:

- **Por estudiante**: si está marcado, cada estudiante necesita su _propia_ ocurrencia (una
  one-on-one como una entrevista de salida); si no está marcado, una ocurrencia _única_
  satisface a toda la cohorte (una convocación que todo el mundo asiste juntos).
- **Visibilidad** — Público (aparece en el calendario compartido) o privado.
- **Instructions** — copied into each event's description (dress code, what to
  bring, location notes).

Tu elemento de la biblioteca de asistencia al evento apunta a la **categoría**, no a una fecha
específica, porque la misma categoría se reutiliza cada año.

### Creando los eventos actuales

Hay dos maneras en que el personal convierte una categoría en un evento fechado que los estudiantes obtienen crédito
por:

- **Cohort event** (_Per Student_ off) — from the **Event Custom Category** list,
  click **Create Event** on the category's row, pick a date (and optional
  location). The system creates one Event covering every enrolled student who
  still owes this requirement; marking that Event **Completed** flips all of
  their requirement rows to Fulfilled at once.
- **Evento por estudiante** (_Por estudiante_ en) — desde el **Programa
  Inscripción**, haz clic en **Programar evento requerido**, elige el requisito y una fecha
  . Esto crea un evento para ese estudiante, realizado cuando se marcan
  como asistente.

Either way the event is a normal calendar Event — it can be synced to Google
Calendar like any other — and the matching graduation requirement updates
automatically, with no separate "tick Fulfilled" step.

> **Chapel is different.** Chapel attendance is recurring and count-based, so it
> uses its own **Chapel Attendance** type with student self check-in
> ([Example 1](#example-1-chapel-attendance-self-check-in)), not the Event
> Attendance flow described here.

## Día a día para el personal

### Dónde mirar

- **Estado por estudiante** — abra el _Program Enrollment_ del estudiante y
  desplácese hasta la tabla _Student Graduation Requirements_, o abra la
  _página Program Audit_ desde el portal del estudiante (el personal también puede acceder a ella
  desde el Backoffice).
- **Política por programa** — Desk → Program Graduation Requirement → elija la
  política activa del programa.
- **Resumen de cohorte** — una vista de lista de _Student Graduation Requirement_
  filtrada por `status = Not Started` y agrupada por `requirement_name` le muestra
  quién aún debe qué.

### Marcar algo como Fulfilled

Abra la fila SGR (desde el Program Enrollment padre o directamente).
Establezca `status` en `Fulfilled`, adjunte evidencia del personal si el requisito lo
pide y guarde. El sistema sella `verified_by` y `verified_on`
automáticamente.

For Linked Document and Chapel Attendance requirements, you usually do **not**
mark the SGR row manually — the linked document's workflow (or the student's
own check-ins) flips it for you. Aún puedes renunciar a ellos, o marcar
como una sobreescribición.

### Eximir un requisito

A veces, un requisito genuinamente no debería aplicarse a un estudiante en particular
(p. ej., el requisito se agregó para nuevos estudiantes y un estudiante en curso
solicitó formalmente una excepción). En la fila SGR:

1. Marque **Waived**.
2. Ingrese un **Waiver Reason** (un párrafo breve — este es su rastro de auditoría).
3. Guardar. El sistema registra `waived_by` (usted) y `waived_on` (ahora).

Una fila eximida cuenta como satisfecha para la elegibilidad de graduación, pero se distingue
claramente de `Fulfilled` en los reportes.

### Publicar un nuevo año de catálogo

Cuando el seminario cambia sus requisitos, publique una política nueva **junto a** la antigua — _no_ edite la antigua in situ.

1. Duplique el Program Graduation Requirement existente (o cree uno
   nuevo).
2. Defina `Active from` en la fecha en que entra en vigor el nuevo catálogo (p. ej.,
   `2027-09-01`).
3. Defina `Active until` de la política anterior al día anterior
   (p. ej., `2027-08-31`).
4. Marque `Is Active` en la nueva.
5. Ajuste las filas.

Los estudiantes que se matriculen **después** del nuevo `Active from` generarán la instantánea con la
nueva política. Los estudiantes ya matriculados conservan la anterior. Si un estudiante
pide explícitamente pasar al nuevo catálogo, use **Resnapshot** en su
Program Enrollment.

### Allowed documents

A _"Linked Document"_ requirement points at a real document in the system. To
keep that choice friendly, the document types that may fulfil a requirement are
curated in a small list — **Allowed Graduation Document** (Desk → Allowed
Graduation Document). Each entry pairs a document type with a plain-language
**label** and the **fulfilling status** that marks it done. The seminary ships
with the built-in options:

| Label                        | Document               | Fulfilling status |
| ---------------------------- | ---------------------- | ----------------- |
| Thesis / Culminating Project | Culminating Project    | `Completed`       |
| Recommendation Letter        | Recommendation Letter  | `Approved`        |
| Internship                   | Internship Application | `Completed`       |

When you author a library item with `Type = Linked Document`, you simply pick
from this list under **Fulfilling Document** — the underlying doctype and the
status that fulfils it are filled in for you, so you never type a raw doctype
name or guess a status.

Most seminaries never touch the list itself. If your IT team builds a _new_ kind
of linked document (say an _Internship Report_ doctype with its own workflow),
an **advanced user** adds one Allowed Graduation Document row for it — no code —
and it becomes available to every program policy. The system reflects status
changes onto SGR rows automatically.

> **Heads-up — bespoke doctypes.** Three requirement types ship with their own
> complete doctypes because the generic "Linked Document" path is too thin for
> them: **Recommendation Letter** (with the external recommender portal),
> **Culminating Project** (with reviewer rounds and milestones), and
> **Internships** (with org-posted positions, placements, hours, and supervisor
> evaluations — see [Internships](internship.md)). For these, use the dedicated
> doctypes; the system already wires them into the graduation audit.

## Cómo se conecta esto con Program Audit

La **página Program Audit** (`/program-audit/<enrollment>`) presenta una vista única
y consolidada:

- La sección **Académico**, alimentada desde la tabla Program → Courses, muestra
  el progreso de créditos y el estado de los cursos obligatorios. _(sin cambios)_
- La sección **Requisitos de Graduación**, alimentada desde la instantánea SGR, muestra
  cada requisito activo, agrupado por estado, con instrucciones por fila
  y cualquier evidencia ya archivada. Las filas de asistencia a Chapel muestran un recuento
  en vivo (_22 / 30_) y un botón **facturar** cada vez que se abre un capellán confirmado.

A un estudiante se le muestra `Eligible to graduate` solo cuando ambas secciones están
libres de elementos obligatorios sin cumplir.

## Leveling and advanced standing

Some students arrive needing **leveling** (remedial courses, e.g. biblical
languages) or qualify for **advanced standing** (placed out of courses or
requirements). This is per-student and lives on the **Program Enrollment**, in
the _Leveling & Advanced Standing_ section — separate from the program-flat
policy and from emphasis.

- **Register the common cases once** as a **Leveling Profile** (global, or
  filtered to one program). On a student's enrollment, use **Apply Leveling
  Profile** to seed an editable plan, then override per student. You can also
  add rows by hand with no profile.
- Each plan row is one of: **Leveling Course** (must pass, unless placed out),
  **Course Exemption** (placed out outright), **Placement Assessment** (a
  placement exam whose recorded **score** gates the leveling courses), or
  **Requirement Waiver** (waive a graduation requirement).
- **Placement Assessments are their own thing** (no longer a graduation
  requirement). Define each exam once as a **Placement Assessment** (Desk →
  Placement Assessment) and give it an **Academic Unit** — that unit's **Placement
  Examiner** capability holders grade it. The score lives on the student's
  enrollment, not in their graduation-requirement list, so leveling and graduation
  stay separate.
- **Score-gated placement.** Give each leveling course an _"Exempt if Score ≥"_
  threshold and point its _Placement Assessment_ at the exam (the threshold sits
  on the same row). A **Placement Examiner** records the score from their
  [Faculty Worklist](./academic-units.md#the-faculty-worklist-portal); each course
  then resolves to **Exempt** or **Required** automatically (e.g. a Greek score of
  80 places out of Greek I & II, still requires Greek III). Manual overrides stick
  (tick _Overridden_); use **Resolve Leveling Plan** after hand-edits.
- **Effects.** An exemption clears the course for graduation (and satisfies a
  _Course Passed_ prerequisite on other requirements) but earns **no credit and
  no grade**. Leveling courses keep their credit for enrollment but **don't count
  toward the degree**. A **Required** (unmet) leveling course **blocks
  graduation** — waive the row if a student should be let through.
- **Before enrollment**, an applicant can flag _Requesting requirement review_;
  that raises a registrar to-do but changes nothing on its own (the plan is
  always built on the enrollment, once transcripts can be verified).

## Referencia rápida

| Si desea...      | Haga esto                                                                                                                                                            |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agregar una nueva categoría de requisitos para todo el seminario | Crear un Graduation Requirement Item (biblioteca)                                                                                                 |
| Aplicar un requisito a un programa específico                    | Añadir una fila al Program Graduation Requirement (política) de ese programa                                                                      |
| Requiere que los estudiantes asistan a los servicios de N capel  | Tipo de elemento de la biblioteca = Asistencia al Chapel, establecer cantidad predeterminada; programar los registros del Chapel y marcarlos Confirmados             |
| Requiere una tesis / cápsula                                     | Tipo de elemento de biblioteca = Documento vinculado → Culminando proyecto; listar el tipo de proyecto permitido                                                     |
| Definir las etapas y la defensa de un proyecto                   | Agrega hitos al tipo de proyecto de cultivo (anclaje + desplazamiento, roles de desconexión, Crea Evento para la defensa)                         |
| Requerir asistencia en un evento único                           | Crear una categoría personalizada de eventos, luego crear un evento (cohorte) o programar un evento requerido (por estudiante) |
| Hacer que un requisito venza solo después de otro                | Activation Mode = After Requirement, elija los prerrequisitos                                                                                                        |
| Make a requirement due only after a course is passed             | Activation Mode = Course Passed, set the Prerequisite Course                                                                                                         |
| Apply a requirement only to one emphasis                         | Set Applies to Emphasis on the policy row (add the row per emphasis for several)                                                                  |
| Hacer que un requisito venza X días antes de la graduación       | Activation Mode = Time Offset, anchor = Expected Graduation Date                                                                                                     |
| Resolve a requirement left behind by a dropped emphasis          | Orphan Graduation Requirements report → Cancel / Waive / Withdraw                                                                                                    |
| Set up leveling / advanced standing for common entrance cases    | Create a Leveling Profile, then Apply Leveling Profile on the enrollment                                                                                             |
| Place a student out of a course by exam score                    | Leveling row: Leveling Course + Gating Assessment + "Exempt if Score ≥"; verify the exam with a score                                                |
| Confirmar que un estudiante cumplió algo                         | Abrir la fila SGR, establecer status = Fulfilled                                                                                                                     |
| Eximir a un estudiante de un requisito                           | Abrir la fila SGR, marcar Waived, dar un motivo                                                                                                                      |
| Actualizar el catálogo del seminario                             | Publicar un nuevo Program Graduation Requirement con una nueva fecha Active from — no edite el anterior                                                              |
| Mover a un estudiante al nuevo catálogo                          | Acción Resnapshot en su Program Enrollment                                                                                                                           |

## Relacionados

- [Matrícula](enrollment.md) — Program Enrollment es donde vive la instantánea.
- [Calendario académico](academic-calendar.md) — Eventos usados por los requisitos de Event
  Attendance.
- [Internships](internship.md) — the bespoke linked-document path for
  supervised placements, hours, and supervisor evaluations.
- [Roles de usuario](../administration/user-roles.md) — qué roles pueden crear
  políticas, marcar requisitos como Fulfilled y eximirlos.
