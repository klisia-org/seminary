# Asistencia

A los seminarios les importa la presencia — muchos programas requieren que los estudiantes realmente sean
en la habitación, y la acreditación a menudo depende de ella. The **Attendance** module
covers the whole arc: **recording** who was Present, Tardy, or Absent at each
class meeting (by the instructor, or by students themselves with a check-in
code), turning that into a **standing** against a per-course absence limit,
**warning** everyone before a student is in trouble, and — when a seminary's
policy calls for it — letting the registrar **fail a student for absences** even
when their scores would otherwise pass. Al igual que el resto del sistema, nada
falla a un estudiante automáticamente: el límite eleva las banderas y envía advertencias, y un
humano hace la llamada.

## Descripción general

La asistencia tiene **cuatro capas**, cada edificio en la precedente:

```
1. Captura — marca Presente/Tardía/Ausencia por reunión (instructor o autofacturación)
2. Política — cuántas ausencias están permitidas (límite de programa → por curso)
3. De pie — cada estudiante se ejecuta cuánta vs. su límite, con advertencias
4. Por lo tanto — el registrador "Fail for absence" (FA), un paso humano deliberado
```

- La **captura** ocurre en la página de asistencia del curso, en una hoja impresa o
  a través del **autoentrada** del estudiante con un código de rotación por reunión.
- **Policy** is set once at the Program level as a percentage and resolves to a
  concrete number of allowed absences on each Course Schedule.
- **Standing** is computed for every student and shown to them (on their course
  status), to instructors (on the attendance page), and to the registrar (in a
  cross-course report), with notifications when a student nears or crosses the
  limit.
- La **carencia** —falla en las ausencias— nunca es automática. Es una acción de registrador
  que marca un grado especial **FA**.

## Capturando la asistencia

El instructor abre **asistencia** desde un curso y ve la lista de clases con
un control tripartito para cada alumno: **Present**, **Tardía**, o **Ausente**.
Elija una fecha de reunión a la izquierda, marque a todos y guárdela. A running
**Absences (used / allowed)** column shows each student's standing at a glance,
coloured amber when they're at risk and red when they're over the limit (this
column only appears once an absence limit is in force — see
[Policy](#the-absence-policy)).

> **Tardía es un estado de primera clase.** No es solo una nota: los tardies pueden contar
> hacia el límite de ausencia a una tasa configurable (e. . 3 tardies = 1 ausencia),
> así que marcar a alguien Tardía en lugar de ausente es significativo.

### La hoja imprimible

Para aulas en las que no es práctico prestar asistencia en una pantalla, un botón **Imprimir
hoja en blanco** produce una lista limpia — nombres de estudiantes con cajas vacías
Presente / Tardía / Ausente y una línea de firma. Imprimirlo, marque a mano
durante la clase, y llévalo más tarde. La hoja se genera a partir de la lista viva,
así que siempre es actual.

## Autofacturación del estudiante

En lugar de (o de lado ojo) el instructor que marca a todos, los estudiantes pueden registrar
su propia asistencia. The instructor projects a short **check-in code** (and/or
a QR code), students enter it from their phones, and a Present (or Tardy) record
is created for them.

### Mostrar el código

En la página de asistencia, **Mostrar código de facturación** genera un código
corto, legible por humanos para la reunión seleccionada (e. . `9WBH5`) y lo muestra grande en la pantalla,
junto con un **código QR**. El QR enlaza a los estudiantes directamente a la página
de check-in con el curso, fecha, y código ya completado, así que escanearlo es la ruta
más rápida; escribir el código es la reserva. El código se genera bajo demanda
y se mantiene estable para esa reunión.

### Comprobando

Los estudiantes facturan desde **Marcar mi asistencia** en su tarjeta de curso, o por
escaneando el QR (que abre la página de facturación). Lo que ven depende de la configuración de la **ventana de tiempo** del seminario
(abajo):

- **Ventana de tiempo aplicada (recomendada):** el sistema selecciona automáticamente la reunión
  que ocurre _ahora mismo_ y registra la asistencia con un solo toque o solicita el código
  . Un estudiante que ingresa después del periodo de gracia está marcado **Tardía**
  automáticamente.
- **Ventana de tiempo no aplicada (modo de recuperación):** el estudiante elige cualquier reunión pasada
  para la que no tenga asistencia. No clock, no code — useful when you can't
  rely on the server clock matching local class times.

> **El reloj importa.** El check-in de la ventana de tiempo compara "ahora" con la hora programada de la reunión
> **en la zona horaria del sitio** (Configuración del sistema → Zona
> ). Si la zona horaria de tu sitio no coincide donde las clases ocurren realmente, una clase
> puede leer como "cerrada". Cuando esté en duda, configure correctamente la zona horaria
> del sitio, o desactive la ventana y utilice el modo de recuperación.

### Ajustes de autofacturación

Todos bajo **Configuración Seminaria → Autoverificación de Asistencia al Curso**:

| Ajustes                                                        | Qué hace                                                                                                                                                                                                                                          |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Forzar ventana de hora de la reunión**                       | On = selección automática basada en el tiempo (ventana + código + Tardy aplicar). Apagado = modo de puesta al día (elegir cualquier reunión pasada; sin reloj, sin código). |
| **Requiere código de facturación**                             | Los estudiantes deben escribir el código de la reunión para registrarse.                                                                                                                                                          |
| **Abre el check-in antes de (minutos)**     | Cuanto temprano se abre la ventana antes de que comience la reunión.                                                                                                                                                              |
| **Closes de Check-in después de (minutos)** | Cuán tarde permanecerá abierta la ventana después del final de la reunión.                                                                                                                                                        |
| **Tardy After (mins)**                      | Período de gracia después del inicio; un check-in más tarde se registra **Tardía**. `0` = nunca auto-Tardy.                                                                                                       |

Las autocomprobaciones solo marcan **Present** o **Tardía**: el instructor todavía
revisa la lista y finaliza cualquier escasez.

## La política de ausencia

Un seminario expresa su regla como un **porcentaje de reuniones que un estudiante puede perder**,
y el sistema lo convierte en un número de hormigón para cada curso.

### Tres lugares, un número

1. **Predeterminado para todo el seminario — Configuración seminaria → Política de asistencia:**
   - **Tardies per Absence** (default **3**) — how many tardies equal one
     absence toward the limit. `0` desactiva la conversión.
   - **Advertencia dentro (ausencias del límite)** (por defecto **1**) — cuán cerca del límite
     debe estar un estudiante antes de que estén marcados "en riesgo".
2. **Programa → Política de asistencia → ausencia máxima predeterminada %** — la política en sí,
   p.e. **20%**. `0` significa "no hay límite de asistencia por defecto para este programa".
3. **Programación del curso → Política de asistencia** — donde el porcentaje se convierte en un número
   . Editable \*\*solo por el registrador/programa (los instructores lo ven
   solo lectura):
   - **Auto (de programa)** — límite = ronda( el programa del estudiante % ×
     reuniones programadas ).
   - **Personalizado**: un número fijo de ausencias que se aplican a todos en el curso
     .
   - **Desactivado**: no hay límite de asistencia para este curso.

> \*\*El límite es por estudiante, a propósito. \* Un curso no pertenece a un solo programa
> : diferentes estudiantes de la misma clase pueden estar en diferentes programas
> con diferentes porcentajes. Así que en **Auto**, el número permitido de cada estudiante es
> calculado a partir del porcentaje _de su propio programa_. Un curso de 14 reuniones con una regla de programa de 20%
> da a esos estudiantes un límite de **3** (20% × 14 = 2. → 3); un alumno
> de un programa de 10% en la misma clase recibe **2**. **Custom** and
> **Disabled** apply uniformly to everyone.

> **Virtual courses are exempt by default.** When a course's **Modality** is
> _Virtual_ and the policy is _Auto_, the limit is automatically disabled —
> online courses often have only one or two listed meetings, which would make a
> percentage meaningless. Los cursos _Presenciales_ y _Hybrid_ mantienen el límite.

### Lo que cuenta como ausencia

- **Ausencias efectivas** = registros de **ausencia** registrados **+** (tardies
  _Tardies por ausencia_, redondeados hacia abajo). Con el valor predeterminado de 3, un estudiante con 4
  verdaderas ausencias y 6 tardies tiene un total efectivo de **4 + 2 = 6**.
- **Se excluye la licencia aprobada.** Un registro ausente vinculado a una solicitud de abandono del estudiante aprobada
  (enviado) **no** cuenta para el límite.
- **Auditors are exempt.** Students auditing a course (not graded) are never
  flagged.
- The denominator is the course's **scheduled meetings**, so the allowed number
  is stable from the first day — even before all attendance has been taken. (El límite
  se recalcula automáticamente cuando añades fechas de reuniones más tarde.)

## Mono, advertencias y notificaciones

Once a limit is in force, every student gets a **standing** that updates as
attendance is recorded:

- **En riesgo** — dentro de la banda de advertencia (p.e. con un límite de 3 y un buffer de
  1, un estudiante alcanza "en riesgo" en 2 ausencias efectivas).
- **Sobre el límite** - más allá del número permitido.

Donde aparece el pie:

- **Los estudiantes** ven un panel de **asistencia** en la página de estado de su curso —
  "_X de Y ausencias usadas_" — más un estandarte ámbar cuando esté en riesgo y uno rojo cuando
  supere el límite.
- **Instructores** ver la columna por estudiante **Ausencias (X / Y)** en la página
  de asistencia, colorida por el pie.
- **Registrar / Programa** recibe el informe
  (Desk) de **Estudiantes en riesgo de asistencia**: cada estudiante en riesgo y sobre-límite en todos los cursos, con su
  contador, límite y estado.

\*\*Las notificaciones se disparan una vez por cruce. \* Cuando un estudiante entra por primera vez en la banda de advertencia
, y de nuevo cuando cruzan por primera vez el límite, una notificación va a los \*\*instructor(es)
\*\*, el **registrador/programa**, y el **estudiante**. Cada
dispara una vez, corregir la asistencia de vuelta no hará spam a nadie y la alerta
no se repetirá en la próxima recalificación nocturna.

## Fallo en ausencias (FA)

Some programs fail a student who misses too many classes **regardless of their
grades**. This is a deliberate, registrar-driven step — the absence limit only
_flags_; failing is a human decision.

### Configurando el código de grado FA

En la **Escala de Calificación** (Escalera → Escala de calificación) dos campos, junto a las notas
retirada/retirada:

- **Código para el fallo en las ausencias** (por defecto **FA**) — el código de grado marcado en
  la transcripción cuando un estudiante falló en las ausencias.
- **Considere la FA en GPA** — si la fila de la FA cuenta para el GPA.

La escala _numérica_ por defecto viene con `FA` ya definida, así que la acción funciona
de la caja.

### Falla a un estudiante

La acción **Falla por la ausencia** está disponible para el **registrador/programa**
en dos lugares:

- En el **Roster de Curso Programado** (Escritorio), justo al lado del **Estudiante de Grado**.
- En el informe de **Riesgo de Estudiantes en Asistencia**: marque la fila(s) y elija
  **Falla por la ausencia**.

Aplicando:

- Fuerza la nota final del estudiante al código **FA** con un resultado **falla**,
  **sin importar sus puntuaciones** — y es _pegado_, así que volver a ejecutar las notas (o
  el instructor de **Enviar calificaciones**) mantiene a la FA en lugar de recalcular una nota
  que pasa.
- Updates the **transcript** (Program Enrollment Course → status _Fail_, grade
  _FA_) and removes the course's credits from the student's total if they had
  been counted as passed.
- Es completamente **reversible** — **Deshacer fallar la ausencia** lo elimina y restaura el grado
  computado real.

> \*\*Puntuación de partituras, calificación fallida. \* Es todo el punto del FA: un estudiante puede
> tener un promedio B y recibir una FA en la transcripción porque perdió
> demasiadas clases. El puntaje numérico se conserva para el registro; el código
> y el pasar/fallar se anulan.

### En su lugar, reportando un incidente disciplinario (o también)

Los problemas de asistencia a menudo también pertenecen al módulo [Discipline](discipline.md).
Cuando **Configuración seminaria → Instructores crear Incidente Disciplinario** está encendido, y
existe una **Attendención** categoría Disciplinaria, aparece un botón **Informe Disciplinario
Incidente**:

- En la **página de asistencia al instructor**, junto a cualquier estudiante que esté en riesgo o
  sobre el límite (solo por razones marcadas como _Portal del instructor_).
- On the **Students At Attendance Risk** report, for the registrar — it opens a
  new incident pre-filled with the student and an Attendance reason.

Fragmentar las ausencias y presentar un incidente disciplinario son independientes: usar uno,
el otro, o ambos.

## Ejemplos prácticos

### Ejemplo 1 — Una regla estándar del 20% con autofacturación

**Objetivo:** los cursos en persona permiten a los estudiantes perder el 20% de las clases; los estudiantes
se registran a sí mismos con un código.

1. **Programa → Política de asistencia → Por defecto Max Ausencia Máxima %** = `20`.
2. **Configuración seminaria → Política de asistencia:** Tardies por ausencia `3`, Advertencia
   dentro de `1`.
3. **Configuración seminaria → Auto-Checkin de Asistencia al Curso:** Forzar tiempo de reunión
   ventana (ventana), Requiere código de registro de entrada, Tardía después de `10`.
4. Un curso presencial con **14 reuniones** (política automática) da a cada estudiante un límite de **3** ausencias de 20%-programas
   a cada estudiante.
5. En clase, el instructor hace clic en **Mostrar código de facturación**, proyecta el código +
   QR. Los estudiantes lo escanean/introducir; cualquiera que realice un check-in en más de 10 minutos después del inicio
   está marcado como **Tardía**.
6. Cuando un estudiante alcanza **2** ausencias efectivas, está marcado _en riesgo_
   (se notifica a todos una vez); a las **4** están _por encima del límite_ (notificado de nuevo).

### Ejemplo 2 - Falla a un estudiante para las ausencias

**Objetivo:** un estudiante con un promedio que pasa ha perdido demasiadas clases y el programa
las falla.

1. El estudiante muestra **sobre el límite** en el reporte **Estudiantes en riesgo de asistencia**.
2. El registrador marca la fila y hace clic en **Fallo para la ausencia** (o abre el Ranking de Curso programado
   y utiliza el botón al lado del _Estudiante de calificación_).
3. La nota del estudiante se convierte en **FA / Fail**; su transcripción registra la FA y los créditos del curso
   no se contabilizan. Si el instructor ejecuta **Envía calificaciones**,
   los sticks de la FA.
4. Si fue un error, el registrador hace clic en **Deshacer Falla por la ausencia** y la nota
   real devuelve.

### Ejemplo 3 — Un curso en línea sin límite de asistencia

**Objetivo:** un curso virtual con dos reuniones listadas no debería estar sujeto a la regla porcentual
.

Nada que hacer. Con **Modality = Virtual** y política **Auto**, el límite es
automáticamente desactivado — los estudiantes no ven ningún panel de asistencia, el instructor ve
no hay columna de ausencias, y nadie está marcado. Si un curso en línea en particular _sí_
necesita un límite, el registrador establece su política en **Personalizado** con un número explícito
.

## Día a día

- **Presta atención.** Abre un curso → Asistencia → Elige la fecha → Marcar
  Presente / Tardía / Ausente → guardar. O imprima una hoja en blanco e introdúzcala más tarde.
- \*\*Haz clic en **Mostrar código de facturación**, proyectarlo (y el QR),
  y hacer que los estudiantes ingresen desde **Marcar mi asistencia**.
- **Mira quién está en riesgo.** Registrar: ejecuta **Estudiantes en riesgo de asistencia** (Desk).
  Instructores: la columna Ausencias en la página de asistencia. Students: the
  Attendance panel on their course status.
- **Falla (o no falla) en las ausencias.** Registrador / Programa Deshacer: **Falla por
  ausencia** en la lista o en el informe de riesgo **Deshacer** para revertir.
- **Establece la política.** Programa → ausencia máxima predeterminada %; sobreescribe por curso en la
  Programación del curso (solo registrador).

## Referencia rápida

| Si desea... | Haga esto                                                                                                                      |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Grabar asistencia                                           | Curso → Asistencia → Marcar Presente / Tardía / Ausente                                                                        |
| Imprimir una hoja para marcar a mano                        | Attendance page → **Print blank sheet**                                                                                        |
| Permitir que los estudiantes se registren a sí mismos       | **Mostrar código de facturación** (código del proyecto + QR); los estudiantes usan **Marcar mi asistencia** |
| Requiere un código / establecer la ventana                  | Configuración seminaria → Autofacturación de asistencia al curso                                                               |
| Hacer que los tardies cuenten para las ausencias            | Configuración seminaria → **Tardies por ausencia** (0 deshabilitados)                                       |
| Establecer la regla de ausencia para un programa            | Programa → **Ausencia máxima predeterminada %**                                                                                |
| Anular el límite de un curso                                | Programación del curso → Política de asistencia → **Personal** (solo registrador)                           |
| Desactiva el límite para un curso                           | Programación del curso → Política de asistencia → **Desactivado** (Auto-discapacidades virtuales)           |
| Excluir una ausencia (permiso aprobado)  | Enlace el registro ausente a una solicitud de abandono de estudiantes aprobada                                                 |
| Ver estudiantes de riesgo en todos los cursos               | Informe Desk → **Estudiantes en riesgo de asistencia**                                                                         |
| Fallo al alumno por ausencias                               | **Fallo en la ausencia** en la lista o en el informe de riesgo (registrador / Programa n)                   |
| Invertir un fallo en la ausencia                            | **Fallo de deshacer por la ausencia**                                                                                          |
| Elija el código de transcripción de FA                      | Escala de calificación → **Código de fallo para ausencias**                                                                    |
| Enviar un incidente disciplinario de asistencia             | **Informar del incidente disciplinario** en la página de asistencia o en el informe de riesgo                                  |

## Relacionados

- [Discipline](discipline.md) — file attendance-related incidents; progressive
  sanctions for repeated absence.
- [Grading](grading.md) — cómo funcionan las notas finales y enviar calificaciones; FA anula la nota
  calculada.
- [Retiro y Separación](withdrawal.md) — licencia aprobada que excusa
  ausencias.
- [User Roles](../administration/user-roles.md) — who can set policy, fail for
  absences, and adjudicate.
