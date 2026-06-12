# Calendario Académico

El calendario académico gestiona los términos, las fechas importantes y las reglas de plazos. Todos los aspectos se controlan a través de Desk.

## Descripción general

El calendario académico tiene una estructura por niveles:

### Año Académico:

Contiene términos académicos. Puede utilizarse para activar cuotas específicas. En el Plazo Académico, se puede ver si y cuándo se generaron facturas para el "Año Nuevo Académico" (NAY).

### Plazo Académico:

Los términos no pueden superponerse. Cada término debe estar íntegramente contenido en un Año Académico, con fechas de inicio y fin dentro del Año Académico. Términos Académicos pueden ser usados para activar tarifas específicas, y usted puede ver si y cuándo se generaron facturas para "Nuevo término académico" (NAT).
Cada término académico define la estructura de un período de enseñanza: fechas de inicio y fin y plazos de retiro (fechas para cada [Regla de retirada](withdrawal.md#withdrawal-rules)). Adicionalmente, los Términos Académicos se utilizan en todo el sistema como "anclas" para calcular otros eventos, como la inscripción y los períodos de clasificación (en la Configuración Seminaria).

### Reglas de la ventana de inscripción

Course enrollment windows control **when a Course Schedule opens and closes for
student enrollment** (plus a third, informational _grade close_ deadline). They
are defined once, seminary-wide, under **Seminary Settings → Enrollment Window
Rules**, and applied to every Course Schedule automatically.

Cada una de las tres ventanas tiene un **ancla** más un **desplazamiento en días**:

- **Ancla** — la fecha de referencia de la que cuenta el descuento:
  - `term_start` / `term_end` — el [Términos Académicos](#academic-term)de fecha de inicio / fin.
  - `classes_start` / `classes_end` — _esto_ Fecha de inicio / fin del programa del curso.
- **Desplazamiento (días)** — cuántos días del fondo. **Negativo = antes** del ancla
  , positivo = después, `0` = en el ancla mismo.

Las tres ventanas:

| Ventana                    | Lo que controla                                                                                                                                                                                                                 |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Inscripción abierta**    | Cuando el horario del curso se mueve de _borrador_ a _Abrir para matricular_ — los estudiantes pueden inscribirse.                                                                                              |
| **Cerrar inscripción**     | Cuando se mueve de _Open for Enrollment_ a _Enrollment Closed_ — la matrícula se detiene.                                                                                                                       |
| **Clase de Clasificación** | Fecha límite informativa para el envío de notas finales. Después de que pase, los instructores de los cursos que todavía están siendo calificados reciben correos electrónicos de recordatorio. |

> **Deja un ancla en blanco para salir** de esa ventana. Sin inscripciones Abiertas
> regla (y sin sobreescribir), un nuevo Programa de Curso abre para la inscripción
> _inmediatamente_ en la creación en lugar de esperar en Borrador.

\*\*Avance automático. \* Cuando **Estadísticas del Horario del Curso** está habilitado en Ajustes seminarios
, un trabajo diario promueve cada Horario del Curso a medida que sus fechas llegan
(Borrador → Abrir para la inscripción → Inscripción cerrada). Con esto apagado, las fechas son
calculadas y mostradas, pero el personal mueve los cursos a través de los estados a mano.

**Sobreescribe por curso.** La regla para todo el seminario es sólo el valor predeterminado. Cualquier
horario individual del curso puede anular una fecha en su sección **Fechas de inscripción**
(_Fecha de inscripción_, _Anulación de fecha de cierre de matriculación_,
_Anulación de fecha de cierre de matriculación_) — la anulación siempre gana para ese curso. Úsalo
para un curso añadido tarde o una excepción única.

#### Ejemplos prácticos

Cada ejemplo muestra los valores a introducir en **Configuración Seminaria → Inscribir
Reglas de Ventana**.

##### Ejemplo 1 — Todos los cursos de un término abiertos y cerrados juntos

Todo el mundo se inscribe durante una ventana de un solo término, sin importar cuando cada clase
se reúna realmente.

| Ajustes                                                           | Valor                                                                                                                         |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Anclaje abierto de inscripción                                    | `term_start`                                                                                                                  |
| Desplazamiento abierto de inscripción (días)   | `-14` &nbsp;_(dos semanas antes del comienzo del término)_                             |
| Anclaje cercano de inscripción                                    | `term_start`                                                                                                                  |
| Desplazamiento de cierre de inscripción (días) | `7` &nbsp;_(una semana después de que el término comience — una gracia corta/añadida)_ |

##### Ejemplo 2 — Cada curso se abre en relación a su propia fecha de inicio

Útil cuando las clases dentro de un término empiezan en diferentes fechas (por ejemplo, cursos intensivos o
modulares).

| Ajustes                                                           | Valor                                                                                                                 |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Anclaje abierto de inscripción                                    | `classes_start`                                                                                                       |
| Desplazamiento abierto de inscripción (días)   | `-30` &nbsp;_(la inscripción se abre un mes antes de que comience cada clase)_ |
| Anclaje cercano de inscripción                                    | `classes_start`                                                                                                       |
| Desplazamiento de cierre de inscripción (días) | `0` &nbsp;_(cierra el día que comienza la clase)_                              |

##### Ejemplo 3 — Cerrar la inscripción antes de que termine el término

| Ajustes                                                           | Valor                                                                                                             |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Anclaje abierto de inscripción                                    | `term_start`                                                                                                      |
| Desplazamiento abierto de inscripción (días)   | `0`                                                                                                               |
| Anclaje cercano de inscripción                                    | `término_fin`                                                                                                     |
| Desplazamiento de cierre de inscripción (días) | `-10` &nbsp;_(no nuevas inscripciones en los últimos 10 días del término)_ |

##### Ejemplo 4 — Una fecha límite de calificación después de que terminen las clases

Emparejar cualquiera de las ventanas anteriores con una fecha límite de calificación:

| Ajustes                                                      | Valor                                                                                                                      |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Ancla de cierre de escala                                    | `classes_end`                                                                                                              |
| Desplazamiento de cierre de escala (días) | `14` &nbsp;_(las notas finales vencen dos semanas después de que la clase termine)_ |

Instructors of any course still in _Enrollment Closed_ or _Grading_ past this
date receive automatic reminder emails.

##### Ejemplo 5 — No hay ventanas automáticas (abiertas inmediatamente)

Deja **todos los anclajes en blanco**. Cada nuevo Programa de Curso aterriza directamente en _Abrir
para inscripción_ y permanece allí hasta que el personal lo cierre manualmente. Elige esto si
tu seminario administra el tiempo de inscripción a mano o curso por curso.

##### Ejemplo 6 — Un curso necesita una excepción

Keep the seminary-wide rule, but for a single late-added Course Schedule, open
its **Enrollment Dates** section and set **Enrollment Open Date Override** to the
date you want. Ese curso ignora la regla seminaria; todas las demás no se ven afectadas.

## Conceptos clave

- **Término Académico** — la unidad de tiempo fundamental (semestre, trimestre, cuatrimestre)
- **DateRuleResolver** — lógica configurable para calcular plazos académicos en función de las fechas del término
- **Ventanas de inscripción** — Anclaje de todo el seminario + reglas de desplazamiento que abren y cierran los Programas del Curso para la inscripción (anulable por curso)
- **Reglas a nivel de término** — la configuración de plazos y políticas reside en el nivel del término, lo que permite diferentes reglas por término
