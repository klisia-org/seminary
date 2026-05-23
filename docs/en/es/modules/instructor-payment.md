# Pago a instructores

SeminaryERP admite tres formas diferentes de pagar a los instructores: como **voluntarios** que reciben honorarios, como empleados **asalariados**, o con base **por curso / por estudiante**. Esta página le guía para configurarlo todo.

## Descripción general

Cada registro de instructor tiene un campo **Tipo de instructor**. Elija la opción que describe cómo la escuela compensa a esa persona:

| Tipo de instructor | Cómo se les paga                                                  | Qué tendrá que configurar                                                              |
| ------------------ | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| **Voluntario**     | Honorarios / "ofrenda de amor" por visita                         | Un registro de Proveedor + Facturas de compra                                          |
| **Asalariado**     | Salario fijo y recurrente                                         | Empleado estándar de HRMS + Estructura salarial                                        |
| **Por curso**      | Pagado por curso impartido, opcionalmente por estudiante inscrito | Empleado de HRMS + el componente Pago del instructor (automatizado) |

Puede combinarlo en su profesorado — algunos asalariados, otros por curso y otros voluntarios — todos en el mismo sistema de nómina.

El flujo de **Voluntario** funciona por sí solo sin aplicaciones adicionales. Los flujos de **Asalariado** y **Por curso** requieren que la aplicación Frappe HRMS esté instalada en su sitio.

---

## Requisitos previos (solo para Asalariado y Por curso)

Omita esta sección si solo planea pagar a voluntarios mediante Factura de compra.

### 1. Instalar HRMS

Pida a su administrador de bench que instale la aplicación Frappe HRMS en su sitio. Desde la terminal de bench, esto es:

```
bench get-app hrms
bench --site <your-site> install-app hrms
```

> **Nota:** HRMS `v16.5.1` tiene un error conocido de instalación con ERPNext v16. Si la instalación falla con un error `repost_allowed_types`, fije HRMS a la etiqueta `v16.4.8`:
>
> ```
> cd ~/frappe-bench/apps/hrms
> git checkout v16.4.8
> ```
>
> …luego vuelva a intentar `bench install-app hrms`.

### 2. Habilitar la Nómina de HRMS en Configuración del seminario

Abra **Configuración del seminario** en Desk, desplácese a la sección **RR. HH. / Nómina** y marque **Habilitar Nómina de HRMS**. Guardar.

Al guardar se hará lo siguiente:

- Se agregarán los campos de pago de instructor por categoría a cada Recibo de salario.
- Se creará un Componente salarial listo para usar llamado **"Pago del instructor"**.

Si ve un error que indica que HRMS no está instalado, vuelva al paso 1.

### 3. Establecer la Fecha de inicio de HRMS

Aún en **Configuración del seminario → RR. HH. / Nómina**, complete **Fecha de inicio de HRMS (corte de pago)** con la fecha en que su escuela comenzará a usar HRMS para la nómina.

Los cursos cuya fecha de inicio sea **anterior** a este corte _no_ aparecerán en la nómina. Esto le protege de incluir accidentalmente años de cursos históricos en su primera ejecución de nómina. Déjelo en blanco solo si desea incluir todos los cursos registrados.

### 4. Elegir una política de distribución de pagos

**División del pago al instructor** indica al sistema cuándo se libera el pago por curso a lo largo de las ejecuciones de nómina:

- **Fin del período** _(predeterminado)_: el importe total se paga en el Recibo de salario cuyo período contiene la fecha de finalización del curso.
- **50% al inicio + 50% al final**: la mitad se paga en el Recibo de salario que contiene la fecha de inicio del curso y la otra mitad en el Recibo de salario que contiene la fecha de finalización del curso.

Elija una. Puede cambiarla más adelante, pero los cambios solo afectarán a los cursos pagados en adelante.

---

## Categorías de instructores

Cada instructor asignado a un curso lleva una **Categoría** — "Instructor responsable", "Asistente de docencia de posgrado", "Calificador", etc. Las categorías impulsan dos cosas: los informes de acreditación y cuánto gana el instructor.

El sistema incluye cuatro categorías predeterminadas: **Instructor responsable**, **Co-instructor**, **Asistente de docencia de posgrado**, **Calificador**. Puede agregarlas, renombrarlas u ocultarlas en **Desk → Categoría de instructor**.

Nota: Actualmente no hay configuración para pagos diferentes por programa o nivel de programa. Si esto es importante para usted, cree un issue en nuestro repositorio de GitHub. Una forma de hacerlo sin programar es simplemente crear una categoría nueva, p. ej., "Instructor of Record - PhD" con valores de tarifa de pago diferentes.

### Vincular tarifas de pago a una categoría

Abra una Categoría de instructor y desplácese hasta **Tarifas de pago**. Cada fila es una tarifa:

| Columna           | Qué significa                                                                                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Modo de pago**  | `Por curso` (importe fijo por curso) o `Por estudiante` (importe × número de inscritos)   |
| **Importe**       | Cuánto pagar                                                                                                                    |
| **Moneda**        | La moneda para esta tarifa (admite USD para programas financiados por donantes y moneda local para lo local) |
| **Vigente desde** | La fecha en que esta tarifa entra en vigor                                                                                      |
| **Activo**        | Marque la tarifa vigente. Desmarque las anteriores para mantener el historial visible pero sin uso              |

Puede tener simultáneamente una fila Por curso y una fila Por estudiante activas: el sistema paga ambas. Para cambiar una tarifa, **desmarque Activo en la fila anterior** y **agregue una nueva fila** con el nuevo importe y una nueva fecha de **Vigente desde**. Esto mantiene preciso el historial de pagos de los Recibos de salario anteriores.

#### Ejemplo: categoría "Instructor responsable"

| Modo de pago   | Importe | Moneda | Vigente desde | Activo                                 |
| -------------- | ------- | ------ | ------------- | -------------------------------------- |
| Por curso      | 200     | USD    | 2024-01-01    | ☐ (tarifa anterior) |
| Por curso      | 300     | USD    | 2026-01-01    | ☑ (vigente)         |
| Por estudiante | 10      | USD    | 2024-01-01    | ☑                                      |

Un Instructor responsable que imparta un curso en Otoño de 2025 con 8 estudiantes ganaría 200 + 80 = **$280**. El mismo curso en Primavera de 2026 ganaría 300 + 80 = **$380**.

---

## Asignar una categoría en cada curso

Cuando crea o edita un **Horario del curso**, la tabla **Instructores** ahora tiene una columna **Categoría**. Elija la categoría para cada instructor en ese curso. La categoría determina qué tarifas se aplican para esa persona en ese curso específico.

Cuando la Nómina de HRMS está habilitada, se bloquea guardar un Horario del curso sin una categoría en cada fila de instructor; esto evita olvidar el pago de alguien.

Después de asignar instructores, abra una vez el registro de cada instructor y haga clic en **Actualizar registro de instructor** (o espere a que se actualice en la próxima carga). Esto sincroniza el curso con su registro, que es de donde lee la nómina.

---

## Configurar cada flujo de pago

### Flujo de voluntario

Para conferencistas invitados o profesores visitantes que reciben un honorario:

1. Cree el registro de **Instructor** con **Tipo de instructor = Voluntario**.
2. Abra el formulario del Instructor y haga clic en **Acciones → Crear Proveedor**. Se crea automáticamente un registro de Proveedor con el nombre, correo electrónico y teléfono copiados del Instructor. El vínculo al Proveedor se guarda de vuelta en el Instructor.
3. Cada vez que quiera pagar al voluntario, cree una **Factura de compra** contra ese Proveedor. Agregue un Artículo (p. ej., "Honorario de instructor") y el importe.
4. Envíe la **Factura de compra** y luego cree una **Entrada de pago** para desembolsar.

Los voluntarios **no** necesitan un registro de Empleado y **no** aparecen en la **Entrada de nómina**. Su compensación se registra en el libro mayor habitual de proveedores.

### Flujo de asalariado

Para personal de tiempo completo o de medio tiempo con salario recurrente:

1. Cree el registro de **Empleado** (módulo de RR. HH.).
2. Cree o edite el registro de **Instructor** y establezca **Tipo de instructor = Por curso**. Vincúlelo al Empleado.
3. Cree una **Estructura salarial** (p. ej., "Instructor — Tiempo completo") con los Componentes salariales que necesite (Base, asignaciones, deducciones).
4. Cree una **Asignación de estructura salarial** que conecte al Empleado con la Estructura.
5. Ejecute la **Entrada de nómina** en su calendario mensual habitual. HRMS hace el resto.

No se requiere configuración específica del seminario: esto es HRMS estándar.

### Flujo por curso

Para instructores pagados por curso impartido:

1. Cree el registro de **Empleado**.
2. Cree o edite el registro de **Instructor** y establezca **Tipo de instructor = Asalariado**. Vincúlelo al Empleado.
3. Asegúrese de que la Categoría de instructor asignada en cada Horario del curso de este instructor tenga **Tarifas de pago** definidas (vea la sección anterior).
4. Cree una **Estructura salarial** llamada algo como "Instructor — Por curso". En la tabla **Ingresos**, agregue una sola fila:
   - **Componente salarial:** `Pago del instructor` _(este componente se creó automáticamente cuando habilitó la Nómina de HRMS; no lo vuelva a crear)_
5. Asigne la Estructura al Empleado mediante **Asignación de estructura salarial**.

Eso es todo. Cuando se ejecuta la Entrada de nómina, el sistema calcula el pago según los cursos impartidos en ese período × las tarifas de la categoría y coloca el resultado en el Recibo de salario.

No necesita componentes por categoría ("Pago IoR", "Pago GTA"). El único componente "Pago del instructor" gestiona todas las categorías, porque las tarifas residen en las propias categorías.

---

## Ejecución de la nómina

Ejecute **Entrada de nómina** del mismo modo que siempre:

1. HH. → Nómina → Entrada de nómina → Nuevo\*\*.
2. Defina las fechas del período, la empresa y el filtro de **Asignación de estructura salarial**.
3. Enviar. HRMS genera un Recibo de salario por empleado.

Abra un recibo generado. Cerca de la parte superior, en la sección **Entradas de pago del instructor**, verá:

- **Pago del instructor calculado**: el total calculado.
- **Resumen del registro de instructor**: un desglose de solo lectura que muestra, para cada curso pagado en este recibo: el curso, la categoría, la tarifa aplicada, la porción (100% o 50%), el evento de pago (Inicio / Fin) y el subtotal.

Este es su rastro de auditoría. Si algo parece incorrecto, esta tabla le indica exactamente qué cursos y tarifas se utilizaron.

### Volver a ejecutar una nómina

Si cancela un Recibo de salario y vuelve a ejecutar la Entrada de nómina, el sistema excluye automáticamente los cursos que se pagaron en el recibo cancelado. **No puede pagar doble por accidente.**

---

## Conciliación: el informe Registro de instructor no pagado

Después de cada ciclo de nómina, consulte **Informes → Registro de instructor no pagado**. Enumera cada fila de enseñanza (instructor × curso) cuyo período haya finalizado pero que no se haya pagado al 100%.

Esto detecta los errores habituales:

- Un instructor que no tiene un Empleado vinculado, por lo que se omitió.
- Un Horario del curso sin categoría asignada (no debería ocurrir con la validación activada, pero se detecta si sucede).
- Una categoría sin tarifa de pago definida.
- Una ejecución de nómina que simplemente no se realizó en un mes determinado.

Los filtros en la parte superior le permiten acotar por instructor, período académico o categoría.

---

## Tareas del día a día

### Agregar una nueva Categoría de instructor

1. **Desk → Categoría de instructor → Nuevo**. Asígnele un nombre, una descripción y marque **¿Es Instructor responsable?** si debe contar para la acreditación.
2. Abra **Configuración del seminario** y guárdela una vez (no se requieren cambios; solo Guardar). Esto actualiza los campos del Recibo de salario para que los contadores de la nueva categoría aparezcan en recibos futuros.
3. Agregue tarifas de pago a la categoría como se describió anteriormente.

### Cambiar una tarifa (p. ej., aumento de fin de año)

1. Abra la Categoría de instructor.
2. En la fila activa actual de **Tarifas de pago**, **desmarque Activo**.
3. Agregue una nueva fila con el nuevo importe y una nueva fecha de **Vigente desde**.
4. Guardar.

Los recibos históricos seguirán usando automáticamente la tarifa anterior (según la fecha de inicio del curso), por lo que la nómina pasada no se ve afectada.

### Comenzar un nuevo año académico con una nueva Fecha de inicio

Si desea restablecer qué cuenta para la nómina de HRMS (p. ej., su primer año usó una política piloto), actualice **Configuración del seminario → Fecha de inicio de HRMS** al nuevo corte. Solo se considerarán los cursos que comiencen en o después del nuevo corte.

---

## Preguntas frecuentes

**¿Puede el mismo instructor tener categorías diferentes en distintos cursos?**
Sí. La categoría es por fila de Instructor en el Horario del curso, no por instructor. Un profesor podría ser "Instructor responsable" en un curso y "Co-instructor" en otro.

**¿Qué sucede si olvido asignar una categoría a un curso?**
Cuando la Nómina de HRMS está habilitada, guardar el Horario del curso se bloquea hasta que cada fila de instructor tenga una categoría. Las categorías también son en blanco por defecto; puede usar un script o una actualización masiva para rellenarlas.

**¿Qué pasa si un curso intensivo se ejecuta dentro de un período más amplio?**
Complete **Fecha de inicio** y **Fecha de finalización** en el propio Horario del curso. Cuando se establecen esas fechas, el sistema las usa en lugar de las fechas del período académico; así, un intensivo de dos semanas se paga en el recibo cuyo período contiene el final del intensivo, no el del período.

**¿Qué pasa si un voluntario luego se convierte en instructor remunerado?**
Cambie su **Tipo de instructor** de Voluntario a Asalariado o Por curso. Vincúlelo a un registro de Empleado. El vínculo antiguo al Proveedor permanece (para Facturas de compra históricas), pero se ignora en adelante.

**¿Puedo ver cuánto pagará un recibo antes de ejecutarlo?**
Sí. Cree manualmente un **Recibo de salario** para el empleado y el período; la sección **Resumen del registro de instructor** se completa en cuanto lo guarde como borrador.
