# Requisitos de Graduación

El Program Audit siempre ha respondido a la pregunta: _"¿este estudiante ha obtenido
suficientes créditos y aprobado los cursos requeridos?"_ Pero muchos seminarios gradúan
estudiantes contra una lista más larga: asistencias a capilla, entrevistas de ordenación,
cartas de recomendación, declaraciones doctrinales, horas de prácticas, una tesis o
trabajo final. El módulo de **Requisitos de Graduación** captura todo lo que
_no_ es un curso, permite a la secretaría crearlo desde Desk sin código y alimenta
el resultado en la misma página Program Audit que estudiantes y asesores ya
usan.

## Descripción general

Piense en la graduación como **dos vías paralelas**:

| Vía                                            | Dónde se configura                                              | Qué responde                                                                                                                                               |
| ---------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Académico** — créditos y cursos obligatorios | Program → tabla Courses                                         | ¿El estudiante ha aprobado los cursos correctos y acumulado suficientes créditos?                                                                          |
| **Requisitos de Graduación** — todo lo demás   | Program Graduation Requirement (este módulo) | ¿El estudiante también ha cumplido con la evidencia no relacionada con cursos (cartas, asistencias, proyectos, declaraciones firmadas)? |

Ambas vías se consolidan en la página Program Audit. Un estudiante es
`graduation_eligible` solo cuando **todos los elementos obligatorios activos** en
**ambas** vías están en verde. Las dos vías se evalúan de forma independiente: un
estudiante al que le falte una asistencia a capilla no queda bloqueado para registrarse en
cursos, y un estudiante que aún no ha terminado su último curso no queda
bloqueado para enviar sus cartas de recomendación.

## Las tres capas

El módulo está construido en tres capas. Pasará la mayor parte del tiempo en las dos primeras.

```
1. Biblioteca      — Graduation Requirement Item        (defínalo una vez, reutilícelo en cualquier lugar)
                    │
2. Política        — Program Graduation Requirement     (vincular a un programa, con fechas)
                    │
3. Instancia       — Student Graduation Requirement     (una fila por estudiante, congelada al matricularse)
```

### Capa 1 — La Biblioteca

Un **Graduation Requirement Item** declara _qué tipo de elemento existe en el
seminario_. Lo define una vez, con instrucciones para los estudiantes, y lo reutiliza
a través de tantos programas como desee.

Cada elemento de biblioteca elige **uno** de tres tipos:

- **Event Attendance** — se cumple cuando un estudiante asiste a un
  [Event](../modules/academic-calendar.md) específico. Ejemplo: _"Retiro de Formación Espiritual
  2027"_. Elija **Event per Student** si cada estudiante debe presentarse
  individualmente; déjelo sin marcar si una sola ocurrencia (un servicio de capilla
  único al que todos asisten juntos) satisface a la cohorte.
- **Manual Verification** — se cumple cuando el personal confirma que el estudiante hizo
  lo requerido, opcionalmente con evidencia en archivo del estudiante, del personal o
  de ambos. Ejemplo: _"Declaración doctrinal firmada"_, _"Asistencia a capilla"_ (8
  en total).
- **Linked Document** — se cumple cuando otro documento del sistema
  alcanza un estado específico. Ejemplo: una _Recommendation Letter_ pasa a
  `Approved`, o un _Culminating Project_ pasa a `Completed`.

Dos indicadores controlan la evidencia en los elementos de Manual Verification:

- **Evidence Submitted by Student** — ofrece al estudiante un botón de carga en
  su página de auditoría. Úselo para cosas como un formulario de acuse de recibo firmado
  que el propio estudiante adjunta.
- **Evidence Required by Staff** — el personal debe adjuntar un archivo al marcar el
  elemento como Fulfilled. Úselo para elementos que debe conservar en el expediente (una declaración
  doctrinal firmada, actas escaneadas del concilio de ordenación).

Estos dos indicadores son independientes. Una declaración doctrinal podría requerir _ambos_
(el estudiante carga el PDF firmado y el personal carga su nota de verificación de identidad). La asistencia a capilla normalmente no requiere _ninguno_ — el personal solo
marca Fulfilled.

> **¿Por qué dos indicadores?** Algunos elementos, como la asistencia a capilla, son simples — el personal
> marca una casilla. Otros, como una declaración doctrinal, necesitan un documento escrito del
> estudiante _y_ una verificación de identidad por parte del personal. Un solo par de campos
> puede modelar ambos casos.

#### Blocks Graduation Request

Si su seminario usa el flujo de [Graduation Request](graduation-request.md),
cada elemento de biblioteca tiene un indicador más — **Blocks Graduation Request**
(visible solo cuando `Mandatory` está marcado). Cuando está definido, el estudiante no puede
ni siquiera _presentar_ una Graduation Request hasta que este requisito esté `Fulfilled` o
`Waived`. Úselo para prerrequisitos estrictos que la Secretaría Académica quiere
verificar por adelantado: cartas de recomendación, tesis, declaraciones doctrinales.
Los elementos sin ese indicador igualmente se siguen para la elegibilidad de graduación,
pero el estudiante puede presentar la solicitud y el paso de revisión académica
detectará cualquier pendiente.

### Capa 2 — La Política

Un **Program Graduation Requirement** vincula elementos de biblioteca a un Program con
fechas de vigencia. Esta es la principal pantalla de autoría de la Secretaría Académica.

Campos en el encabezado de la política:

- **Program** — a qué programa se aplica esta política.
- **Active from / Active until** — la ventana del año de catálogo. Un estudiante que se matricula el 2026-09-01 toma la política cuya ventana contiene esa
  fecha.
- **Is Active** — control para marcar un borrador (o reemplazada) frente a una política publicada.

Dentro de la política, enumere los **elementos de requisito del programa** (las filas de la política).
Cada fila elige un elemento de biblioteca y agrega metadatos de vinculación específicos del programa:

- **Activation Mode** — _cuándo_ el requisito pasa a estar "pendiente" para un
  estudiante matriculado. Véase más abajo.
- **Is Mandatory** — ¿no cumplir esta fila bloquea la graduación, o es
  opcional/informativa?
- **Quantity Required** — solo significativo para Manual Verification (por ej.,
  "8 asistencias a capilla"). Los otros dos tipos siempre cuentan como 1.

#### Modos de activación

Un requisito puede quedar pendiente _el día que el estudiante se matricula_ — o solo tras algún
disparador. Los cuatro modos:

- **Always Active** — pendiente desde el primer día. Úselo para cualquier cosa que el estudiante pueda empezar en cualquier momento (asistencia a capilla, declaración doctrinal).
- **After Requirement** — pendiente solo después de que uno o más _otros_ requisitos en
  esta misma política se hayan cumplido o eximido. Úselo para cadenas de prerrequisitos: _"Ordination Interview"_ queda pendiente solo después de _"Pastoral
  Recommendation Letter"_ y _"Doctrinal Statement"_ estén ambas cumplidas.
- **On Document Status** — pendiente solo después de que un documento relacionado alcance un
  estado dado. El `link_doctype` del elemento de biblioteca y el `linked_doc_status`
  seleccionado juntos definen la compuerta.
- **Time Offset** — pendiente en relación con un ancla de fecha. Elija un ancla
  (Expected Graduation Date, Last Term Starts, Program Starts), un valor de desfase
  y una unidad (Days o Academic Term). _"Recital de último año — pendiente 60 días
  antes de Expected Graduation Date"_ es offset = -60, unit = Days, anchor =
  Expected Graduation Date.

Una fila cuya activación aún no se ha disparado aparece en la auditoría como
_Not Yet Active_, y aunque sea obligatoria **no** bloquea la elegibilidad
de graduación — es "aún no es su problema". Una vez activa, una fila obligatoria sin cumplir bloquea la graduación.

### Capa 3 — La Instancia (instantánea)

Cuando se envía un Program Enrollment, el sistema **toma una instantánea** de la política activa
en filas por estudiante llamadas **Student Graduation Requirements**
(SGR). Una fila SGR por fila de política, multiplicada por la cantidad para los elementos de
Manual Verification.

Esta instantánea queda **congelada para ese estudiante.** Que una secretaría publique una nueva
política en 2027 **no** cambia retroactivamente los requisitos de un
estudiante que se matriculó en 2025. Este es el contrato del año de catálogo: es la regla que los seminarios honran tradicionalmente y se aplica por construcción.

El **Program Enrollment** también almacena la política que tomó
(`graduation_policy`) para que quien revise el expediente pueda rastrear exactamente en
qué año de catálogo está el estudiante.

Si la secretaría realmente necesita migrar a un estudiante a la política actual
(p. ej., el estudiante lo solicitó o un regulador lo exigió), existe una acción
permitida **Resnapshot** en el Program Enrollment. De forma predeterminada
conserva cualquier fila que ya estuviera eximida; la acción queda registrada.

## Ejemplos prácticos

### Ejemplo 1 — Asistencia a capilla (8 servicios por período)

**Objetivo:** todo estudiante debe asistir a 8 servicios de capilla a lo largo del programa.

1. **Cree el elemento de biblioteca.** Desk → Graduation Requirement Item → New.
   - Requirement: `Asistencia a capilla`
   - Type: `Manual Verification`
   - Default Quantity: `8`
   - Obligatorio: ✓
   - Evidence Submitted by Student: ✗
   - Evidence Required by Staff: ✗ (basta con un registro de marcar la casilla)
   - Instructions: _"Se espera que los estudiantes asistan al menos a 8 servicios de
     capilla. La oficina del capellán registra la asistencia de los estudiantes en la puerta."_

2. **Agréguelo a la política del programa.** Desk → Program Graduation Requirement
   → abra _MDiv 2026 Catalog_ → añada una fila apuntando a `Chapel Attendance`.
   - Activation Mode: `Always Active`
   - Quantity Required: `8` (o sobrescriba por programa — p. ej., 4 para una
     maestría a tiempo parcial)

3. **Al matricularse**, el sistema materializa 8 filas SGR por estudiante,
   etiquetadas _"Asistencia a capilla — Casilla 1 de 8"_ hasta _"8 de 8"_.

4. **En el día a día**, la oficina del capellán abre el Program
   Enrollment del estudiante, busca la siguiente casilla _Not Started_ y la marca como
   `Fulfilled`. La página Program Audit se actualiza de inmediato.

### Ejemplo 2 — Tres cartas de recomendación (con casillas con nombre)

**Objetivo:** todo solicitante de graduación presenta tres cartas de recomendación
— _Pastoral_, _Académica_, _Carácter_ — cada una de un tipo diferente
de recomendador, cada una con sus propias instrucciones.

El instinto es usar un solo elemento de biblioteca con `quantity_required = 3`.
**No lo haga.** Cada carta tiene un público diferente e instrucciones diferentes.
En su lugar, cree **tres elementos de biblioteca por separado**:

- _Pastoral Reference Letter_ — Linked Document, destino `Recommendation
    Letter`. Instrucciones: _"Solicítela a su pastor de la iglesia local."_
- _Academic Reference Letter_ — igual. Instrucciones: _"Solicítela a un
  profesor de tu especialidad."_
- _Character Reference Letter_ — igual. Instrucciones: _"Solicítela a
  alguien que le conozca desde hace al menos 5 años y que no sea pariente."_

El estudiante ve tres entradas distintas en la auditoría, cada una con su propia
guía. El doctype Recommendation Letter gestiona el resto: un enlace tokenizado al portal de invitados enviado al recomendador, entrega multicanal
(portal / correo electrónico / carga manual) y un flujo de trabajo que termina en `Approved`.
Cuando la carta es aprobada, la fila SGR pasa a Fulfilled automáticamente.

### Ejemplo 3 — Entrevista de ordenación (después de las cartas)

**Objetivo:** una entrevista de ordenación solo puede programarse _después_ de que ambas
cartas de recomendación estén ingresadas.

1. Cree un elemento de biblioteca Manual Verification _Ordination Interview_
   (Obligatorio, Staff Evidence Required = ✓ con etiqueta _"Acta de la entrevista"_).
2. En la política, añada una fila con **Activation Mode = After
   Requirement** y elija como prerrequisitos las filas de política _Pastoral Reference_ y
   _Academic Reference_.
3. Hasta que ambas cartas estén en estado Fulfilled, la auditoría muestra _"Ordination Interview
   — Not Yet Active"_ y no bloquea la graduación. En el momento en que la segunda
   carta es aprobada, la fila se activa y empieza a contar para la
   elegibilidad.

### Ejemplo 4 — Proyecto de fin de estudios (un doctype vinculado complejo)

**Objetivo:** todo estudiante de MDiv redacta un Proyecto de fin de estudios, defendido en hasta
tres rondas con revisores.

Este es el doctype **Culminating Project**. No necesita modelar el
proyecto usted mismo: viene incluido con el sistema, con su propia tabla de revisores
y un flujo de trabajo de 9 estados.

Para conectarlo a un programa:

1. Cree un elemento de biblioteca _Proyecto de fin de estudios_.
   - Type: `Linked Document`
   - Linked Document: `Culminating Project`
2. Agréguelo a la política con **Activation Mode = Time Offset**, ancla
   `Last Term Starts`, valor `0`, unidad `Days` — es decir, pendiente una vez que inicia el
   último período.
3. Al matricularse, la fila SGR aparece en la instantánea. El estudiante inicia
   el proyecto desde la página de auditoría (un botón _Start Senior Project_); cuando
   el flujo de trabajo del proyecto llega a `Completed`, la fila SGR pasa a
   Fulfilled automáticamente.

### Ejemplo 5 — Declaración doctrinal (firmada por ambas partes)

**Objetivo:** el estudiante firma una declaración doctrinal; la Secretaría Académica
verifica la firma y archiva una copia.

1. Cree un elemento de biblioteca _Doctrinal Statement_.
   - Type: `Manual Verification`
   - Obligatorio: ✓
   - Evidence Submitted by Student: ✓, etiqueta _"Declaración firmada (PDF)"_
   - Evidence Required by Staff: ✓, etiqueta _"Nota de verificación de identidad"_
2. El estudiante carga el PDF firmado en el portal. Su casilla pasa a
   `Submitted`.
3. La secretaría abre la fila SGR, adjunta la nota de verificación y
   hace clic en Fulfilled.

## Día a día para el personal

### Dónde mirar

- **Estado por estudiante** — abra el _Program Enrollment_ del estudiante y
  desplácese hasta la tabla _Student Graduation Requirements_, o abra la
  _página Program Audit_ desde el portal del estudiante (el personal también puede acceder a ella
  desde el Backoffice).
- **Política por programa** — Desk → Program Graduation Requirement → elija la
  política activa del programa.
- **Resumen de cohorte** — una vista de lista de _Student Graduation Requirement_
  filtrada por `status = Not Started` y agrupada por `requirement_name` le muestra
  quién aún debe qué.

### Marcar algo como Fulfilled

Abra la fila SGR (desde el Program Enrollment padre o directamente).
Establezca `status` en `Fulfilled`, adjunte evidencia del personal si el requisito lo
pide y guarde. El sistema sella `verified_by` y `verified_on`
automáticamente.

Para requisitos de Linked Document, normalmente **no** marca la fila SGR
manualmente: el propio flujo de trabajo del documento vinculado la cambiará por usted cuando
llegue al estado configurado.

### Eximir un requisito

A veces, un requisito genuinamente no debería aplicarse a un estudiante en particular
(p. ej., el requisito se agregó para nuevos estudiantes y un estudiante en curso
solicitó formalmente una excepción). En la fila SGR:

1. Marque **Waived**.
2. Ingrese un **Waiver Reason** (un párrafo breve — este es su rastro de auditoría).
3. Guardar. El sistema registra `waived_by` (usted) y `waived_on` (ahora).

Una fila eximida cuenta como satisfecha para la elegibilidad de graduación, pero se distingue
claramente de `Fulfilled` en los reportes.

### Publicar un nuevo año de catálogo

Cuando el seminario cambia sus requisitos, publique una política nueva **junto a** la antigua — _no_ edite la antigua in situ.

1. Duplique el Program Graduation Requirement existente (o cree uno
   nuevo).
2. Defina `Active from` en la fecha en que entra en vigor el nuevo catálogo (p. ej.,
   `2027-09-01`).
3. Defina `Active until` de la política anterior al día anterior
   (p. ej., `2027-08-31`).
4. Marque `Is Active` en la nueva.
5. Ajuste las filas.

Los estudiantes que se matriculen **después** del nuevo `Active from` generarán la instantánea con la
nueva política. Los estudiantes ya matriculados conservan la anterior. Si un estudiante
pide explícitamente pasar al nuevo catálogo, use **Resnapshot** en su
Program Enrollment.

### Agregar un nuevo tipo de documento vinculado sin código

Si más adelante su seminario quiere un _nuevo_ tipo de documento vinculado (por ejemplo,
_Internship Report_ — un doctype que su equipo de TI crea con su propio flujo de trabajo),
**no** necesita editar ningún código. Una vez que exista el doctype con un campo
`workflow_state`:

1. Cree un elemento de biblioteca con `Type = Linked Document` y elija _Internship
   Report_ en `Linked Document`.
2. Agréguelos a las políticas de los programas pertinentes con el modo de activación que
   desee.
3. En cada elemento de biblioteca con `Activation Mode = On Document Status`,
   especifique el estado que señala el cumplimiento (p. ej., `Approved`,
   `Completed`).

El sistema refleja automáticamente los cambios de estado en las filas SGR.

> **Aviso — doctypes a medida.** Dos tipos de requisitos vienen con sus
> propios doctypes completos porque la vía genérica "Linked Document" se queda
> corta para ellos: **Recommendation Letter** (con el portal externo para
> recomendadores) y **Culminating Project** (con rondas de revisión). Para estos,
> use los doctypes dedicados; el sistema ya los integra en la
> Program Audit.

## Cómo se conecta esto con Program Audit

La **página Program Audit** (`/program-audit/<enrollment>`) presenta una vista única
y consolidada:

- La sección **Académico**, alimentada desde la tabla Program → Courses, muestra
  el progreso de créditos y el estado de los cursos obligatorios. _(sin cambios)_
- La sección **Requisitos de Graduación**, alimentada desde la instantánea SGR, muestra
  cada requisito activo, agrupado por estado, con instrucciones por fila
  y cualquier evidencia ya archivada.

A un estudiante se le muestra `Eligible to graduate` solo cuando ambas secciones están
libres de elementos obligatorios sin cumplir.

## Referencia rápida

| Si desea...      | Haga esto                                                                                               |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Agregar una nueva categoría de requisitos para todo el seminario | Crear un Graduation Requirement Item (biblioteca)                                    |
| Aplicar un requisito a un programa específico                    | Añadir una fila al Program Graduation Requirement (política) de ese programa         |
| Hacer que un requisito venza solo después de otro                | Activation Mode = After Requirement, elija los prerrequisitos                                           |
| Hacer que un requisito venza X días antes de la graduación       | Activation Mode = Time Offset, anchor = Expected Graduation Date                                        |
| Confirmar que un estudiante cumplió algo                         | Abrir la fila SGR, establecer status = Fulfilled                                                        |
| Eximir a un estudiante de un requisito                           | Abrir la fila SGR, marcar Waived, dar un motivo                                                         |
| Actualizar el catálogo del seminario                             | Publicar un nuevo Program Graduation Requirement con una nueva fecha Active from — no edite el anterior |
| Mover a un estudiante al nuevo catálogo                          | Acción Resnapshot en su Program Enrollment                                                              |

## Relacionados

- [Matrícula](enrollment.md) — Program Enrollment es donde vive la instantánea.
- [Calendario académico](academic-calendar.md) — Eventos usados por los requisitos de Event
  Attendance.
- [Roles de usuario](../administration/user-roles.md) — qué roles pueden crear
  políticas, marcar requisitos como Fulfilled y eximirlos.
