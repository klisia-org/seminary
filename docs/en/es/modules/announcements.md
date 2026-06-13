# Anuncios

Seminary Announcements let you send a single message to everyone enrolled this term, everyone teaching this term, all alumni, or any combination you need. Messages are delivered over the channels you choose — email and the in-app inbox by default, with SMS, WhatsApp, and Telegram available for urgent reach. Los destinatarios se resuelven a partir de datos en vivo en el momento del envío, por lo que los estudiantes que se inscriben o se dan de baja entre la redacción y el envío se incluyen correctamente.

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

### 1. Subject, category, and message

- **Subject** — the email/message subject line. Manténgalo breve y específico: "Semana de parciales — cierre del edificio el viernes" es mejor que "Anuncio importante".
- **Academic Term** — required when the audience is term-scoped (enrolled students, teaching instructors, or specific course schedules); optional for an all-alumni or custom-filter broadcast. Defaults to the current term.
- **Category** — the routing/consent class (default **Academic**). Most announcements are Academic. Choose **Emergency** for a genuine calamity (campus closure, safety alert): Emergency messages **bypass recipient opt-outs and the hourly send throttle** so they reach everyone at once. Promotional messages only reach recipients who have opted in.
- **Send via channels** — leave empty to send **Email + In-App** (the default). Add **SMS**, **WhatsApp**, **Telegram** (urgent reach), **Voice** (an automated call that reads the message), or **Print** (a PDF letter to mail). Each needs a configured provider account — see [Communication](communication.md); Print works out of the box. Submit is blocked if you pick a channel with no provider account configured.
- **Mensaje** — el cuerpo. Texto enriquecido completo: encabezados, listas, enlaces, negritas, imágenes incrustadas. Used for Email, In-App, **and Print** (the printed letter). You can personalize it with Jinja tokens that resolve per recipient: <code v-pre>{{ recipient.first_name }}</code>, <code v-pre>{{ recipient.name }}</code>, <code v-pre>{{ recipient.email }}</code> (and <code v-pre>{{ person.\* }}</code> for spine fields). Example: <code v-pre>"Dear {{ recipient.first_name }},"</code>. Syntax errors are caught when you save.
- **Voice Recording** — _(shown when Voice is selected)_ an optional MP3/WAV the call plays instead of reading the text aloud (e.g. the director records the message). Up to ~40 MB; the file is made public so the carrier can fetch it.
- **Short Message** — a plain-text version for the length-limited / spoken channels (SMS, WhatsApp, Telegram, Voice). Leave it blank and the system strips the rich message down to plain text automatically; fill it in when you want a tighter wording for a 160-character world or a call.
- **Email + In-App fallback** _(on by default)_ — if a recipient can't be reached on any selected channel (no phone/Telegram connected, or opted out), they're sent Email + In-App instead, so the announcement still arrives. Email is always available. Turn it off only if you want a channel-exclusive send.

#### Print options

When **Print** is among the channels, a **Print Options** section appears:

- **Letter Head** — _Seminary Default_ (the one set in Seminary Settings), _None_, or _Specific_ (pick any Frappe Letter Head). The chosen letterhead wraps the printed PDF letter.
- **Print mailing labels** — also produce a sheet of mailing labels (PDF). Pick a **Label Format** — a **Mailing Label Format** record. Common Avery layouts (5160, 5161, 5163, L7160) are shipped; a seminary can add its own by measuring its label stock (columns, rows, label size, margins in mm) under **Mailing Label Format**. Use the **Mailing Labels (PDF)** button to generate/download; labels are also attached to the announcement when it's sent. Labels are produced for recipients with a postal address (on their Person record, or a Student record); those without one are listed as omitted so you know who to follow up.

**Printing the letters.** While drafting, **Letter Preview (PDF)** shows a single letter (subject + message in the letter head, personalized for one recipient) so you can check the layout. After you **submit**, the button becomes **Print Letters (PDF)**: the official, consolidated document — every recipient's personalized letter, one per page, ready to print and mail. It's also generated automatically on send and attached to the announcement (alongside the mailing labels), so the finished letters live on the announcement itself.

### 2. Audiencia

Los anuncios resuelven su lista de destinatarios a partir de consultas en vivo. Elija una o más reglas de audiencia: se combinan (unión) y luego se deduplican por correo electrónico.

| Regla                                                    | A quién incluye                                                                                                                                                                                                                                                                                                                     |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Todos los estudiantes inscritos en este período**      | Todo estudiante con una inscripción en un curso, no retirada, en un Horario del curso del período seleccionado.                                                                                                                                                                                                     |
| **Todos los instructores que enseñan en este período**   | Todo instructor listado en cualquier Horario del curso para el período seleccionado.                                                                                                                                                                                                                                |
| **All alumni**                                           | Every enabled Alumni Profile. Term-independent — ignores the term/program/course narrowing. Use for alumni newsletters or invitations.                                                                                                                                              |
| **Solo estos programas**                                 | Restringe la audiencia de estudiantes a los programas listados. Dejar vacío para todos los programas. No afecta a los instructores.                                                                                                                                                 |
| **Solo estos Horarios del curso**                        | Restringe a esas secciones específicas. Incluye a los estudiantes de esas secciones y — si también se marca "Todos los instructores que enseñan en este período" — solo a los instructores de esas secciones. Use esto para enviar un mensaje a "todos en Teología 101, Sección A". |
| **Filtro personalizado** _(avanzado)_ | Elija cualquier DocType y un filtro JSON. Útil para casos límite: "todos los estudiantes del programa MDiv con una baja pendiente", "todos los instructores de un departamento específico".                                                                                         |

Debe elegir al menos una regla. De lo contrario, el envío se bloqueará.

### 3. Vista previa de destinatarios

Antes de enviar, guarde el borrador y haga clic en **Vista previa de destinatarios** en el menú superior derecho del formulario. A dialog shows a reachability tally — **how many are reachable on the channels you picked**, broken down per channel, and how many will rely on the Email/In-App fallback — plus a sample of up to 50 rows with a ✓/✗ **Reachable** column (with the reason: "no address" or "opted out"). Use this to sanity-check the audience _and_ to spot, before sending, when an urgent SMS/WhatsApp blast would actually reach only a fraction of people (e.g. "SMS 12 of 32") so you can act on it.

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

Wherever you sent it:

- **Correo electrónico** — entregado a través de la Cuenta de correo saliente configurada del seminario.
- **In-App** — the **Inbox / Announcements** in the app sidebar lists every message a person received, most recent first. No se requiere iniciar sesión en Desk.
- **SMS / WhatsApp / Telegram** — if selected and the recipient has a number/chat connected for that channel, the Short Message is delivered there too.

La lista dentro de la aplicación empareja a los destinatarios por cuenta de usuario o por correo electrónico, por lo que funciona incluso para quienes no inician sesión con el mismo correo con el que reciben los mensajes. A recipient who has no address for a chosen channel (e.g. no Telegram connected) simply doesn't get that copy; the other channels still go out.

---

## Seguimiento de la entrega

Abra un anuncio enviado y vaya a la pestaña **Destinatarios**. Cada fila muestra la parte (Estudiante / Instructor / personalizado), el correo electrónico y un **Estado**:

- **Sent** — at least one of the chosen channels reached the recipient (any successful channel marks the recipient Sent).
- **Failed** — every channel attempted for that recipient failed. La columna **Error** contiene el mensaje.
- **Pendiente** — aún no recogido (programado para más tarde o en curso).

El recuento de destinatarios y el estado general del anuncio en la parte superior le ofrecen una vista de un vistazo. Profundice en la pestaña para ver el detalle por persona. For full per-channel detail (which channels were tried, delivery receipts), open the recipient's Person record and its **Conversation** tab, or the **Communication Log** list filtered by this announcement.

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

**Does this respect unsubscribe preferences?**
Yes, by category. A recipient who has opted out of the announcement's category on a channel is skipped for that channel — except for **Emergency** announcements, which are delivered regardless of consent. Promotional announcements only reach recipients who have explicitly opted in. Recipients manage these preferences on their portal **Preferences** page.
