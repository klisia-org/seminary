# Calificación

Grading is how you decide what a student earned in a course and how you keep
track of getting there. El ERP seminario te da dos lugares para trabajar, y
encaja limpiamente: una **Tarjeta To-Hecho** que superficializa lo que está esperando en tu
atención, y un **Gradebook** que te da la imagen completa en una cuadrícula.

## Descripción general

La calificación en ERP seminario se construye alrededor de dos ideas:

- **Criterio de la evaluación** define _lo que cuenta_ hacia la calificación final para un curso
  (el plan de estudios dice "30% papeles, 20% cuestionarios, 50% examen final", y
  los Criterios de Evaluación lo expresan como filas en el Horario del Curso).
- **Envíos** son _lo que los estudiantes aportan_ (un papel, un intento de cuestionario, un examen
  , una publicación de discusión). Cada envío recibe una calificación con el criterio
  del Criterio de la evaluación al que pertenece, luego se inscribe en el total del curso
  del estudiante.

Some assessments don't have a submission at all — chapel attendance,
class participation, an in-class presentation. Those use a special type
called **Offline**, where you enter the grade directly in the Gradebook
without any handed-in artifact.

## Tipos de exámenes

Cuando creas un criterio de evaluación (en la página de evaluación del curso),
eliges un **tipo**. Ese tipo decide cómo se recolecta la evaluación
y cómo los estudiantes envían (o no).

### Examen

Preguntas de múltiples opciones automáticas / verdadero-falsas / cortas respuestas.
Students take it in the browser; the system scores it the moment they
hit submit. Puedes configurar el porcentaje de paso y el máximo de intentos en
el propio Cuestionario. La mayoría de los cuestionarios no necesitan ninguna calificación por parte del instructor, pero si
ha añadido preguntas abiertas, esos terrenos en la vista de Envío de Exámenes
para que anotes.

> **Usa esto para:** comprobaciones semanales, perforaciones vocabularias,
> cuestionarios de lectura-confirmación, cualquier cosa en la que la respuesta sea mecánicamente
> correcta o incorrecta.

### Tarea

Un documento o archivo que el estudiante escribe y carga (PDF, documento, imagen, URL,
o texto). Students see a prompt in the lesson, write or attach their
answer, and submit. A continuación, abre cada Envío de Asignaciones, leerlo,
e introduce una puntuación más comentarios escritos.

> **Usa esto para:** ensayos, documentos exegéticos, diarios de reflexión,
> entregables del proyecto, cualquier cosa donde el estudiante produzca algo
> que leas cuidadosamente.

### Examen

Una prueba en el navegador más elaborada, a menudo temporizada. Exams support multiple
question types (multiple choice, open-ended, file upload), time limits,
and per-question feedback. Las partes autogradables se marcan a sí mismas; las porciones
de terminación abierta están marcadas "Sin calificar" hasta que las anotes.

> **Usa esto para:** evaluaciones intermedias, finales, formales proctorizadas donde
> quieres una única experiencia de prueba lineal para el estudiante.

### Discusión

Diálogo en línea. Los estudiantes publican su posición inicial en un mensaje
y responden a sus compañeros de clase. Discussions can be **graded** (linked to an
Assessment Criterion) or **free-form** (just for engagement). Graded
discussions can require students to reply to a minimum number of
classmates' original posts; you set this on the Discussion Activity as
_"Minimum replies to other students"_. The system tracks each student's
reply count and won't mark the discussion complete until the threshold
is met.

> **Usa esto para:** conversación semanal alrededor de las lecturas, debates de estudio de casos
> , redondeadas por pares, en cualquier lugar donde la _interacción_ sea la
> aprender.

### Desconectado

El "catch-all for things you grade outside the LMS. No hay ningún documento de tipo
, no hay carga, no hay página de puntuación. Acabas de abrir el Calificador y escribe
la puntuación para cada estudiante.

> **Use this for:** chapel attendance, class participation, in-person
> presentations, oral exams, lab work, peer-evaluation scores, anything
> that lives in your notebook and you transcribe in. Crea una evaluación
> sin conexión por categoría para que los pesos aún se sumen limpiamente.

## Donde la calificación ocurre día a día

### La tarjeta To-Do (arriba a la derecha de cada página del curso)

Cada página de detalles del curso muestra una tarjeta **Hacer** a la derecha. For
instructors and academic users it lists, in plain text:

- **"Assignments to Grade — N"**, **"Exams to Grade — N"**, etc. — one
  line per activity with un-graded submissions, with the count.
- Cada línea es un acceso directo en la cola de calificación
  para esa actividad.

Esta es tu vista diaria de prueba. Abre el curso, mira la tarjeta,
haz clic en la actividad con el mayor atrasado. La tarjeta solo muestra cosas
que realmente necesitan atención, las colas vacías colapsan _"¡Felicidades!
No hay evaluaciones para calificar por ahora."_

> **Lo que NO está en la tarjeta To-Do :** Evaluaciones sin conexión. Since there's
> no submission to grade, they don't appear here. Usa las Calificaciones para
> .

### La cola de calificación (una actividad a la vez)

Al hacer clic en un objeto de la tarjeta To-Do te llevará a la página de **envíos** por actividad
. Allí ve una fila por estudiante, con su estado
de envío (No Enviado / No Calificado / Calificado), publicación original
fecha o fecha de carga, y cualquier respuesta cuenta para discusiones. Click a
student's row to open their submission, read it, type a score, leave
feedback, and save.

Este es el lugar adecuado cuando quieres centrarte en una sola evaluación
y calificarla en una sola sentada.

### El Calificador (toda la cuadrícula)

El **Calificación** (enlazado desde cada página del curso) es una sola tabla:

- **Filas:** cada estudiante en el curso.
- **Columnas:** cada criterio de evaluación, en orden, con un porcentaje
  de peso que se muestra bajo el título.
- **Publicación de calificaciones** — hacer visibles las calificaciones para los estudiantes

Tres cosas a saber:

1. **Header links.** Click any column title and you jump to that
   assessment's grading queue (the per-activity view above). El
   Calificaciones es la plataforma de lanzamiento natural cuando estás moviendo a través de
   evaluaciones en lugar de entre los estudiantes.
2. **Editar celdas directamente.** Puedes escribir una nota en cualquier celda. Este es
   el **único lugar para introducir las notas para las evaluaciones sin conexión** — no hay
   nada en el que hacer clic para ellas, ya que no hay envío. También
   funciona como anulación para los otros tipos si alguna vez necesitas nudear un grado
   después de que el envío haya sido guardado.
3. **Guarda todos los cambios.** Las ediciones se rastrean localmente hasta que hagas clic en el botón
   _Guardar todos los cambios_ en la parte superior (o pulsa `Ctrl+S`). El botón
   muestra cuántas celdas tienen ediciones sin guardar. Esto bloquea las escrituras para que
   pueda fluir a través de la cuadrícula sin guardar cada celda.

Extra-credit columns are tinted blue and show a "Max Extra: N" hint
under the title instead of a weight, so they're easy to spot.

## Una semana típica

Un ritmo común para un instructor seminario:

1. **Lunes por la mañana** - abre el curso. La tarjeta To-Do muestra
   _"Asignaciones a la calificación: 8"_. Haga clic en él, trabaje a través de las ocho
   envíos uno por uno, ahorre cada una.
2. **Semana** — el plazo de discusión pasa. La tarjeta To-Do ahora muestra
   _"Discusiones a la Igualdad: 12"_. Abrir la cola, mira la columna _"Respuestas"_
   (formato X / Y cuando se establece un mínimo) para que sepa a un vistazo
   quién alcanzó el requisito de participación y quién no. Califica a los
   que lo conocieron; contacta a los que no lo hicieron.
3. **Fin de la sesión de clase** — abre la **Gradebook**, encuentra la columna
   _"Participación de Clase"_ (sin conexión), y escribe puntuaciones para
   los estudiantes que hablaron bien. Pulsa _Guardar todos los cambios_ una vez.
4. **End of term** — open the Gradebook to see the full grid, spot any
   missing cells, fill in the last few Offline assessments, and verify
   the totals look right before publishing final grades.

## Configurando un plan de evaluación para un curso

Antes de cualquiera de los trabajos anteriores, el curso necesita que se definan los criterios de evaluación
. From a Course Schedule, click **Course Assessment** to open
the configuration page. Añadir una fila por cosa calificada en la sílice:

- Escoja el **tipo** (Quiz / Asignación / Examen / Discusión / Desconectado).
- Para tipos no sin conexión, vincule la actividad real (el ensayo específico,
  Actividad de asignación, etc.).
- Establece el **peso** (porcentaje del grado final) — o marca
  **Crédito adicional** e introduce puntos máximos, en cuyo caso el registro cuenta
  encima del 100% en lugar de contra él.
- Optionally set a **due date** — used for the To-Do card's "Due Soon"
  list and for marking late submissions.

El peso total de las filas no extra-crédito debe ser igual a **100** antes de que
pueda guardar. The page shows a running total at the top in red until you
get there.

## Consejos

- \*\*No clasifiques en el Calificador por defecto. \* Hacer clic a través de la cola
  por actividad te da la vista completa del envío (el archivo, la
  rubric, la caja de comentarios, comentarios previos). El Calibrador es para
  grados, anulaciones y barridos de final de fin.
- \*\*Usar sin conexión libremente. \* Cualquier cosa que viva en un portapapeles o en
  tu cabeza: asistencia, puntuación del examen oral, totales de evaluación de pares,
  puntuaciones rubricas de presentación — se convierte en una columna limpia en el Calificador
  en el momento en que añades un Criterio de Evaluación sin conexión.
- \*\*Una fila sin conexión por categoría. \* Una sola _"Participación"_ fila
  que combina atención, compromiso oral, y el trabajo en grupo está bien cuando
  el plan lo describe de esa manera. Dividirlos en renglones separados
  también está bien: los estudiantes ven el desglose y puedes pesar
  cada parte.
- **Discussion replies count toward "complete," not toward the grade.**
  The minimum-replies setting controls when the discussion is marked
  _complete_ on the student's outline and To-Do. The grade itself is
  whatever you enter on the Discussion Submission — you can reward
  participation with the score, deduct for missing it, or use a
  separate Offline assessment if you want to track participation
  apart from the discussion's content.

## Relacionados

- [Actividades de discusión](discussions.md) — requisitos de configuración y respuesta
- [Enrollment](enrollment.md) — quién aparece en las filas de Calificaciones
- [Withdrawal](withdrawal.md) — cómo los estudiantes retirados están representados
- [Graduation Requirements](graduation-requirements.md) — non-course
  evidence that complements graded coursework
