# Anuncios

Los Anuncios del seminario le permiten enviar un único mensaje a todos los estudiantes inscritos en este período, a todos los instructores que enseñan en este período o a cualquier combinación que necesite. Los mensajes se entregan por correo electrónico y también aparecen dentro de la aplicación de estudiantes/instructores en **Anuncios**. Los destinatarios se resuelven a partir de datos en vivo en el momento del envío, por lo que los estudiantes que se inscriben o se dan de baja entre la redacción y el envío se incluyen correctamente.

## Cuándo usarlo

- Recordatorios de plazos (fechas de baja, ventanas de examen, envío de calificaciones).
- Cambios en el campus o en el calendario (cierres, feriados, cambios de horario).
- Avisos de políticas o administrativos que deben llegar a toda una audiencia a la vez.

Para mensajes con alcance a un único curso (una clase de estudiantes y su instructor), use el panel de **Anuncios** del propio curso dentro de la página del curso. Los Anuncios del seminario son para audiencias que abarcan múltiples clases.

---

## Quién puede enviar

El rol **Usuario de Académicos** puede crear, enviar y cancelar Anuncios del seminario. Los estudiantes y los instructores pueden leer los anuncios que recibieron, pero no pueden redactarlos.

---

## Crear un anuncio

Abra **Desk → Anuncio del seminario → Nuevo**.

### 1. Asunto y mensaje

- **Asunto** — la línea de asunto del correo electrónico. Manténgalo breve y específico: "Semana de parciales — cierre del edificio el viernes" es mejor que "Anuncio importante".
- **Período académico** — predeterminado al período actual. Cámbielo solo si anuncia algo para un período diferente (p. ej., un aviso previo para la audiencia del próximo período).
- **Mensaje** — el cuerpo. Texto enriquecido completo: encabezados, listas, enlaces, negritas, imágenes incrustadas.

### 2. Audiencia

Los anuncios resuelven su lista de destinatarios a partir de consultas en vivo. Elija una o más reglas de audiencia: se combinan (unión) y luego se deduplican por correo electrónico.

| Regla                                                    | A quién incluye                                                                                                                                                                                                                                                                                                                     |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Todos los estudiantes inscritos en este período**      | Todo estudiante con una inscripción en un curso, no retirada, en un Horario del curso del período seleccionado.                                                                                                                                                                                                     |
| **Todos los instructores que enseñan en este período**   | Todo instructor listado en cualquier Horario del curso para el período seleccionado.                                                                                                                                                                                                                                |
| **Solo estos programas**                                 | Restringe la audiencia de estudiantes a los programas listados. Dejar vacío para todos los programas. No afecta a los instructores.                                                                                                                                                 |
| **Solo estos Horarios del curso**                        | Restringe a esas secciones específicas. Incluye a los estudiantes de esas secciones y — si también se marca "Todos los instructores que enseñan en este período" — solo a los instructores de esas secciones. Use esto para enviar un mensaje a "todos en Teología 101, Sección A". |
| **Filtro personalizado** _(avanzado)_ | Elija cualquier DocType y un filtro JSON. Útil para casos límite: "todos los estudiantes del programa MDiv con una baja pendiente", "todos los instructores de un departamento específico".                                                                                         |

Debe elegir al menos una regla. De lo contrario, el envío se bloqueará.

### 3. Vista previa de destinatarios

Antes de enviar, guarde el borrador y haga clic en **Vista previa de destinatarios** en el menú superior derecho del formulario. Un cuadro de diálogo muestra el recuento total y una muestra de hasta 50 filas (tipo, nombre, correo electrónico). Use esto para comprobar que no haya apuntado accidentalmente al programa equivocado o que no haya olvidado un curso.

Si el recuento de la vista previa es cero, sus reglas de audiencia son demasiado restrictivas; en ese estado tampoco se enviará nada. El formulario le indicará lo mismo en el momento del envío.

### 4. Enviar inmediatamente o programar

- Deje **Enviar el** en blanco para enviar en el momento en que lo envíe.
- Rellene **Enviar el** con una fecha/hora futura para programar. El anuncio se guarda con estado **En cola** y lo recoge el programador que se ejecuta cada hora. La granularidad es de aproximadamente una hora; no use esto para mensajes sensibles al tiempo que deban salir en un minuto exacto.

### 5. Enviar

Haga clic en **Enviar**. En este momento:

1. Se ejecuta la consulta de audiencia y la lista resultante se congela en la pestaña **Destinatarios** como un registro de auditoría permanente.
2. Si el envío es inmediato, los correos se ponen en cola de inmediato; si está programado, se ponen en cola en el siguiente ciclo del programador después del valor de **Enviar el**.
3. El estado avanza **Borrador → En cola → Enviando → Enviado**. Una transacción SMTP fallida para un destinatario marca esa fila como **Fallido** y se registra; el resto de la lista sigue enviándose.

Una vez enviado, el anuncio queda bloqueado: no puede editar el asunto, el cuerpo ni la audiencia. Si necesita corregir algo, cancele y enmiende (o simplemente cree un nuevo anuncio).

---

## Dónde lo ven los destinatarios

En dos lugares:

- **Correo electrónico** — entregado a través de la Cuenta de correo saliente configurada del seminario.
- **Anuncios** en la barra lateral de la aplicación: los estudiantes y los instructores ven una lista de todos los anuncios que recibieron, el más reciente primero, dentro de la aplicación principal. No se requiere iniciar sesión en Desk.

La lista dentro de la aplicación empareja a los destinatarios por cuenta de usuario o por correo electrónico, por lo que funciona incluso para quienes no inician sesión con el mismo correo con el que reciben los mensajes.

---

## Seguimiento de la entrega

Abra un anuncio enviado y vaya a la pestaña **Destinatarios**. Cada fila muestra la parte (Estudiante / Instructor / personalizado), el correo electrónico y un **Estado**:

- **Enviado** — correo aceptado por el servidor saliente.
- **Fallido** — un error de entrega. La columna **Error** contiene el mensaje.
- **Pendiente** — aún no recogido (programado para más tarde o en curso).

El recuento de destinatarios y el estado general del anuncio en la parte superior le ofrecen una vista de un vistazo. Profundice en la pestaña para ver el detalle por persona.

---

## Tareas comunes

### Enviar un recordatorio a un programa específico

1. Nuevo Anuncio del seminario.
2. Marque **Todos los estudiantes inscritos en este período**.
3. En **Solo estos programas**, agregue el programa. Deje instructores y cursos en blanco.
4. Vista previa: confirme que solo se muestren los estudiantes del programa correcto. Enviar.

### Enviar un mensaje conjuntamente a los estudiantes y al instructor de una sección

1. Nuevo Anuncio del seminario.
2. Marque **Todos los estudiantes inscritos en este período** y **Todos los instructores que enseñan en este período**.
3. En **Solo estos Horarios del curso**, agregue la sección.
4. Vista previa. Enviar. La lista de estudiantes se restringe a esa sección; la lista de instructores se restringe a los instructores de esa sección.

### Enviar correo a todas las personas que enseñan, en todos los programas

1. Nuevo Anuncio del seminario.
2. Marque **Todos los instructores que enseñan en este período**. Deje todo lo demás en blanco.
3. Vista previa. Enviar.

### Enviar correo a un segmento personalizado (avanzado)

Use **Filtro personalizado** cuando ninguna de las reglas incorporadas se ajuste:

- **DocType del filtro:** el DocType que consultar (`Student`, `Instructor` o cualquier elemento con un campo de correo).
- **Campo de correo:** el nombre de la columna de correo en ese DocType (p. ej., `student_email_id` para Student, `prof_email` para Instructor).
- **Filtros (JSON):** una expresión de filtro de Frappe, p. ej., `[[\"Student\",\"enabled\",1]]`.

Combínelo con las reglas incorporadas o úselo por sí solo.

---

## Preguntas frecuentes

**¿Puedo editar un anuncio después de enviarlo?**
No. Al enviar, se congelan el asunto, el cuerpo y la instantánea de destinatarios; esto es intencional, para que lo enviado siempre coincida con lo que consta en el registro. Si necesita corregir algo, cancele y envíe un nuevo anuncio indicando la corrección.

**¿Qué sucede si la Cuenta de correo saliente no está configurada?**
El envío igualmente tiene éxito: los destinatarios se congelan y las filas entran en estado Pendiente, pero no sale ningún correo del sistema. Configure o corrija la Cuenta de correo y la cola se vaciará en el siguiente intento.

**¿Qué ocurre si un estudiante se da de baja entre la redacción y el envío?**
La lista de destinatarios se congela en el momento de presentar, no en el de enviar. Si alguien se da de baja entre la presentación y el envío programado, seguirá recibiendo el mensaje. Si necesita volver a resolver los destinatarios, cancele el anuncio en cola y cree uno nuevo más cerca de la hora de envío.

**¿Puedo programar un anuncio para que se repita?**
No: cada anuncio es de una sola vez. Para recordatorios recurrentes (recordatorios mensuales de matrícula, advertencias semanales de asistencia), use en su lugar Notificaciones de Frappe con un activador programado.

**¿Esto respeta las preferencias de cancelación de suscripción?**
Sí. Se aplican las reglas estándar de la cola de correo de Frappe: cualquiera que se haya dado de baja de los correos de este seminario se omite.
