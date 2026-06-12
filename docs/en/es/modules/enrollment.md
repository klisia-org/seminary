# Inscripción

La Inscripción gestiona cómo los estudiantes se inscriben en cursos dentro de un período académico.

## Descripción general

Los estudiantes pueden autoinscribirse a través del portal del LMS durante las ventanas de inscripción configuradas, o los administradores pueden inscribir a los estudiantes directamente desde Frappe Desk.

## Conceptos clave

- **Ventana de inscripción** — el rango de fechas durante el cual la autoinscripción está abierta
- **Inscripción al curso** — el registro que vincula a un estudiante con un curso en un período académico específico
- **Capacidad de inscripción** — límite opcional de estudiantes por sección del curso

## Ciclo de vida de matriculación del curso

Un registro individual de un curso se mueve a través de un flujo de trabajo de cuatro estados:

<LifecycleDiagram type="enrollment" />

- **Borrador** — creado pero no enviado; nada ha pasado más allá de guardar la fila
- **Esperando pago** — enviado, facturas de ventas generadas, pero el estudiante aún no ha sido añadido a la lista del curso (sin acceso a LMS)
- **Enviado** — el estudiante está totalmente inscrito: en la lista de cursos, en la lista de cursos de la Inscripción al programa, elegible para recibir calificaciones
- **Retirada** — se establece automáticamente cuando una Petición de Retiro alcanza Aprobación Académica; visible en la vista de lista CEI como una píldora de estado de lista

¿Qué camino toma el CEI de Drraft depende del **Programa** al que pertenece el curso:

| Marcas del programa                            | Envíos de borrador a | Por qué                                              |
| ---------------------------------------------- | -------------------- | ---------------------------------------------------- |
| Programa gratis (`is_free`) | Enviado              | Sin facturación, sin pago a puerta en                |
| Pagado + Requerir Pago Antes de Inscripción    | A la espera de pago  | Mantenga el asiento hasta que el estudiante pague    |
| Pago + pago no requerido                       | Enviado              | Factura al estudiante pero inscríbete de todos modos |

Para programas configurados como _Requerir Pago Antes de Inscripción_, los anticipos automáticos CEI de **Esperando el Pago** a **Enviado** cuando los pagos acumulados del estudiante cruzan el umbral _Pago mínimo %_ del programa (100 % por defecto). Para escenarios de pagadores mixtos (estudiante + beca + terceros), el umbral se calcula en función de la cantidad _total_ facturada a través de todas las facturas de ventas vinculadas.

### Anulación manual

Si un pago llega fuera de la plataforma (efectivo en la oficina del registrador, transferencia bancaria reconciliada más tarde, excepción especial), un usuario de Académicos puede usar el botón de flujo de trabajo **Marcar como pago** en un CEI en espera de pago para avanzar a Enviado sin grabar primero una entrada de pago.

### Reembolsos y notas de crédito

Si un post de nota de crédito después del CEI llegó a Enviado y el porcentaje de pago recalculado cae por debajo del umbral, el CEI **se queda en Submitted** — el alumno no está inscrito a medio plazo. En su lugar, se crea un ToDo y se envía un correo electrónico a todos los Usuarios Académicos para que el registrador pueda decidir si presentar una Petición de Retiro, seguimiento de la colección, o aceptar la nueva realidad.

### Sección de estado del pago en el CEI

El formulario CEI expone una sección de _Estado de pago_ que muestra el estado en vivo:

- **Total facturado** — suma de todas las facturas de ventas vinculadas
- **Total pagado** — suma de `(grand_total − importe_pendiente)` a través de esas facturas
- **Pagado %** — derivado; mostrado en la vista de lista
- **Umbral activado** - hora de fecha sellada por el sistema cuando el avance automático se disparó (vacío para anulaciones manuales y programas libres)

## Programas gratuitos y en curso

Dos banderas a nivel de programa conforman la experiencia de inscripción para ofertas no tradicionales:

- **Está en curso** (reflejado en el nivel del programa) — programas sin graduación: educación continua, auditoría gratuita y cursos devocionales. Los CEI en los programas en curso omiten el cálculo de la GPA, nunca activan cheques de auditoría de graduación y tienen retiro gratuito (sin revisión académica).
- **Programa gratis** (por programa) — evita completamente la generación de Facturas de Ventas y omite la revisión financiera en el retiro. A menudo combinado con _Está en curso_, pero los dos son independientes: un seminario remunerado en una pista continua deja _Programa Gratis_ apagado; un programa de grado libre deja _Está en curso_ así que la lógica de graduación todavía se ejecuta.

Vea [Withdrawal → Rápidas rutas para programas en curso y gratis](withdrawal.md#fast-paths-for-ongoing-and-free-programs) para ver cómo las mismas banderas dan forma al flujo de retiro.

## Duración máxima de la inscripción

Programas que limitan el tiempo que un estudiante puede permanecer inscrito (p. ej. "MDiv debe terminar en 7 años") estableció **Max Years en Graduate** en el Programa (años fraccionales apoyados). Al enviar la inscripción, la _Fecha Máxima de Graduación_ del estudiante es autoajustada a _fecha de matriculación + año máximo a Graduate_. Los registradores pueden editar _Fecha Máxima de Graduación_ después para conceder extensiones.

El informe **Riesgo de tiempo para graduar** (en Informes → Seminario) lista cada inscripción activa cuyo Programa tiene una duración máxima de inscripción, calcula los créditos restantes y el tiempo restante, y clasifica a los estudiantes por el ritmo de los créditos por año que necesitan para hacer su tope. Los estudiantes de mayor riesgo aparecen en la parte superior.
