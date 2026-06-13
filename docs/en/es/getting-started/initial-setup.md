# Configuración inicial

Después de [installation](installation.md), camina por las secciones de abajo **por orden**. Cada uno depende de lo anterior. Todo se hace en la Frappe Desk a menos que se tenga en cuenta.

:::tip Fundamentos ERPNext
SeminaryERP se construye sobre ERPNext. Varios artículos a continuación (artículos, listas de precios, grupos de clientes, precios de artículos, artículos Los términos de pago) son _registros ERPNext estándar_ — esta página cubre lo que un seminario necesita específicamente. y enlaza con el manual ERPNext para la referencia completa.
:::

## 1. Escala de Calificación

Crear la escala de calificación predeterminada utilizada seminario--do? Puedes crear escalas adicionales más tarde y asignarlas por curso. Vea [Grading](../modules/grading.md) para ver cómo interactúan las escalas con las evaluaciones y transcripciones.

## 2. Ajustes seminarios

Vaya a **Ajustes del Seminario** en Frappe Desk para configurar: Este es el panel de control para todo el seminario:

- **Detalles de la institución y logo**
- Escala de valoración por defecto
- **Becas** — Centro de Costos y Cliente Predeterminado
- **Cuidados** - si se permite a estudiantes no acreditados y cómo se les cobra (tarifa fija o por hora de crédito)
- **retiro de curso** — política de línea de referencia (las reglas detalladas están configuradas en el [módulo de retirada](../modules/withdrawal.md))
- **Curso de Programación de ciclo de vida**:
  - **Estado del Horario del Curso Auto-Avanzado** (por defecto en) — cuando está marcado, el planificador diario avanza los Programas del Curso automáticamente en base a las fechas siguientes (Borrador → Abrir para la inscripción → Cerrar la inscripción) y enviar un correo electrónico a los instructores que no han enviado las calificaciones por el plazo. Desmarque si su seminario prefiere un control manual completo.
  - **Reglas de Ventana de Inscripción** — tres pares de (anclaje, desplazamiento en días) que definen cuándo se abre cada Programación de Curso para la inscripción, cierra la inscripción y espera las calificaciones. Anclajes: `term_start`, `term_end`, `classes_start` (= la fecha de inicio de cada horario del curso), `classes_end` (= la fecha de fin de cada finalización del curso del horario). Desfase negativa = antes del fondo; positivo = después. Un ancla en blanco opta por una ventana — los Programas del Curso afectados necesitan anulaciones explícitas en su propia forma (sección de ciclo de vida) o aterrizar directamente en Open for Enrollment sin plazo de inscripción. Ver [Sección 12](#_12-course-schedule-lifecycle).
- **HR/nómina** - Puedes extender la funcionalidad de SeminaryERP con nuestra integración con Frappe HRMS para procesar nóminas. Para hacer esto, haga clic en [Habilitar nómina HRMS](../modules/instructor-payment.md)
- **Portal de estudiantes** — cambia cada capacidad que tendrán los estudiantes:
  - Solicitar matriculaciones de cursos
  - Solicitar retiros de cursos
  - Pagar en línea a través de una pasarela de pago (y cuál pasarela es el predeterminado — por ejemplo, Stripe)
  - Editar instrucciones del calendario del curso
  - Flujo de trabajo en línea de la aplicación del estudiante

## 3. Elementos ERP

En ERPNext, todo lo que se puede facturar es un **artículo** (hora de crédito, cuota de inscripción, cuota de biblioteca, alojamiento, etc.). SeminaryERP viene con un set de inicio — revisa y decide qué se ajusta a tu seminario antes de crear más.

:::warning UOM no debe ser "número entero"
Al crear un nuevo objeto, asegúrate de que su [UOM](https://docs.frappe.io/erpnext/uom) tiene **"Debe ser número completo"** sin marcar. Las horas de crédito y muchas comisiones son fraccionales.
:::

Para cualquier otra cosa acerca de los artículos — stock vs. no stock, grupos de artículos, impuestos — vea el ERPNext [Documentación del artículo](https://docs.frappe.io/erpnext/item).

## 4. Listas de precios

Una [Lista de precios](https://docs.frappe.io/erpnext/price-lists) es simplemente un conjunto de precios. Puedes tener tantos como quieras (p.e. _Estudiantes nacionales_, _Estudiantes extranjeros_, _Becas de nivel A_), pero **cada lista adicional es mantenida en curso** — agregue una sólo cuando los precios difieran genuinamente.

## 5. Grupos de clientes

SeminaryERP crea automáticamente un grupo de clientes **Estudiantes**. Si necesitas diferentes listas de precios aplicadas automáticamente (por ejemplo, nacional vs. internacional), crea [Grupos de clientes] adicionales (https://docs.frappe.io/erpnext/customer-group) y establece la lista de precios por defecto de cada uno. Los estudiantes asignados al grupo serán facturados de esa lista.

## 6. Precios del artículo

Aquí es donde usted introduce el precio de cada artículo en cada lista de precios. Ver [Precio del artículo](https://docs.frappe.io/erpnext/item-price) para los mecánicos.

Antes de introducir números, leer [Estrategia de Precios](pricing-strategy.md) — cómo el gránulo de tu precio determina cuánta automatización y el informe SeminariERP puede hacer por ti más tarde.

## 7. Términos de pago

Una [Plantilla de términos de pago] (https://docs.frappe.io/erpnext/payment-terms-template) contiene uno o más [Términos de pago](https://docs.frappe.io/erpnext/payment-terms) (por ejemplo, _50% en la matriculación, 50% a medio plazo_).
Por lo tanto, las plantillas son una forma sencilla y práctica de configurar **cuando** y **la porción de la factura (%)** debe pagarse.

Las condiciones de pago definirán la fecha de vencimiento de una factura basada en la fecha de creación, así como el porcentaje de la factura a pagar.
Las plantillas están adjuntas a Categorías de Tarifa y a facturas, así que crea las plantillas que necesitas antes de configurar Categorías de Tarifa.

## 8. Categoría de cuota

Una **Categoría de tasas** es la unidad de automatización de facturación de SeminaryERP. Cada categoría enlace:

- Un **elemento ERP** (lo que se factura)
- Una **Plantilla de términos de pago** (cómo se factura)
- Un **tipo de categoría** (grupo de artículos) para reportar
- Un **evento a cargar** (cuando se crea el cargo)
- Marcas para **Es Crédito Académico** y **Está asumido** --Solo las categorías de tarifas con estos indicadores se calcularán por hora de crédito (en el caso de las auditorías, ver también Configuración Seminaria)

SeminaryERP define el **evento a cargar** y se llaman programáticamente. Los siguientes activadores están disponibles para la creación de categorías de tarifa:

- **Inscripción al programa**: se desencadena una vez al enviar la inscripción al programa.
- **Inscripción al Curso**: se produce un incendio una vez por curso, en la presentación de la inscripción al Curso.
- **Nuevo plazo académico** — el planificador diario dispara en la fecha de inicio del plazo académico (o al día siguiente se ejecuta el trabajo, si no se encuentra el programa).
- **Año nuevo académico** — el planificador diario dispara en la fecha de inicio del Año Académico (o al día siguiente el trabajo se corre, si no se cumple).
- **Mensualmente** — el programador diario dispara en el primer calendario de cada mes para cada inscripción activa del programa. Una fecha `efectiva desde` en la Categoría de Tarifa restringe la facturación a las inscripciones del programa cuya Fecha de Inscripción es estrictamente posterior a esa fecha (déjalo en blanco para facturar a todos los que están inscritos).

Los tres activadores impulsados por el tiempo (NAT / NAY / Mensual) son idempotentes: el planificador registra que un período ha sido facturado (a través de `invoiced_nat_on`, `invoiced_nay_on`, `last_monthly_invoiced_on`) y no lo facturará dos veces. Si no se ejecuta un cron, la próxima ejecución diaria recoge cualquier período pendiente. La facturación puede ser pausada globalmente a través de **Configuración Seminaria → Habilitar facturación automática**. Para una recuperación única, use **Registrar Hub → Regenerar Facturas a Plazo Actual**.

Configurar una Categoría de Tarifa por evento cargable para que SeminaryERP pueda publicar facturas automáticamente cuando el evento suceda. Por eso primero deben existir artículos, listas de precios y términos de pago.

Una vez creadas las Categorías de Tarifa, las utilizará durante la creación de Programas y cursos.

## 9. Estructura del Año Académico

Crea tu primer [**Año Académico**](../modules/academic-calendar.md#academic-year). Es un contenedor de Términos Académicos — los términos no pueden extenderse más allá de los límites de su año. Algunas tasas y tareas administrativas están programadas una vez al año.

## 10. Plazo Académico

Cree su primer período académico

1. Establezca las fechas de inicio y fin
2. Configure las ventanas de matriculación y los plazos de retiro — vea el [Calendario Académico](../modules/academic-calendar.md#academic-term) y [Withdrawal](../modules/withdrawal.md) para ver cómo estas fechas establecen las reglas de bajada.

## 11) Programa

Un [**Programa**](../modules/program.md) es la estructura curricular en la que los estudiantes se inscriben (por ejemplo, _M.Div._, _Certificado en Estudios Bíblicos_). Define los créditos/términos requeridos, cursos, trazas, acentos y tarifas de nivel de programas. Crear al menos un programa antes de abrir la inscripción.
El modelado detallado del programa (seguimientos, enfoques, requisitos de crédito) está cubierto bajo [Enrollment](../modules/enrollment.md). Durante la inscripción en el programa, también se establecerá **quién** paga cada categoría de cuota y qué porcentaje (Categoría de cuota de pago).

Todas las Categorías de Tarifa para cualquier curso de ese programa **debe** estar vinculadas primero al nivel del programa.

### Nivel de programa

Cada Programa enlaza a un **Nivel de Programa** (por ejemplo, _Bachelors_, _Masters_, _Doctorado_, _Certificado_, _Programa no formal_). Los niveles son **enviados**: una vez enviado, un nivel está bloqueado y visible en el selector de nivel del formulario. Para cambiar los campos de compuerta en un nivel después del hecho, modifíquelo (creando una nueva revisión) y programas de repunte según sea necesario — esto le da una pista de auditoría limpia y evita cambios de comportamiento silenciosos en los programas que ya están en vuelo.

El nivel lleva una bandera que da forma al comportamiento:

- **Está en curso** — comprueba esto sólo cuando el programa no tiene un fin definitivo (educación continua, auditoría gratuita, cursos devocionales). Los programas en curso omiten la GPA, la graduación, la transición de antiguos alumnos y el paso de Examen Académico al retiro. El parámetro se refleja desde el Nivel de Programa a cada Programa a ese nivel (sólo lectura en el formulario del Programa).

Cuando _está en curso_ está establecido, la sección de GPA & Honores, _Tipo de inscripción_, _Términos de finalización_, y los _créditos para completar_ campos desaparecen del formulario del Programa — no tienen sentido para los programas en curso.

### Programa gratis

Una casilla de verificación separada por programa **Programa gratis** desacoplará la parte financiera del lado académico:

- Cuando está marcado, el programa **no** genera facturas de ventas de matrícula (envío de CEI, Nuevo Plazo Académico/Año Académico Nuevo / Académico de facturación mensual activa todos los programas libres de salteo), y las solicitudes de retiro omiten el paso de Revisión Financiera.
- La tabla _Financial_ y _Tarifas de programa_ se ocultan en el formulario del programa cuando se establece _Programa Gratis_.

Las dos banderas son ortogonales: un programa pagado-pero en curso (p.ej. los seminarios pagados de una sola vez en una pista continuada dejan sin control el _Programa Gratis_, por lo que los honorarios por curso y los flujos de reembolso todavía funcionan; un programa de grado libre deja _Está en curso_ sin comprobar, así que la lógica de graduación todavía se ejecuta. Vea [Withdrawal → Rápidas rutas para programas en curso y Gratis](../modules/withdrawal.md#fast-paths-for-ongoing-and-free-programs) para ver cómo se combinan las dos banderas para dar forma a los botones de retiro.

### Pasarela de pago (programas de pago)

Para los programas de pago, dos campos más controlan si la inscripción en un curso requiere el pago antes de que el estudiante esté completamente inscrito:

- **Requiere el pago antes de inscribirse** (predeterminado, oculto cuando se marca el _Programa Gratis_) — cuando se establece, una nueva inscripción en el curso aterriza al _Pago en espera_ al enviar. El estudiante es facturado pero no se añade a la lista del curso hasta que paga.
- **Pago mínimo %** (por defecto 100) — el pago acumulado mínimo, como porcentaje del total facturado de la inscripción en el curso que debe limpiar antes de que el sistema avance la inscripción a _Enviado_. Establecer 50 si se inscribe a la mitad; déjalo a 100 para requerir el pago completo.

Ambos campos están ocultos para programas en curso (sin concepto de matriculación). Ver [Inscripción → ciclo de vida de matriculación del curso](../modules/enrollment.md#course-enrollment-lifecycle) para la máquina de estado completo.

### Duración máxima de la inscripción (límite de tiempo)

**Max Years to Graduate** (Float, valores fraccionales soportados) es el tiempo máximo que un estudiante puede permanecer inscrito antes de que se gradue. 0 significa que no hay límite (el predeterminado). Cuando se establece, cada nueva inscripción a este programa obtiene una **Fecha de Graduación Máxima** calculada automáticamente como `Enrollment_date + Max Años para Graduar`; los registradores pueden editar esa fecha más tarde para conceder extensiones.

El informe de **Riesgo de tiempo para graduar** de compañero (informes → Seminario) lista las inscripciones activas cuyo programa tiene años máximos distintos de cero, los clasifica por el ritmo de crédito por año que necesitan para terminar a tiempo, y las banderas atrasadas a los estudiantes en la parte superior.

## 12. Curso de programación de ciclo de vida

Cada **Horario del curso** se mueve a través de un flujo de trabajo de seis estados que el planificador diario avanza automáticamente (cuando [Sección 2](#_2-seminary-settings) "Avance automático" está encendido) o los registradores caminan a través manualmente:

<LifecycleDiagram type="courseSchedule" />

- **Borrador** — creado, aún no visible para los estudiantes. El planificador promueve la apertura para la inscripción cuando llegue la fecha resuelta de inscripción.
- **Abrir para inscripción** — los estudiantes pueden solicitar la inscripción en el portal.
- **Inscripción cerrada** — ha pasado la ventana de registro, el término está en funcionamiento, prof está enseñando.
- **Calificación** — el sistema entra en este estado automáticamente la primera vez que se guarda una nota no nula contra cualquier estudiante activo (ya sea a través de la presentación/asignación/Exam/Discusión o directamente en el gradebook). No se necesita ninguna acción de registro.
- **Cerrado** — estado final, establecido cuando el prof hace clic en **Enviar calificaciones** en el cuaderno de notas (o, en la Información, en el formulario de Programación del curso). Las notas finales están escritas en la transcripción en este momento.
- **Cancelado** — terminal. Sólo se puede obtener antes de comenzar la calificación (ver _Cancelar un Curso_ más abajo).

### Anulación de fecha por horario del curso

La sección **Lifecycle** de cada Programa de Curso (en la pestaña Clase Roster) muestra la inscripción resuelta abrir/cerrar / cerrar calificaciones de las fechas de la regla de Configuración Seminaria, más tres campos opcionales de fecha de anulación. El rellenado de una anulación reemplaza la regla para ese programa — útil para cursos con retraso agregado, intensivos o excepciones únicas.

### Razones de cancelación del curso

Las cancelaciones requieren una **razón** elegida de una lista configurable. Barcos seminaryERP con cinco razones de semilla:

- Inscripción insuficiente
- Instructor no disponible
- Cambio de currículo
- Decisión administrativa
- Force Majeure

Para añadir o renombrar razones, abre **Razón de cancelación del curso** en el escritorio (barra de búsqueda). Marcar razones antiguas como inactivas en lugar de eliminarlas, por lo que las cancelaciones históricas mantienen una etiqueta válida.

### Cancelar un Curso (registrar flujo de trabajo)

Un curso sólo se puede cancelar mientras esté en **Open for Enrollment** o **Enrollment Closed**. Una vez que se ha ingresado cualquier calificación, el sistema mueve el curso a **Calificación** y la cancelación ya no se ofrece, en ese momento la cancelación correría el riesgo de perder los datos de transcripción.

Pasos:

1. Abre el formulario de Horarios del Curso (Escritorio).
2. Grupo de acción **Estado** → **Cancelar Curso**.
3. Elija un motivo de cancelación en el diálogo y confirme.

El sistema será:

- Marca la inscripción de cada estudiante matriculado con `Curso Cancelado`, la razón elegida y una marca de tiempo (diferente de una retirada iniciada por el estudiante).
- Elimine las filas del curso de inscripción del programa afectado para que los cursos cancelados no aparezcan en las transcripciones o evaluaciones de progreso. Se conservan las filas que provienen de las notas transferidas de un seminario asociado.
- Enviar un Anuncio Seminario a todos los estudiantes matriculados explicando la cancelación.
- Libera a los estudiantes matricularse en otra sección o curso inmediatamente — cheques de matriculación duplicados y listas de "cursos disponibles" ignoran los CEI de cursos cancelados.

La cancelación no se puede deshacer en esta versión. El diálogo advierte sobre esto, así que verifique antes de confirmar.

:::tip Emergencia: cancelar después de iniciar la calificación
Si un curso debe ser retirado después de que la calificación haya comenzado (p.e. el instructor muere a medio plazo), el procedimiento es: retirar a cada estudiante matriculado a través del flujo de retiro estándar, entonces haz clic en **Enviar calificaciones** en la lista vacía. El curso se cierra de forma limpia sin que haya grados de disputación.
:::

:::warning Las facturas de ventas NO son tocadas en la cancelación
Esta versión no toca las facturas de ventas cuando se cancela un curso. Reconcile manualmente — típicamente cancelando la factura por curso y creando una nota de crédito. Una iteración futura puede automatizar esto; hasta entonces, tratar la limpieza de las facturas como una tarea de registro separada.
:::

### Inscripción mínima

Cada **Curso** tiene un campo opcional **Inscripción mínima predeterminada**. Cada Horario del Curso tiene su propia anulación **mínimo de inscripción** (en la sección de ciclo de vida). Ambos son _sólo informativos_ — el sistema no cancela automáticamente cursos que pierdan el umbral. Utilice el informe de **Estado de inscripción** (Escritorio → Informes) para ver, por término académico, cada Horario del Curso con su mínimo, su inscripción actual y la brecha. Los cursos inferiores son destacados; cancelarlos mediante el flujo de trabajo anterior antes de que comiencen las clases.

### Recordatorios de grado tardío

Cuando **Avance automático** está activado, el planificador envía todos los días un correo electrónico a cualquier instructor cuya Programación del Curso ha pasado su fecha límite de cierre de notas y aún no ha alcanzado el estado **Cerrado**. El rol de Registrador es C'd. El recordatorio se envía una vez por Horario del Curso (bandera idempotente previene envíos repetidos).

### Criterios de evaluación automáticos del curso

Un nuevo horario de cursos no comienza vacío. Tan pronto como guarde un nuevo horario de cursos, su tabla de **Criterios de Evaluación** rellena automáticamente desde el `Criterio de Evaluación` del curso padre (configurado en la pestaña **Curso → Evaluación**). El título de las copias de mapeo, el enlace de criterios y el peso literalmente — así que si tu curso tiene el 100% de peso asignado, el nuevo Horario comienza listo para enseñar sin entrada de datos manuales.

Si cambias el Curso en un programa existente, la siembra **no** vuelve a correr — solo dispara una vez en la creación. Para extraer una copia fresca, usa **Importar plantilla del curso** a continuación.

:::tip Configurar primero las evaluaciones del curso
Configure los criterios de evaluación del curso padre (curso → pestaña de evaluación) con pesos que suman al 100% antes de crear cualquier planificación del curso. La misma configuración se almacena automáticamente cada término.
:::

### Reutilizando un Horario como Plantilla

La semilla automática de arriba cubre los criterios de evaluación, pero un horario de curso totalmente construido normalmente tiene más: capítulos, clases (con vídeos, PDFs, notas del instructor) y enlaces de evaluación conectados a lecciones específicas. Para reutilizar todo esto a través de términos:

1. Abre el curso padre (Escritorio → Curso → _Tu curso_).
2. En la pestaña **Evaluación**, establece **Plantilla por defecto de programación del curso** en el horario del curso que quieres utilizar como estructura canónica.

Luego, al crear un nuevo programa de cursos para ese curso:

1. Guardar el nuevo Horario del Curso como de costumbre (semilla de criterios de evaluación automáticamente — no se necesita entrada manual).
2. En el formulario del nuevo horario, haga clic en **Acciones → Importar plantilla del curso**.
3. El diálogo pre-rellena con la plantilla predeterminada del curso; puede elegir cualquier otro programa del mismo curso. Haga clic en **importar**.

Las copias de importación:

- **Capítulos** (incluyendo paquetes SCORM, referencias de archivos compartidas entre programas)
- **Lecciones** — cada una, sin importar si tiene un enlace de evaluación. Videos, PDFs, notas de instructor, contenido, permitir la bandera — todo lleva encima.
- **Criterios de evaluación** — reemplaza lo que hay en el nuevo programa (por lo que las filas autoseised son sobrescritas por las de la plantilla). Los enlaces de evaluación a nivel de la lección se reorganizan automáticamente con los criterios del nuevo programa.

La importación **no** copia:

- Roster, inscripciones o datos calificados
- Fecha de vencimiento de la evaluación (permanezca nulo hasta que los establezca por término)
- Historial de cancelación o timestamps de flujo de trabajo

Un comentario cronológico sobre el nuevo programa registra lo que fue importado, desde donde, cuándo y por quién.

**Restricciones:**

- Disponible en el estado de **Borrador** o **Abrir para inscripción** sólo — una vez que se cierra la inscripción, la estructura es confirmada.
- Permitido para **Usuario Académicos**, **Administrador Seminario**, o **Registrar**.
- Se niega si el calendario de destino ya tiene capítulos (operación de un solo disparo, no fusión). Para reimportar, elimina los capítulos primero.
- Se niega si el horario de origen no tiene criterios de evaluación, o si sus pesos no suman al 100% — arreglar la fuente primero.

:::warning La importación no es reversible
No hay "deshacer" para la importación. El diálogo advierte sobre esto. Si importó la plantilla incorrecta, elimine los capítulos e inténtelo de nuevo.
:::

## 13. Configure los roles de usuario

Consulte [Roles de usuario](../administration/user-roles.md) para obtener detalles sobre la configuración del acceso de instructores, estudiantes y administradores.

## 14. Entrada manual O importar los siguientes datos

Debe estar presente para que comience su primer mandato.
Si tienes un pequeño número de estudiantes y prefieres hacerlo manualmente, al crear un estudiante, SeminaryERP puede crear tanto un usuario vinculado como un cliente. Sin embargo, también es fácil importar estos datos. Puedes seguir [estas instrucciones](https://docs.frappe.io/erpnext/data-import).

| _**Importar**_ en este pedido                     | _**Entrada manualmente**_ en este pedido          |
| ------------------------------------------------- | ------------------------------------------------- |
| 1. Usuarios                | 1. Estudiantes             |
| 2. Clientes                | 2. Cursos                  |
| 3. Estudiantes             | 3. Lista de días festivos  |
| 4. Cursos                  | 4. Inscripción al programa |
| 5. Lista de días festivos  |                                                   |
| 6. Inscripción al programa |                                                   |

Luego, tienes que vincular los cursos a tus programas.
Se **recomienda encarecidamente** comprobar la importación y **complementar** la información de los Cursos antes de añadirlos a los Programas. Los cursos propagarán varias piezas de información a **Horario del Curso**, por lo que su integridad de la información acelerará el trabajo cada término.
Para añadirlos en masa, navega a cursos, selecciona todos los cursos que quieras añadir a un programa, y haga clic en **Acciones** ⇒ **Agregar al Programa**. Se abrirá una ventana emergente donde tendrás que seleccionar el Programa al que se añadirán estos cursos. La ventana también tiene una casilla de verificación para indicar si todos los cursos seleccionados deben ser obligatorios para este programa o no.

## 15. Importar notas existentes

SeminaryERP utiliza un único proceso para aceptar calificaciones de otros seminarios que también sirven para importar calificaciones de cualquier sistema heredado, manualmente o a través de CSV. Vea [Legacy Grade Import](legacy-grade-import.md) para el flujo de trabajo completo — configuración seminaria de Partner única, creación de equivalencia en masa, validación de gestión seca y commit idempotente.

## 16. Añadir instructores

Crea un registro de **Instructor** para cada persona que enseñará. Cada instructor necesita un **Usuario del Sistema** enlazado (para que puedan iniciar sesión en el escritorio y LMS) y un **Tipo de instructor** que refleje cómo son pagados:

- **Voluntario**: no pagado o solo honorario. Haga clic en _Crear proveedor_ en el formulario para habilitar la facturación de honorario a través de la factura de compra.
- **Salariado** o **por curso** — requiere [HRMS Payroll activado](../modules/instructor-payment.md) y un registro vinculado a los empleados.

Para acreditación, rellene la sección **Educación** con los títulos, instituciones y documentos de apoyo de cada instructor. Cuando un Empleado está enlazado, utilice _Educación → Tirar del Empleado_ para copiar la educación ya registrada en HRMS en lugar de volver a introducirla.

---

Una vez que lo anterior esté en su lugar, procede a [Tu primer término](first-term.md).
