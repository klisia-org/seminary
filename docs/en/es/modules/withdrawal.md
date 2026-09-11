# Retiro

El módulo de retiro gestiona bajas de cursos y retiros institucionales con reglas configurables por periodo académico.

## Descripción general

Los estudiantes pueden solicitar el retiro a través del Portal del LMS.
Las reglas que rigen los plazos, las penalizaciones y la elegibilidad para reembolsos las configuran los usuarios académicos en la vista de Desk.

## Conceptos clave

- **Periodo sin penalización** — un periodo configurable después del inicio del periodo académico en el que el retiro no conlleva penalización académica
- **Motivo de retiro** — un doctype independiente que permite a las instituciones hacer seguimiento y reportar por qué los estudiantes se retiran
- **Gestión de reembolsos/becas** — implicaciones financieras configuradas junto con las reglas de retiro

## Solicitud de retirada

Iniciada por el estudiante (si está permitido en Seminary Settings) o por administradores/usuarios académicos

### Solicitud del estudiante

Los estudiantes pueden solicitar el retiro de cualquier curso en el que estén actualmente matriculados y al que tengan acceso en el Portal.
Vaya a un Curso --> Mi estado: Al final de la página, los estudiantes pueden solicitar el retiro de ese curso. El sistema mostrará en la parte superior de esta página el estado de la solicitud de retiro del curso.

Los estudiantes deberán proporcionar un [motivo preconfigurado](#withdrawal-reasons) y cualquier documentación de respaldo requerida por ese motivo específico. El sistema completará automáticamente los campos obligatorios.

Los estudiantes también pueden crear solicitudes de retiro para otros cursos, además de este, seleccionando la opción adecuada en "Withdrawal Scope". Cada curso rastreará su propia Petición de Retiro, pero los administradores seminarios verán las solicitudes relacionadas.

![Pantalla del Portal de Solicitudes de retiro](/modules/withdrawal/img/withdrawal_request_portal.png)

Una vez que el estudiante haya enviado la solicitud, su estado será visible en la parte superior de la página Mi estado de ese curso. Los estados dependen del Workflow correspondiente.

![Pantalla de estado del Portal de Solicitudes de retiro](/modules/withdrawal/img/withdrawal_request_portal_status.png)

### Solicitud del registrador

Registars or other assigned users can create and track progression of the Withdrawal Request within Desk, advancing it through the workflow with the Action menu (top right).
Seminary ERP incluye un Workflow predefinido, que puede personalizar el administrador del seminario. Esto es particularmente útil para incluir notificaciones por correo electrónico, entre otras posibilidades.

![Pantalla de Solicitudes de retiro en Desk](/modules/withdrawal/img/withdrawal_request_desk.png)

## Motivos de retiro

Es una buena práctica estandarizar y evaluar periódicamente los motivos que llevan a los estudiantes a retirarse de los cursos. Muchas agencias acreditadoras lo exigen y SeminaryERP facilita el cumplimiento de este requisito.
Cuando se crea un motivo de retiro, los administradores indicarán un nombre, una descripción, si será obligatorio adjuntar documentación de respaldo (siempre está disponible, solo que no es obligatoria) y, en ese caso, qué etiqueta se mostrará a los estudiantes. Esto facilita que los estudiantes sepan exactamente qué deben enviar. Dos editores de texto enriquecido informativos proporcionan documentación inicial para estudiantes y personal.

![Pantalla de Motivos de retiro](/modules/withdrawal/img/withdrawal-reasons.png)

## Reglas de retiro

1. Asigne a la regla un nombre claro, fácil de entender por sí mismo.
2. La casilla de verificación "Exclude from Grade calculation" indica que esto no contará para el GPA final
3. Símbolo de calificación: Cómo desea que esto aparezca en el expediente académico (puede ser una palabra, no necesariamente un símbolo)
4. Permitir crédito parcial: Las evaluaciones enviadas por el estudiante pueden usarse para otorgar crédito parcial (esta función está en desarrollo)
5. Si la configuración principal en "Seminary Settings" lo permite, se podrá calcular automáticamente para cada periodo una [**Fecha basada en el periodo**](#term-widrawal-rules). Cuando está marcada, habrá campos adicionales para calcular la fecha "Applies until" para cada periodo. Tenga en cuenta que, dado que la regla se aplica por periodo (aunque afecte a los horarios de los cursos), los umbrales de fecha siempre son relativos al periodo.
6. Reembolso: Si la casilla está marcada, se habilita una tabla hija. Esto definirá cuánto se reembolsará y a quién, si la regla aplica. Es decir, el sistema identificará automáticamente la "Sales Invoice" de ese curso y creará una "Credit Note" contra ella, siguiendo el mismo procedimiento fiscal que la "Sales Invoice". Las reglas contemplan tres tipos de pagadores: Estudiante (es decir, el Customer de ERPNext asociado con el Estudiante), Becas (el Customer de ERPNext asociado con Scholarships en Seminary Settings) y Otros pagadores (ya que SeminaryERP también da la opción de que iglesias o denominaciones paguen parte de la matrícula).

![Pantalla de Reglas de retiro](/modules/withdrawal/img/withdrawal-rules.png)

## Reglas de retiro por periodo

Si es necesario ajustar manualmente las fechas a las que aplica una regla, esto puede hacerse en Desk, Term Withdrawal Rules.

![Pantalla de Reglas de retiro por periodo](/modules/withdrawal/img/withdrawal-term-rules.png)

## Workflow de la Solicitud de retiro

La mayoría de los seminarios no necesitarán editar el Workflow preconfigurado. Sin embargo, es posible hacerlo y las instituciones más grandes pueden beneficiarse especialmente de personalizaciones. Dado que esta es una funcionalidad de ERPNext, su [documentación](https://docs.frappe.io/erpnext/workflows) puede resultar útil.

<LifecycleDiagram type="withdrawal" />

The workflow has five states: **Draft → Academic Review → Financial Review → Completed**, plus **Rejected**. Academic Review is the registrar's queue; Financial Review belongs to the Accounts User. The _action_ you take carries the meaning — approving academically routes the request onward, and the side effects (withdrawing the course enrollment, issuing refunds, finalizing a program separation) are applied as those actions are taken.

The Academic Review step adapts to whether money is involved. When a refund could be due (a withdrawal rule with refunds applies and the program is not free), the registrar's approval is **Approve Academically**, which sends the request to Financial Review. When no refund is due, that same step becomes **Approve Academically & Conclude**, which settles the request in one click without a Financial Review stop.

### Rápidas rutas para programas en curso y gratuitos

Dos banderas en el programa subyacente cambian los botones mostrados en una solicitud de retiro para que los usuarios no tengan que hacer clic a través de los estados de revisión que no tienen nada que evaluar:

- **Está en curso** – una propiedad del **Nivel del Programa**, reflejada en todos los Programas de ese nivel. Los programas en curso no tienen un concepto de graduación, GPA o transcripción, por lo que no hay nada que revisar académicamente sobre un retiro.
- **Programa gratis** es una casilla de verificación por programa. Cuando se establece, la inscripción no genera facturas de venta, por lo que no hay nada que revisar financieramente sobre un retiro.

Los botones disponibles en una solicitud de retirada de borrador se adaptan automáticamente:

| Marcas del programa      | Botón mostrado en el borrador                                                        | Tierras en                                                                                                                                                                                         |
| ------------------------ | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ninguna marca            | **Submit**                                                                           | Academic Review (standard Academic → Financial → Completed chain)                                                                                                               |
| Solo gratis              | **Submit**                                                                           | Academic Review; with no refund due, the registrar's approval appears as _Approve Academically & Conclude_ and settles it in one step (no Financial Review) |
| Ongoing only, refund due | **Submit & Approve Academically** (Registrar) | Financial Review (academic auto-approved; paid courses still settle)                                                                                                            |
| Ongoing only, no refund  | **Submit & Conclude** (Registrar)             | Completed                                                                                                                                                                                          |
| **y** gratis             | **Submit & Conclude** (Student or Registrar)  | Completado (sin revisión en absoluto)                                                                                                                                           |

On the ongoing-program fast-paths no grade treatment is applied — the system simply marks the underlying Course Enrollment as withdrawn.

If a student initiates a withdrawal for an ongoing-but-paid program, they still see the standard **Submit** button; the registrar later walks the request through Academic Review, where the academic processing for ongoing programs is a no-op by design.