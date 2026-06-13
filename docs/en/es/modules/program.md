# Programas

A **Program** is the thing a student enrolls in to gain access to courses — an
M.Div, a one-year certificate, a continuing-education track. También es donde
estableces las reglas académicas y financieras que rigen a todos los inscritos en él:
cómo se mide el progreso, si cuesta dinero, lo que cuenta para graduarse en
y cómo se organizan sus cursos y especializaciones.

You author programs entirely from Desk (**Program → New**). Esta página camina
a través de las opciones y luego explica la parte que más atrae a la gente —
**pistas y énfases**.

## Cómo se forma un programa

Un puñado de opciones ortogonales definen el _carácter_ de un programa. Set these
first; everything else hangs off them.

| Opción                 | Campo                                            | Lo que decide                                                                                                                                                  |
| ---------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Nivel**              | `Nivel de programa`                              | El nivel (Certificado, Bachelor, Master, Doctorado, Continuando Ed…) y si el programa está _en curso_.                      |
| **¿Tiene un fin?**     | _(espejado)_ `Está en marcha` | Degree-style (graduación, GPA, transcripción) vs. en curso (sin fin, sin graduación).    |
| **Modelo de progreso** | `Tipo de inscripción`                            | Medido por **términos** completados (basados en el tiempo) o **créditos** ganados (basados en créditos). |
| **Admisiones**         | `Modo de inscripción`                            | Aplicar sólo durante las ventanas publicadas (temporizado) o en cualquier momento (continuar).           |
| **Costo**              | `Programa gratis` + banderas de pago             | Gratis o pagados con matriculación cerrada al pago.                                                                                            |

These are independent — a program can be _Credits-based_, _Continuous_, and
_Free_ all at once, or any other combination.

### Nivel de programa y "en curso"

A **Program Level** (Desk → Program Level) is a reusable tier you attach to a
program — _Certificate_, _Bachelor_, _Master_, _Doctorate_, _Continuing
Education_, etc. Además de categorizar el programa, lleva un interruptor
importante:

> **Está en curso** — _"Compruebe esto SÓLO si el Programa no tiene un fin definitivo (sin gradación
> , créditos, etc.). Útil para cursos gratuitos, educación continua,
> etc."_

Cuando el nivel elegido está en curso, el programa **réplicas** que como una bandera de solo lectura
`Está en ejecución` y automáticamente omite todo lo que asume un final:
auditoría y solicitudes de graduación, GPA y honores, la transición de ex becarios y la
Academy Review pasaron a retirarse. Deja el nivel no permanente para cualquier grado
real.

### Modelo de progreso — basado en tiempos vs. créditos

For degree (non-ongoing) programs, **Enrollment Type** picks how you track a
student toward completion:

- **Basado en el tiempo** — el progreso se cuenta en **términos**. Set **Terms for
  completion**. Los cursos pueden llevar un **número de término** sugerido, para que la auditoría sepa
  dónde pertenece cada uno en la secuencia.
- **Basados en créditos** — los estudiantes se inscriben en cursos en cualquier término, y el progreso es
  contabilizado en **créditos**. Establezca **Créditos para completar**.

**Máximos años para graduar** (se permiten años opcionales, `0` = sin límite)
límites de cuánto tiempo tiene un estudiante; al inscribirse el sistema estampa una fecha máxima
de graduación de _fecha de matriculación + esto muchos años_.

### Admisiones — Tiempo vs Continente

**Modo de inscripción** controla la forma en que los solicitantes consiguen:

- **Timed** — las aplicaciones son aceptadas sólo durante las ventanas publicadas
  [Term Admission](enrollment.md).
- **Continuo** — los solicitantes pueden aplicar en cualquier momento; el botón público "Aplicar" marca
  ellos al término académico actual.

### El formulario de solicitud

El botón público "Aplicar" abre un **Formulario Web** que crea un Aplicante de Estudiantes.
The built-in form is intentionally thorough (personal, education, employment,
church, doctrinal statement, signature…), which is right for a degree program but
far heavier than a free course or continuing-education track needs.

Para usar una forma más ligera, establezca **Forma Web de Aplicación** en el programa. El botón
luego abre ese formulario en su lugar. La ruta está resuelta en este orden:

1. El **Forma Web de Aplicación** del programa, si se establece.
2. **Configuración seminaria → Formulario de aplicación predeterminado**, si se establece (un valor predeterminado
   en todo el sitio para cada programa que no elija el suyo).
3. El formulario `student-applicant` incorporado, como el respaldo final.

So you can leave most programs blank and only point your free/CE programs at a
short form — or flip the _default_ and reserve the long form for the few programs
that need it.

> \*\*Construye tu propio formulario; no edites el incorporado. \* El formulario enviado
> `student-applicant` es un formulario web _estándar_ — se vuelve a sincronizar desde la aplicación
> en cada actualización, y cualquier cambio que realice en el escritorio se sobrescribirá. En su lugar,
> **crea un nuevo Formulario Web** (Escritorio → Formulario Web → Nuevo) para el doctype _Estudiante_
> con solo los campos que quieras. Tus propios formularios viven en la base de datos y
> nunca son truncados. El selector de **Formulario Web de Aplicación** solo muestra Formularios Web
> construidos en Estudiantes.

Unas pocas cosas para ponerse bien en un formulario personalizado:

- **Mantén los campos de prerelleno.** Incluye `program` y `academic_term` (y
  `term_admission` si aceptas aplicaciones temporizadas). El botón Aplicar pasa
  estos en la URL, y Frappe solo prerellena si el formulario realmente contiene
  esos campos. También necesita el `Email de Student`, ya que esto es necesario para iniciar sesión.
  **no** necesitas añadir `academic_year` — se deriva automáticamente de
  el término académico, así que déjalo fuera del formulario.
- \*\*Para la sentencia doctrinal, simplemente añade el campo de firma `signdoctrine`. \*
  La declaración Doctrinal de admisión actual se renderiza automáticamente como un bloque de solo lectura
  directamente encima de la firma en cada formulario de solicitud de estudiante
  (incorporado o personalizado) — no agregas un campo `ds2` y no escribes ningún script
  .
- **Establece su propio comportamiento de éxito.** El formulario incorporado redirige a la página
  de pago después del envío. That redirect lives on the built-in form, so a custom
  form for a **free** program won't carry it — set the new form's **Success URL**
  (or a success message) to send applicants wherever makes sense, e.g. a simple
  thank-you instead of a payment page.

### Coste y pago

- **Programa gratuito** - evita la facturación de matriculación y omite la revisión financiera en
  retiro.
- Para programas de pago, **Requiere el pago antes de inscribirse** de cada curso
  matriculación a la _Esperando Pago_ hasta que el estudiante pague (o llegue a la
  **Pago mínimo %**). **Requiere la verificación del personal de las inscripciones del curso**
  hace que un registrador apruebe el borrador de inscripciones del estudiante antes de que pueda pagar.

Los mecanismos de matriculación con compuerta de pago están cubiertos en
[Enrollment](enrollment.md).

## Cursos

La tabla **Cursos** lista todos los cursos que pertenecen al programa. For each
row:

- **Mandatory for this program** (`required`) — every student must pass it to
  graduate. Déjalo sin comprobar para **opciones**.
- **Inscribirse al programa** (`pgm_course_reqonenroll`) — el estudiante está
  **inscrito automáticamente** en este curso; nadie tiene que registrarlos manualmente.
  Esto es **separado** de _Obligatorio para este programa_ anterior: esa bandera es acerca de
  _graduándose_, esta es acerca de _registrarse_. Un curso puede ser uno, el
  otro, ambos o ninguno de ellos. Vea **Auto-matriculación de estudiantes** a continuación.
- **Créditos para este programa**: el mismo curso puede valer un número
  diferente de créditos en diferentes programas, para que los créditos en vivo sobre la fila del programa.
- **Número de término**: término sugerido, utilizado para secuenciar la auditoría.
- **Permitir más de una vez** - permitir que el curso cuente para créditos de más de
  una vez.
- **Desactivado** (+ **Razón de desactivación**) — retira un curso de este plan de estudios
  sin eliminar el historial. Students who already took it keep their record; new
  students no longer see it. Los sellos del sistema **desactivados en** automáticamente.

> **List every course here.** Even courses that only matter to one track or
> emphasis must appear in this main Courses table. The track tables below just
> point at courses that already exist here.

### Auto-matricular estudiantes en cursos

Selecciona **Mandatorio en la matriculación del programa** en un curso y los estudiantes ya no tienen
para registrarse en él — el sistema los registra para ti. This is meant for the
courses everyone in the program takes (a required orientation, a first-term core
sequence), so the registrar doesn't enroll each student one by one.

Algunas cosas que vale la pena entender _cuando_ y _cómo_ esto sucede:

- \*\*Espera una oferta. \* Un estudiante solo puede inscribirse una vez que el curso se ofrezca
  realmente, es decir, once a [Horario del Curso](enrollment.md) para ello
  está **abierto para la matriculación**. Si el curso no se ofrece en el término, el estudiante
  se inscribe, nada falla: el estudiante simplemente se inscribe más tarde, automáticamente, el
  momento en que se abre una oferta futura.
- \*\*Elege una oferta sensata. \* Cuando el curso está abierto en más de un
  lugar a la vez, el sistema prefiere una oferta en la inscripción propia del estudiante
  término, entonces una sección en línea (**Virtual**), luego la más temprana.
- **Los programas pagados todavía facturan normalmente.** "Mandatorio en la matriculación" **no**
  significa gratuito. En un programa de pago, la inscripción automática es facturada y se sienta en
  _Pago en espera_ exactamente como una inscripción hecha a mano hasta que el estudiante paga.
- \*\*Los prerrequisitos son respetados. \* Si el curso tiene un requisito obligatorio
  sin cumplir, el estudiante **no** está inscrito automáticamente; en su lugar un to-do se eleva
  para que el registrador ordene la secuencia.
- **No hay doble inscripción.** Un estudiante ya inscrito (o quien ya ha pasado)
  el curso queda solo.

> \*\*La lista se fija al momento de la inscripción. \* Los cursos en los que un estudiante es
> auto-matriculado se deciden **cuando se envía su matriculación**, desde las banderas
> tal y como están ese día. Turning the flag on for a course **later** does
> **not** reach back and enroll students who are already in the program — by
> design, so a curriculum change never silently re-enrolls an existing cohort.
>
> Para empujar un curso recientemente marcado a estudiantes que están _ya_ inscritos, abra el Programa
> y utilice **Acciones → Aplicar Mandatorio-on-Enrollment a estudiantes activos**.
> Añade el nuevo curso a la lista de cada estudiante activo y los inscribe donde una oferta
> está abierta. El botón solo aparece una vez que el programa tenga al menos un curso
> obligatorio-a-inscripción, y solo añadirá _nunca_ — nunca elimina un curso
> para el que ya estaba configurado un estudiante.

## Pistas y acentuados

Una **pista** es un grupo nombrado de cursos dentro de un programa. Tracks come in two
flavors, distinguished by one checkbox — **Program Emphasis?** — and they behave
very differently.

### Pistas organizativas (no enfatizadas)

Leave **Program Emphasis?** unchecked to use a track as a **requirement
carve-out** — a way to say _"the program requires N credits from this group of
courses."_

> Ejemplo: \*"Los estudiantes deben ganar 6 créditos de griego bíblico. \* Crea una pista
> _Griego bíblico_, establece **Créditos de pista requeridos = 6**, y liste los cursos griegos
> debajo de él (en la tabla **Cursos por pista**). El estudiante puede satisfacer
> los 6 créditos de cualquiera de esos cursos.

Las pistas organizativas son sobre la estructura **comunicándose y agrupando**.
Los estudiantes **no** los declaran; no son especializaciones en una transcripción.

### Vacíos (una especialización declarada)

Check **Program Emphasis?** to make a track a **declared concentration** — an
Old Testament emphasis, a Counseling emphasis, a Missions emphasis. Emphases are
actively tracked on the student's audit and (unless marked advisory) **gate
graduation**.

Campos clave en una pista de enfoque:

- **Requiere créditos de pista** (`addcredits`) — los créditos mínimos que el estudiante
  debe ganar dentro del enfés. Estos cuentan para el total del programa.
- **Rastrear el techo de créditos** (`max_credits`, `0` = ilimitado) — el máximo
  créditos de énfasis que cuentan para el grado. Credits beyond the cap are
  still earned, but stop counting toward the program total.
- **Declaración de Vacío** — _cuando_ el estudiante lo toma en:
  - **Al inscribirse** — debe elegirse antes de enviar la inscripción.
  - **Anytime** — may be declared later (optionally only after earning a
    **Min Credits to Declare**).
  - **Auto-concesión**: asignado automáticamente una vez que el estudiante cumpla con los requisitos de crédito de
    enfatigado.
- **Solo consultivo**: el énfasis es informativo y **no** bloquea la graduación
  .
- **¿Fallback vacío?** — marca el énfasis predeterminado (por ejemplo, _General
  Studies_) asignado a los estudiantes que nunca declaran uno específico.

Los **cursos obligatorios para énfasis** están establecidos en la tabla de **cursos por pista**
marcando **¿Mandatorio?** para un par (pista, curso). Un estudiante en ese énfasis
debe aprobar esos cursos específicos, además de cumplir el total de crédito.

### Enfoques múltiples

Si **Permitir múltiples vacíos** está activado, un estudiante puede declarar más de uno. La
**Política de Anulación de Emphasis** luego decide cómo se suman los créditos:

- **Bote de Crédito Compartido**: todos los acentos se obtienen del mismo total del programa. Un curso
  puede ayudar a satisfacer dos enfoques a la vez.
- **Additional Credits Required** — each emphasis beyond the first adds its
  track credits _on top of_ the program total, so a double emphasis genuinely
  costs more credits.

### Ejemplos prácticos

**1 — Un requisito de idioma (pista organizacional).**
_Objetivo: 6 créditos del curso griego, la elección del estudiante._
Seguir a _griego bíblico_, **¿programa vacío? off**, **Créditos de pista requeridos =
6**; lista los cursos de griego elegibles en cursos por pista. La pista documenta
el requisito y agrupa los cursos; el estudiante elige cualquier valor de 6 créditos.

**2 — An Old Testament emphasis declared up front.**
_Goal: students choose OT at enrollment, take 12 emphasis credits including two
required courses._
Track _Old Testament_, **Program Emphasis? on**, **Se requieren créditos de seguimiento = 12**,
**Declaración de vacío = inscripción**. En cursos por pista, añade los cursos de OT
y marca **¿Mandatorio?** en _hebreo I_ y _OT Teology_. El estudiante debe
elegir este enfoque, antes de presentar la inscripción, pasar ambos cursos requeridos,
y alcanzar 12 créditos OT.

**3 — A counseling emphasis declared later.**
Same as above but **Emphasis Declaration = Anytime** and **Min Credits to
Declare = 30** — the student can pick it up only after 30 program credits.

**4 — Enfoque Auto-otorgado.**
Establece **Declaración de Vacío = Auto-concesión**. The student never declares it; once
they have met the track's credit requirement, the system records the emphasis
for them.

**5 — Enfoque doble que cuesta más.**
Activa **Permitir múltiples vacíos** y establece **Política de Anulación de Vacíos =
Créditos adicionales requeridos**. A student who declares both _Old Testament_ and
_Missions_ must complete the program total **plus** the second emphasis's track
credits.

**6 — Un enfoque.**
Crear _Estudios Generales_, ¿pulsar **Programa de Emphasis?** y **Fallback Emphasis?**.
Los estudiantes que nunca declaran nada más son tratados como si estuvieran en Estudios Generales
para su graduación.

## GPA, honores y graduación

Para programas de grados:

- **Bases para GPA** — la parte superior de tu escala (US = 4.0; otros variares).
- **AGA ponderada en crédito** cuando está encendido, el APG se mide por los créditos del curso; cuando está desconectado,
  es un promedio simple.
- **Aceptar las calificaciones de transferencia en GPA** - si las notas de los cursos transferidos cuentan en
  GPA (también requiere el seminario del socio fuente para permitirlo).
- **Niveles de Honor** — una lista de nombres de honor con GPA mínimos (por ejemplo, _Cum Laude_
  a 3.5). El nivel más alto que un estudiante califica para espectáculos en su inscripción.
- **Students Can Request Graduation** + **Graduation Request Trigger** (_Enrolled
  in final courses_ vs. _Passed final courses_) — whether and when a student can
  file a [Graduation Request](graduation-request.md) from their audit page.

Los requerimientos que no son del curso que un programa requiere (letras, capillos, proyectos, etc.)
están configurados por separado — vea [Requisitos de Graduación](graduation-requirements.md).

## Publicación en la web

La pestaña **Web** controla la página pública del programa: **Ruta** (URL slug),
**Blurb** e imágenes para la lista del programa, **Descripción del programa** y
**Requisitos**, campos de duración para ordenar/filtrar, y dos interruptores
: **Mostrar Inscripción de Windows en Web** y **Mostrar Aplicar CTA en Web**
(ambos por defecto; el CTA no tiene efecto para los programas continuos, que se aplican
en cualquier momento). Desmarca **Publicar en la web** para ocultar un programa por completo.

## Cómo se muestra todo en la auditoría del programa

Everything above converges on the **Program Audit** page (also visible to
staff). Para cada estudiante inscrito se muestra:

- **Crédito / término de progreso** hacia el total del programa.
- **Programar cursos obligatorios** y su estado.
- **Cada énfasis declarado**: los créditos requeridos vs. ganados (respetando la terminación
  ) y cualquier curso de pista obligatoria aún faltante.
- Los **Requisitos de Graduación** paralelos (evidencia no curativa).

Un estudiante es _elegible para graduarse_ sólo cuando se cumpla el total del crédito/término, se pasan todos los cursos obligatorios de
, cada énfasis no consultivo ha cumplido con sus
créditos y cursos requeridos, y los requisitos de graduación son claros.

## Referencia rápida

| Si quieres…                                                                                                                                                                                                      | Haga esto                                                                                                                                                                                                                      |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Crear un programa de grado                                                                                                                                                                                       | Nuevo Programa; elige un nivel de programa no continuo; establece el tipo de inscripción + términos/créditos para completar                                                                                                    |
| Crea una oferta sin fin (p.ej., una página de cursos gratis en el sitio web para entrenar creadores y servir como herramienta de marketing para el seminario) | Usa un nivel de programa con **está en curso**; marca **Programa Gratis** (a menudo, modo de inscripción = continuo)                                                                                        |
| Rastrear el progreso por créditos, cualquier pedido                                                                                                                                                              | Tipo de inscripción = **Basado en créditos**; establecer créditos para completar                                                                                                                                               |
| Marcar un curso requerido para todos                                                                                                                                                                             | Marca **Mandatorio para este programa** en su fila de cursos                                                                                                                                                                   |
| Inscríbete automáticamente a todos los estudiantes en un curso                                                                                                                                                   | Tick **Mandatory on program enrollment** en su fila de cursos                                                                                                                                                                  |
| Aplicar un curso de automatriculación marcado recientemente a los estudiantes actuales                                                                                                                           | Programa → **Acciones → Aplicar Mandatory-on-Enrollment a los estudiantes activos**                                                                                                                                            |
| Retire un curso del currículo                                                                                                                                                                                    | Tick **Desactivado** en su fila de cursos y dar una razón                                                                                                                                                                      |
| Requiere N créditos de un grupo de cursos                                                                                                                                                                        | Añadir un track organizacional (Programa Vacío? **apagado**) con **Créditos de pista requeridos**                                                                                                           |
| Ofrecer una especialización declarada                                                                                                                                                                            | ¿Añadir una pista con **programa vacío? en**; establecer créditos, cursos requeridos y tiempo de declaración                                                                                                                   |
| Permitir que los estudiantes declaren dos especializaciones                                                                                                                                                      | **Permitir múltiples vacíos**; elige una **Política de Anulación de Vacío**                                                                                                                                                    |
| Dar un valor predeterminado a los estudiantes no declarados                                                                                                                                                      | Marcar un énfasis como **¿Vacío de Fallback?**                                                                                                                                                                                 |
| Permitir a los estudiantes aplicar la ronda                                                                                                                                                                      | Modo de inscripción = **Continuo**                                                                                                                                                                                             |
| Utilizar una aplicación más corta para un programa libre/CE                                                                                                                                                      | Construye un Formulario Web con el _Aplicador de Estudiantes_; póngalo como el **Formulario Web de Aplicación** del programa (o el **Formulario Web de Aplicación** por defecto en Configuración Seminaria) |
| Mostrar el programa (y el botón Aplicar) públicamente                                                                                                                                         | Pestaña Web → **Publicar en web**, **Mostrar aplicar CTA en Web**                                                                                                                                                              |

## Relacionados

- [Enrollment](enrollment.md) — how students enroll, and payment-gated course
  enrollment for paid programs.
- [Requisitos de Graduación](graduation-requirements.md) — los requisitos
  que no son del curso (letras, capellas, proyectos) que se sientan junto a los cursos.
- [Solicitud de Graduación](graduation-request.md) — el flujo de solicitud y aprobación.
- [Calendario Académico](academic-calendar.md) — términos y ventanas de inscripción
  que abren cursos para el registro.
