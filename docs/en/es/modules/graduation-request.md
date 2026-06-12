# Solicitud de Graduación

**Ruta Condicionalmente Elegible**: \*"Puedes presentar una solicitud para iniciar el proceso de graduación. _"Debes aprobar los cursos en los que estás actualmente para que sea aceptada."_

Este módulo es **optativo por programa**. Las escuelas que gestionan la graduación íntegramente desde la Secretaría Académica (sin solicitud iniciada por el estudiante) lo dejan deshabilitado y usan la página de [Auditoría del Programa](graduation-requirements.md) como una vista pasiva de elegibilidad.

## Descripción general

En la página de Auditoría del Programa conviven dos preguntas lado a lado:

| Pregunta                                                                | Respondida por                                                                                                            |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| _¿Este estudiante ha cumplido todos los requisitos para graduarse?_     | El banner de elegibilidad de la auditoría (`Eligible` / `Conditionally Eligible` / `Not Yet Eligible`) |
| _¿Este estudiante ha solicitado formalmente graduarse en este período?_ | El CTA de Solicitud de Graduación debajo del banner                                                                       |

La primera es automática. La segunda es una acción explícita del estudiante que registra una cuota, aparece en la cola de la Secretaría Académica y pasa por revisión.

## Activarlo en un programa

En el doctype **Program**, dos campos nuevos —ambos ocultos para programas en curso— activan el flujo:

- **Los estudiantes pueden solicitar la graduación** (Casilla) — el interruptor principal. Si está desactivado, no hay CTA, no se calcula la candidatura y no se puede presentar ninguna Solicitud de Graduación para este programa. Úsalo para programas gestionados íntegramente por la Secretaría Académica.
- **Disparador de la Solicitud de Graduación** (Selección, obligatorio cuando la casilla está activada) — cuándo el estudiante se vuelve elegible para presentar:
  - **Inscrito en los cursos finales** — el estudiante se convierte en candidato en el momento en que los cursos en los que está inscrito actualmente, _si todos se aprueban_, cerrarían el programa. Úsalo cuando quieras visibilidad temprana (empezar a preparar el diploma, organizar la ceremonia) y confíes en que el estudiante no presentará hasta estar seguro.
  - **Cursos finales aprobados** — el estudiante se convierte en candidato solo después de publicadas las calificaciones finales y cumplida la contabilización de elegibilidad. Úsalo cuando la política sea "no participas en la ceremonia si podrías reprobar tu última clase".

> **Consejo.** Ambos modos de disparador usan el mismo cálculo de elegibilidad. La diferencia es si los cursos **en progreso** cuentan para el cómputo final. Si no estás seguro de cuál elegir, **Cursos finales aprobados** es la opción conservadora.

## Cómo llega el estudiante al CTA

El sistema mantiene un indicador administrado por el sistema en cada Inscripción en el Programa llamado `grad_candidate`. Se reevalúa automáticamente cada vez que cambia el estado de la PE — inscripción a cursos, retiro, registro de calificaciones o cualquier edición de la Secretaría Académica. El estudiante no hace nada para "activar" su CTA; simplemente aparece cuando cumple las condiciones.

`grad_candidate = 1` requiere **todo** lo siguiente:

- El indicador **Los estudiantes pueden solicitar la graduación** del programa está activado y **Disparador de la Solicitud de Graduación** está definido.
- Todos los cursos obligatorios del programa están al menos _En progreso_ (o _Completado_, según el modo de disparador).
- Todos los cursos obligatorios en las trayectorias de énfasis activas del estudiante están al menos _En progreso_ (o _Completado_).
- El total de créditos — completados más en progreso (o solo completados, según el modo de disparador) — cumple con los créditos requeridos del programa.
- Cada requisito de graduación obligatorio marcado **Bloquea la Solicitud de Graduación** está `Fulfilled` o `Waived`.

Si algún bloqueador sigue pendiente, la candidatura permanece en 0 aun cuando el cálculo de créditos/cursos sería suficiente. Esto es deliberado — la escuela marcó explícitamente ese requisito como un prerrequisito estricto.

## Lo que ve el estudiante

En la página de **Auditoría del Programa** (`/program-audit/<enrollment>`):

1. El banner de elegibilidad ahora tiene tres estados:
   - **Elegible para Graduación** (verde) — todo aprobado.
   - **Elegible Condicionalmente para Graduación** (azul) — inscrito en sus cursos finales; será elegible cuando se publiquen esas calificaciones.
   - **Aún no elegible para Graduación** (ámbar) — el estado inicial predeterminado.

2. Debajo del banner, cuando el estudiante es candidato, el **CTA de Solicitud de Graduación**:
   - **Ruta Elegible**: \*"Cumples con los criterios de solicitud de graduación del programa. _"Presenta una solicitud para iniciar el proceso de aprobación."_
   - La **Solicitud de Graduación** es la solicitud formal que un estudiante presenta para graduarse. Es el momento en que la Secretaría Académica deja de preguntarse "¿podría este estudiante graduarse?" y empieza a procesar "este estudiante quiere graduarse este período." _"Debes aprobar los cursos en los que estás actualmente para que sea aceptada."_

3. Debajo del CTA, una tabla de **Pagos pendientes** agrupa cada **Factura de Venta** impaga de esta inscripción por pagador. Esto incluye las facturas del propio estudiante y las adeudadas por otros pagadores (iglesia patrocinadora, donantes de becas, fondo denominacional). El estudiante solo puede pagar las suyas en la página de Cuotas; esta tabla muestra a todos el panorama completo.

   La mayoría de las escuelas exigen saldar todos los saldos antes de la graduación. El paso de revisión financiera (más abajo) es la puerta de control, pero verlo aquí permite al estudiante gestionar a tiempo a sus otros pagadores.

## Qué sucede cuando presentan

Hacer clic en **Solicitar Graduación** realiza tres acciones de forma atómica:

1. Crea el registro de **Solicitud de Graduación** vinculado a esta Inscripción en el Programa.
2. Lo envía a través del flujo de trabajo.
3. Genera una **Factura de Venta** por la cuota de Solicitud de Graduación del programa, dirigida al pagador que esté configurado en la inscripción para el evento `Graduation Request`. (Si hay varios pagadores, la cuota se divide proporcionalmente, exactamente como las cuotas de Inscripción a Curso.)

El estudiante regresa a la página de auditoría; la tarjeta del CTA ahora muestra **A la espera de pago** con el porcentaje pagado y un enlace a la factura.

Si el programa está marcado como **Gratuito**, no se genera factura y la solicitud pasa directamente a `Academic Review`.

## El flujo de trabajo

<LifecycleDiagram type="graduationRequest" />

| Estado                  | Estado del documento | Quién puede editar | Qué significa                                                                                                                                                                                                                             |
| ----------------------- | -------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Borrador**            | 0                    | Usuario Académico  | En preparación; normalmente transitorio (el sistema crea y envía en un solo paso desde la página de auditoría).                                                                                        |
| **A la espera de pago** | 1                    | Usuario Académico  | Factura generada; el estudiante debe pagar. Avanza automáticamente cuando se paga en su totalidad.                                                                                                        |
| **Revisión Académica**  | 1                    | Usuario Académico  | Pago recibido (o el programa es gratuito). El área académica confirma que las calificaciones están publicadas, los bloqueadores despejados y los requisitos de graduación satisfechos. |
| **Revisión Financiera** | 1                    | Usuario de Cuentas | El Tesorero verifica que no haya otros saldos pendientes en la inscripción.                                                                                                                                               |
| **Aprobado**            | 1                    | Gestor seminario   | Sello final. El estudiante queda autorizado para la graduación.                                                                                                                                           |
| **Cancelado**           | 2                    | Gestor seminario   | Retirado del proceso.                                                                                                                                                                                                     |

### A la espera de pago → Revisión Académica (automático)

Cuando una Entrada de Pago se contabiliza contra la factura de la GR y `paid_percent ≥ 100`, el sistema avanza el flujo de trabajo automáticamente. No se requiere paso manual en el caso común.

Si una escuela opera con políticas de pago parcial, un Academics User puede hacer clic manualmente en **Marcar como pagado** para avanzar la solicitud antes de que se registre el pago total.

### Revisión Académica → Revisión Financiera (manual)

Un Academics User hace clic en **Enviar a Revisión Financiera** cuando verifica que:

- Las calificaciones finales están publicadas en cada curso de la inscripción.
- Cada requisito de graduación obligatorio y activo está `Fulfilled` o `Waived`.
- No hay decisiones académicas pendientes (calificaciones incompletas, apelaciones en curso).

El formulario de escritorio de la Solicitud de Graduación muestra dos tablas instantáneas en HTML para agilizar esta revisión:

- **Requisitos de Graduación** — cada fila de SGR con estado, indicador de obligatorio, indicador _Bloquea la Solicitud_, fecha de vencimiento y un enlace al documento vinculado (Carta de Recomendación, Proyecto de Culminación, etc.). Abre cualquiera con un clic.
- **Pagos pendientes** — cada factura impaga de la inscripción, agrupada por pagador, con enlaces de Desk a cada **Factura de Venta**.

### Revisión Financiera → Aprobado (manual)

Un Accounts User hace clic en **Aprobar financieramente** cuando verifica que:

- La cuota de graduación está pagada en su totalidad.
- No hay otros saldos pendientes en la inscripción (o la escuela los ha aceptado explícitamente).
- Los reembolsos, conciliaciones de becas y cualquier retención están resueltos.

Esta es la aprobación final. La Solicitud de Graduación queda en `Approved`.

> **Aviso — `Approved` no marca la PE como "graduado".** Es una acción separada de la Secretaría Académica (en una versión futura, un flujo de trabajo en la propia PE). `Approved` significa que la solicitud está completa; luego la Secretaría Académica ejecuta el procesamiento real de la graduación (anotación en el expediente, creación del registro de exalumno) fuera de este módulo.

## Cancelación

Dos caminos:

1. **Manual** — Academics o Seminary Manager hace clic en Cancelar en el formulario de la GR. Cualquier **Factura de Venta** vinculada y totalmente impaga también se cancela. Las facturas **parcialmente pagadas** se dejan como están — la Secretaría Académica gestiona explícitamente las decisiones de reembolso (usa el flujo estándar de Nota de Crédito de ERPNext si es necesario).

2. **Cascada por retiro de la PE** — cuando la Secretaría Académica desactiva una Inscripción en el Programa (`pgmenrol_active = 0`), toda GR activa en esa PE se cancela automáticamente. **La cuota no es reembolsable** en esta vía — las facturas se dejan intactas. Esta es la política predeterminada porque la mayoría de las escuelas tratan la cuota de graduación como una tarifa de servicio no reembolsable, y un estudiante que se retira no se va a graduar de todas formas.

## Día a día para el personal

### Dónde buscar

- **Por estudiante** — abre la Inscripción en el Programa en Desk; la GR (si existe) es visible en la barra lateral de Conexiones.
- **Cola** — la vista de lista de **Solicitud de Graduación**, filtrada a `workflow_state` en `("Academic Review", "Financial Review")`, es la cola diaria del registro académico.
- **Cohorte** — la misma lista filtrada por `expected_graduation_date` dentro de un período te da la cohorte que se gradúa para planificar la ceremonia.

### Revisar una solicitud

1. Abre la Solicitud de Graduación desde la vista de lista.
2. Revisa la instantánea de **Requisitos de Graduación** — ¿hay algo que no esté `Fulfilled` o `Waived`?
3. Revisa la instantánea de **Pagos pendientes** — el total impago es responsabilidad de Tesorería.
4. Haz clic en **Enviar a Revisión Financiera** (si eres Academics) o **Aprobar financieramente** (si eres Accounts), o **Cancelar** si la solicitud debe volver al estudiante.

### Cuando el estudiante no ve el CTA

Si un estudiante te dice que "debería poder graduarse" pero no ve el botón, repasa las comprobaciones de candidatura:

1. ¿Está activado **Los estudiantes pueden solicitar la graduación** en el Programa?
2. ¿Está configurado el **Disparador de la Solicitud de Graduación**?
3. ¿Todos los cursos obligatorios del programa + énfasis están al menos _En progreso_ (modo Inscrito) o _Completado_ (modo Aprobado)?
4. ¿Suman los totales de créditos?
5. ¿Hay requisitos de graduación **obligatorios** con **Bloquea la Solicitud de Graduación** marcado que aún estén `Not Started`, `In Progress` o `Submitted`?

El quinto es el bloqueador silencioso más común. Abre la Inscripción en el Programa y mira la tabla de Requisitos de Graduación del Estudiante — cualquier elemento con el indicador **Bloquea la Solicitud** debe estar `Fulfilled` o `Waived` primero.

> **Consejo — utilidad de bench.** Si cambias el disparador de un programa o corriges un caso difícil de depurar para un estudiante, el sistema reevalúa la candidatura automáticamente en el siguiente guardado relacionado con la PE. Para forzar un recálculo en todo un programa, ejecuta:
>
> ```
> bench --site <site> execute seminary.seminary.graduation_candidate.recompute_for_program --kwargs "{'program': 'MDiv'}"
> ```

## Ejemplos prácticos

### Ejemplo 1 — Graduación estándar de MDiv con cuota

1. **Configura el programa.** Abre el programa _MDiv_. Marca **Los estudiantes pueden solicitar la graduación**. Configura **Disparador de la Solicitud de Graduación** en _Cursos finales aprobados_ (el valor predeterminado conservador).
2. **Configura el pagador de la cuota.** En cada Inscripción en el Programa, abre la tabla _Payers Fee Category PE_ y añade una fila con `Event = Graduation Request`, la categoría de cuota adecuada, el pagador y el porcentaje.
3. El estudiante termina su último período. Una vez publicadas las calificaciones finales, el sistema cambia `grad_candidate` a 1.
4. El estudiante ve **Elegible para Graduación** + el botón **Solicitar Graduación** en la página de auditoría. Hace clic.
5. El sistema crea la GR + la **Factura de Venta**. El estudiante paga. La GR avanza automáticamente a **Revisión Académica**.
6. Academics abre la GR, revisa las tablas instantáneas y hace clic en **Enviar a Revisión Financiera**.
7. El Tesorero verifica que no haya otros saldos impagos y hace clic en **Aprobar financieramente**. La GR queda en **Aprobado**.

### Ejemplo 2 — Programa gratuito, solicitar en cuanto se inscribe en los cursos finales

1. Configura el programa _Online Certificate_: marca **Programa gratuito**, marca **Los estudiantes pueden solicitar la graduación**, establece el disparador en _Inscrito en los cursos finales_.
2. El estudiante se inscribe en sus últimos cursos del período.
3. La página de auditoría muestra el banner **Elegible Condicionalmente** + el CTA con la advertencia de "debes aprobar".
4. El estudiante presenta la solicitud. La GR omite **A la espera de pago** y pasa directamente a **Revisión Académica**.
5. Academics espera hasta que lleguen las calificaciones. Si todo está aprobado, **Enviar a Revisión Financiera**. Si algún curso se reprobó, **Cancelar** — el estudiante puede volver a presentar cuando cumpla el requisito.

### Ejemplo 3 — Prerrequisito estricto: la tesis debe aprobarse primero

1. Abre el elemento de Biblioteca **Senior Project** (Documento vinculado, destino _Proyecto de Culminación_). Marca **Obligatorio**, marca **Bloquea la Solicitud de Graduación**.
2. El estudiante termina los cursos, pero la tesis sigue en revisión. Aunque el cálculo de créditos se cumple, `grad_candidate` permanece en 0 — la página de auditoría muestra **Elegible Condicionalmente** pero no aparece el CTA.
3. El asesor del estudiante aprueba la tesis. El flujo de trabajo de Proyecto de Culminación queda en `Completed`. La fila de SGR cambia a `Fulfilled`. El evaluador de candidatura se ejecuta, ve que el bloqueador ya está satisfecho y cambia `grad_candidate` a 1.
4. El estudiante actualiza la página de auditoría. Ahora el CTA es visible. Presenta la solicitud.

### Ejemplo 4 — Iglesia patrocinadora con pagos atrasados

1. El estudiante termina los cursos. Presenta la Solicitud de Graduación y paga la cuota de graduación. La GR avanza a **Revisión Académica**.
2. Academics revisa los requisitos; todo está en orden. Envía a **Revisión Financiera**.
3. El Tesorero abre la GR y revisa la instantánea de **Pagos pendientes**. Ve que la iglesia patrocinadora adeuda 4.200 $ en tres facturas mensuales.
4. El Tesorero retiene la Aprobación y contacta a la iglesia. Una vez pagado, **Aprobar financieramente**. (Alternativamente, si la escuela tiene un acuerdo por escrito con la iglesia, el Tesorero puede aprobar y cobrar el saldo por separado — es una decisión de política institucional que el sistema no impone.)

## Referencia rápida

| Si quieres...                         | Haz esto                                                                                                                                                                                         |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Habilitar Solicitudes de Graduación en un programa                                    | Programa → marca _Los estudiantes pueden solicitar la graduación_ + elige un disparador                                                                                                          |
| Deshabilitar Solicitudes de Graduación para un programa específico                    | Desmarca _Los estudiantes pueden solicitar la graduación_ en ese Programa                                                                                                                        |
| Convertir un requisito de graduación en prerrequisito estricto incluso para presentar | Biblioteca → marca _Bloquea la Solicitud de Graduación_ (solo visible si es Obligatorio)                                                                                      |
| Forzar un recálculo de candidatura para un estudiante                                 | Guarda la Inscripción en el Programa (cualquier campo) — el recálculo se dispara en `on_update_after_submit`                                                                  |
| Forzar un recálculo para todo un programa                                             | `bench execute seminary.seminary.graduation_candidate.recompute_for_program --kwargs "{'program': 'XYZ'}"`                                                                                       |
| Ver la cola de revisión de la Secretaría Académica                                    | Lista de Solicitud de Graduación, filtro `workflow_state in ("Academic Review", "Financial Review")`                                                                                             |
| Cancelar una solicitud sin reembolso                                                  | Haz clic en Cancelar en la GR (las facturas parcialmente pagadas se dejan como están)                                                                                         |
| Confirmar que la graduación finalizó                                                  | Queda en el estado de flujo de trabajo `Approved` — el procesamiento real de la graduación (certificado, registro de exalumno) es un paso separado de la Secretaría Académica |

## Relacionado

- [Requisitos de Graduación](graduation-requirements.md) — las capas de política + Biblioteca + SGR de las que lee el evaluador de candidatura.
- [Inscripción](enrollment.md) — En la Inscripción en el Programa residen `grad_candidate`, la instantánea de la política y la configuración del pagador de cuotas.
- [Retiro](withdrawal.md) — retirar una PE cancela automáticamente cualquier Solicitud de Graduación activa.
- [Roles de Usuario](../administration/user-roles.md) — Academics User vs Accounts User vs Seminary Manager (pasos de revisión).
