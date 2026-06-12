# Habitaciones e instalaciones

Planificar un término es realmente un problema que coincide: el curso correcto, en una habitación
que es lo suficientemente grande, tiene lo que el curso necesita, y no está ya tomado. Las herramientas
**Habitaciones y Servicios** lo convierten de conjeturas en algo que puedes ver
y confianza. You describe your spaces once — what each room _has_ and how many it
_seats_ — describe what each kind of course _needs_, and from then on the system
helps you place sections, keeps a room from being double-booked, manages a
**waitlist** when a section fills, and shows you at a glance which rooms are busy,
which are free, and where demand outran the seats you have.

Todo aquí es **opcional y progresivo**. Un seminario de dos salas puede ignorar
casi todo y nada cambia. Una escuela multicampus puede modelar cada edificio
, ajustar características a los requisitos y rastrear el equipo en cada habitación
como activos. Enciende sólo lo que te ayuda.

## Descripción general

Hay algunos bloques de construcción. La mayoría de los seminarios utilizan un subet. Ten en cuenta que una habitación
**tiene** características y un tipo de curso **requieren** características de la misma lista
— ese vocabulario compartido es lo que permite al sistema coincidir con ellas.

```mermaid
flowchart TD
    Campus["Campus"] --> Edificio["Edificio"] --> Sala ["Sala "]
    Sala -->|"tiene"| RF["Características de cuarto"]
    Tipo de Curso["Tipo de Curso"] -->|"requiere, por modalidad"| RF
    Curso["Curso"] -->|"es un"| Curso Tipo
    Sala --> CS["Programación del curso (sección + capa)"]
    Curso --> CS
    CS -->|"rellenar"| Lista de espera["Lista de espera"]
    CS --> Informes["Informes: Utilización, Lista de espera, Demanda Incumplida"]
```

- Un **Salón** es tu unidad básica: un espacio con un nombre, un número, una \*\*capacidad de asientos
  \*\* y una lista de **características**.
- **Campus** y **Edificio** son contenedores opcionales por encima de la habitación, para escuelas multisitio
  y para filtrado de marea ("habitaciones en la Biblioteca").
- Las **Características de las Habitaciones** son un vocabulario compartido de lo que ofrece una habitación. The same
  vocabulary describes what a **Course Type** requires, so the two can be matched.
- Un **Horario del curso** (una sección) se coloca en una habitación y lleva un **asiento
  cap**; una vez que está lleno, los estudiantes se unen a una **lista de espera**.

## La jerarquía de instalaciones (Campus → Construcción → Salón)

No tienes que modelar edificios o campuses. Una habitación puede estar sola. Pero
si tienes más de un sitio — o simplemente quieres que "habitaciones en el Salón de Chapel" sea una cosa
— construye la jerarquía arriba hacia abajo.

### Campus

**Desk → Campus → Nuevo.** Un campus es un sitio físico del seminario.

- \*\*Nombre del Campus \*\*— lo que la gente llama (_Campus Principal_, _Extensión de Downntown_).
- **Abreviación** — etiqueta corta opcional.
- **Zona horaria** — informativa por ahora. Graba la zona horaria del campus pero
  **no** cambia aún las ventanas de asistencia/chapel de facturación, que siguen la zona horaria de la
  (ver [Attendance](attendance.md)). Está ahí así que el registro está
  listo para el futuro.
- **Activo**: desmarca la marca para retirar un campus sin eliminar su historial.

### Edificio

**Escritorio → Edificio → Nuevo.** Un edificio pertenece a un campus.

- **Nombre del edificio** — _Biblioteca_, _Sala del Chapel_. El mismo nombre puede repetirse en campuses
  .
- **Campus** — en qué campus se sienta.
- **Accesible**: una bandera rápida para el acceso sin pasos.

### Sala

\*\*Escritorio → Sala → Nuevo. \* Más allá de lo básico (nombre, número, **capacidad de asiento**,
accesible), una habitación puede nombrar su **edificio** — su **campus** y luego rellenar
automáticamente — y listar sus **Características de Habitación**. La capacidad es el número que conduce los límites de asiento
y los controles "¿es esta habitación lo suficientemente grande?", por lo que vale la pena mantener
preciso.

## Qué habitación tiene, qué necesita un curso

Este es el emparejamiento que hace posible la programación inteligente: describe las salas y los cursos
en las _mismas palabras_, y el sistema puede decirte cuándo una habitación es un mal
encaja.

### Características de la habitación, qué habitación tiene

Una **Característica de la habitación** (Escritorio → Característica de la habitación) es una capacidad que una habitación puede ofrecer:
_Proyecto_, _Sistema de sonido_, _Piano_, _Placa blanca_, _Accesible en silla de rueda_, y
así sucesivamente. Cada una lleva una **Categoría** (Equipamiento AV, Musical, Configuración del Salón,
Especializado) para agrupación de mareas. Se proporciona un set de inicio; añade el tuyo libremente.

En cada **sala**, lista las características que realmente tiene en la tabla **Características de la habitación**
. Ese es el perfil de la habitación.

> \*\*La accesibilidad también es una característica. \* Marcar una habitación _Accesible para silla de ruedas_ como una función
> (no solo la vieja bandera de sí/no) permite que un curso _requiere_ que lo vea a continuación.

### Tipo de curso — lo que un curso necesita

Un **tipo de curso** (Escritorio → Tipo de curso) agrupa cursos según lo que requieran de una habitación
. Dentro de ella, las listas de **Requerimientos** de la tabla, por **modalidad**, las
**Características de la habitación** que la modalidad necesita:

| Modalidad  | Característica de la sala requerida |
| ---------- | ----------------------------------- |
| Todos      | Proyector                           |
| Presencial | Tabla blanca                        |
| Hibrida    | Sistema de sonido                   |

_Todos_ aplica a cada modalidad; las filas específicas le agregan. Así que una sección Presencial
de este tipo de curso necesita un Proyector **y** una pizarra.

En cada **Curso**, establece su **Tipo de Curso**. A partir de entonces, cada sección de ese curso
sabe lo que necesita, y el selector de habitación lo utiliza.

If a course has no Course Type, or a Course Type has no requirements, nothing is
lost — the matching simply stays quiet. Añade requisitos sólo cuando ellos ayuden.

## Colocando una sección en una habitación

When you set the **Room** on a Course Schedule, the system works for you in three
ways.

### Un selector de habitación mejor ajustado

El menú desplegable de la sala **se encarga de poner el mejor ajuste primero** y anota cada opción
, por lo que no estás cogiendo cegado. Una fila lee algo como:

```
Chapel Hall 101 · cap 60 · ✓ ajusta · free
Sala 204 · cap 30 · Falta 1 · ocupado
```

- **capa** - capacidad de asientos de la habitación.
- **✓ cabe / falta N** - si la habitación tiene las características del tipo
  de este curso requiere para esta modalidad.
- **gratis/ocupado** - si la sala ya está reservada durante el horario de reuniones
  de esta sección.

Habitaciones que son gratuitas, adaptadas y grandes flotan en la parte superior. Nada está oculto —
todavía puede elegir cualquier habitación, pero las buenas opciones son obvias.

### Advertencias y paradas duras

Al guardar, el sistema distingue "puede querer saber" de "esto no puede ser":

- **Falta una función requerida → una advertencia.** Te dicen que la habitación carece de
  algo por lo que el tipo de curso solicitó (e. . "Proyector faltante"), pero el guardado
  pasa. A veces un sustituto está bien, y usted está a cargo.
- \*\*Reserva doble → bloqueada. \* Si la habitación ya está reservada por otra sección
  a una hora de superposición en una fecha compartida, el guardado se detiene, nombrando el conflicto
  . Las clases de back-to-back (una termina como el siguiente comienzo) están bien.
- **Habitación demasiado pequeña → bloqueada.** No se puede mover una sección a una habitación con asientos
  menos de lo que ya se ha inscrito.

### Cambiando salas, en el registro

Use el botón **Cambiar sala** de un horario del curso para mover una sección. Pide
por la nueva habitación **y una razón**, y graba tanto en la **Sala
Cambio de registro** de la sección con quién lo cambió como cuando — por lo que un cambio intermedio ("proyector
rompió en 204") deja una pista. Moving a section to a **bigger** room also lets
the waitlist promote into the new seats automatically.

## Capacidad y lista de espera

This is where rooms stop being decoration and start protecting you from
over-enrollment.

### El límite de asiento

Cada Horario del Curso tiene una **Inscripción Máxima**. Cuando elijas una habitación, it
**por defecto de la capacidad de asientos de esa habitación** — pero puedes sobrescribirla (un seminario
limitado a las 12 en una sala de 30 asientos) o despejarla (sin cápsula). Deje en blanco y
la sección no tiene límite y la lista de espera se mantiene inactiva.

Paralelamente, la sección muestra tres números en vivo:

- **Seats Used** — students who hold a seat (enrolled, plus those who've been
  invoiced and are paying).
- **Inscripciones** - demanda total, incluyendo borradores y lista de espera.
- **Lista de espera** — cuántos están en cola.

### Uniéndose a la lista de espera

Cuando una sección está llena, un estudiante que se inscribe se coloca en la **lista de espera**
en lugar de ocupar un asiento — ven un estado de **lista de espera** y su **posición**
(#1, #2…). No se levanta ninguna factura para un estudiante en la lista de espera; están manteniendo un lugar
en la línea, no un asiento.

### Promoción automática

The moment a seat frees up — someone withdraws, an unpaid seat is released, you
raise the cap, or you move the section to a bigger room — the **next student on
the waitlist is promoted automatically**. Ellos (y usted, el registrador) son
notificados. For a paid course, promotion raises their invoice; for a free one, they
go straight in. La promoción es la primera vez que llegan, lo primero que sirve cuando se unen.

### Cuando la línea no se limpia: "Sin asiento"

Si la inscripción se cierra mientras los estudiantes todavía están esperando, esos estudiantes se mueven a un estado de
terminal **Desasiento**. Eso no es un retiro — nunca se sentaron —
es simplemente el registro honesto en el que querían y la habitación no podía sostener
. Da poder al informe de la **Demanda Incumplida**, tu evidencia de "necesitamos una habitación
mayor o una segunda sección".

> **Por qué importa esto.** Antes, un curso completo sobrecargado en silencio o
> volvió a los estudiantes sin rastro. Ahora se respeta la capacidad, la cola es
> justa y automática, y se cuenta a todos los estudiantes que no pudieron obtener un asiento.

## Ver todo el término: informes

Three Desk reports (each filterable by Academic Term) turn all of this into a
registrar's-eye view.

- **Uso de la habitación** — cada habitación con las secciones programadas en ella, sus días y horas
  y asientos vs. capacity — **más habitaciones sin secciones**, así que
  espacios vacíos son visibles. Esta es tu herramienta para enrollar secciones cuando
  una habitación está atascada y otra está inactiva.
- **Secciones en lista de espera** — cada sección que actualmente tiene una lista de espera, con su límite
  , asientos utilizados, longitud de la lista de espera y demanda total. Tu lista corta para "¿dónde
  necesitamos una habitación más grande u otra sección?"
- **Demanda Incumplida**: estudiantes que esperaron pero nunca obtuvieron un asiento (dessentado),
  agrupado por sección. El número duro detrás de una solicitud de más espacio.

## Equipo de seguimiento: Integración de activos

If your seminary tracks **Assets** (ERPNext's fixed-asset register — the actual
projector unit, the piano, the lab kit), every asset must live in a _location_.
Para que eso no se esfuerce, el seminario **espeja su Campus → Creando → Sala
jerarquía en el árbol de ubicación de activos automáticamente**. Create a room, and a
matching location appears under its building and campus; an asset can then be
placed "in" that room with no parallel bookkeeping.

Esto se controla en **Configuración Seminaria → Instalaciones y Activos**:

- **Sincronizar salas para ubicaciones de activos** — activadas de forma predeterminada. Si no registras activos,
  apaga y no se crean ubicaciones. Actívalo de nuevo y los campuses, edificios y habitaciones
  existentes son rellenados.
- **Ubicación de recursos raíz** — opcional. Donde tus espacios cuelgan en la ubicación
  árbol. Déjalo en blanco para usar una raíz de "Lugares seminarios" creada automáticamente, o apunta
  a una ubicación que ya usas.

El espejo es de un solo sentido (sus habitaciones conducen las ubicaciones, nunca el reverso), y nunca
elimina un lugar que todavía tiene un activo. Un buen efecto secundario: porque las _características_ de una habitación
y sus _activos_ ahora comparten un lugar, puedes conciliar "salas
que deben tener un proyector" con "habitaciones que realmente tienen una".

## Ejemplos prácticos

### Ejemplo 1 — Un curso de música que necesita un piano

**Objetivo:** cada sección de _Hymnody_ debe colocarse en una habitación con un piano, y
quieres ser advertido si no lo es.

1. **Haz la función.** Escritorio → Característica de la sala → confirmar la existencia de _Piano_ (Categoría
   _Música_).
2. **Etiqueta las habitaciones.** En cada habitación que tiene una, añade _Piano_ a sus características.
3. **Describe la necesidad.** Escritorio → Tipo de curso → _Música_ → Requisitos: modalidad
   _Todos_ → _Piano_. Establece el **Tipo de curso** del curso de _Hymnody_ a _Música_.
4. \*\*Programarlo. \* Cuando configuras la habitación en una sección de Hymnody, El selector muestra
   _✓ fits_ para salas de piano y _falta 1_ para el resto. Elige una sala
   que no sea pianista y recibirás una advertencia despedida, tu llamada.

### Ejemplo 2 — Un electivo popular se llena

**Objetivo:** _Intro to Counseling_ tiene 25 asientos; esperas más interés.

1. **Ábrelo.** En la sección, la habitación es una habitación de 25 asientos, por lo que el **Inscripción Máxima**
   por defecto es 25.
2. **Llena.** El 26º estudiante se inscribe y es **Esperado #1**; el 27º es
   **#2**. No se han recaudado facturas para ellos.
3. **Un asiento abierto.** Un retiro de estudiante sentado. **#1 es promovido
   automáticamente**, facturado (es un curso de pago), y tanto ellos como tú eres
   notificado. **#2** se convierte en **#1**.
4. **Decides aumentarlo.** Mueves la sección a una sala de 40 asientos con
   **Cambio de espacio** (razón: "movido a la Sala 300 por capacidad"). La lista de espera
   promueve en los nuevos asientos hasta que se despeje o la sala esté llena de nuevo.
5. **Comienza el término.** Cualquiera que todavía esté esperando se convierte en **sin asiento** y aparece en
   **Demanda Incumplida**: tu caso para una segunda sección el año que viene.

### Ejemplo 3 — Se abre un segundo campus

**Objetivo:** modelo un nuevo campus de Downntown y rastrea su equipamiento.

1. Crea un **campo** _Abajo_, luego **Edificio** _Annex_ (campus _Abajo_),
   y luego **Descenso** con el Edificio _Annex_: el Campus de cada habitación se rellena como
   _Abajo_.
2. Con **Sincronizar salas para ubicaciones de activos**, las ubicaciones coincidentes aparecen en
   _Bajada → Annex_ automáticamente.
3. Registra los proyectores y pianos de Annex como **Activos**, colocando cada uno en la ubicación de su habitación
   . Ahora el equipo, las características y la programación de toda la línea.

## Día a día para el registrador

- **Agregue una habitación.** Escritorio → Habitación → Nuevo. Establecer capacidad y características; opcionalmente un edificio
  . Eso es suficiente para empezar a programar contra él.
- **Schedule a section.** On the Course Schedule, pick the **Room** (use the
  ranked picker), confirm **Max Enrollment**, and save. Advertencias de atención; conflictos
  y movimientos de gran tamaño están bloqueados.
- \*\*Encuentra una habitación gratuita en un momento dado. \* Abre **Uso de la habitación** para el término y
  escanea habitaciones con huecos (o sin secciones en absoluto).
- \*\*Gestionar demanda. \* Comprueba **Secciones en lista de espera** durante el registro; cuando una sección
  se haya sobre-suscrito, suba el mayor, muévelo a una habitación más grande o abra una sección
  nueva. La lista de espera se promueve a sí misma a medida que aparecen los asientos.
- **Mueve una sección.** Usa **Cambio de espacio** (con una razón) — nunca simplemente vacíe el campo
  , así que el movimiento se registra.
- **Justifica más espacio.** Trae **Demanda Incumplida** a la conversación de planificación.

## Referencia rápida

| Si desea... | Haga esto                                                                                                  |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Añadir un espacio                                           | Crear una sala (fijar capacidad de asientos)                                            |
| Salas de grupo por sitio                                    | Crea un campus y un edificio, luego establece el edificio de la habitación                                 |
| Diga lo que ofrece una sala                                 | Añadir características de la sala                                                                          |
| Decir lo que necesita un curso                              | Establece el tipo de curso del curso; añade requisitos (modalidad → característica)     |
| Coloca una sección                                          | Establece la sala en el horario del curso (el selector clasifica mejor primero)         |
| Captura de una sección                                      | Establecer la inscripción máxima (por defecto en la habitación; en blanco = sin límite) |
| Evitar doble reserva                                        | Nada — las reservas superpuestas de la misma habitación están bloqueadas al ahorrar                        |
| Mover una sección, en el registro                           | Usa **Cambiar salón** y da una razón                                                                       |
| Permitir a los estudiantes en cola de cursos completa       | Sólo inscríbete más allá del límite — los extras se esperan y se promocionan automáticamente               |
| Ver quién fue rechazado                                     | Ejecutar el informe **Demanda Incumplida**                                                                 |
| Encontrar habitaciones gratis vs. ocupadas  | Ejecutar el informe de **Utilización de Habitaciones**                                                     |
| Rastrear equipo en salas                                    | Mantén **Sync rooms to Asset Locations** encendido; registra Activos en la ubicación de cada habitación    |
| Saltar todo esto                                            | Deja los Tipos, características y límites del curso vacíos; desactiva la configuración de sincronización   |

## Relacionados

- [Enrollment](enrollment.md) — how students enroll, and how waitlist promotion
  and unpaid-seat release fit the enrollment lifecycle.
- [Attendance](attendance.md) — ventanas de hora de check-in y la nota de zona horaria
  detrás de la zona horaria (informativa).
- [Rol de usuario](../administration/user-roles.md) — quién puede administrar habitaciones, tipos de curso
  y programas.
