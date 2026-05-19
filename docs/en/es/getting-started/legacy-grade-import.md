# Importación de calificaciones heredadas

SeminaryERP utiliza un único flujo para gestionar tanto la transferencia de créditos desde una institución asociada como la carga histórica masiva de calificaciones desde un sistema heredado. El modelo trata "nuestro propio historial previo a SeminaryERP" como un Partner Seminary autorreferencial, por lo que el mismo flujo que ingiere el expediente de un estudiante transferido también incorpora décadas de datos históricos.

La importación es un flujo por etapas e idempotente:

**Partner Seminary → Equivalencias de cursos → Partner Transcript Import Batch (Draft → Dry-Run → Submit)**

El Dry-Run resuelve cada fila según las equivalencias y la política de conversión sin modificar el registro del estudiante. Enviar confirma cada fila en la Program Enrollment del estudiante y actualiza los totales de auditoría de grado. Volver a enviar el mismo (estudiante, código de curso de origen, término de origen) actualiza la fila existente del expediente en su lugar — sin duplicados.

## 1. Configuración única (legado interno)

Para importar los datos históricos de tu propia institución, crea un **Partner Seminary** autorreferencial y una **política de conversión de calificaciones**. Regístralo una sola vez; reutilízalo para siempre.

1. **Cree la política de conversión de calificaciones \"Identity (Internal)\"**
   - Source Grading Scale = tu escala interna
   - Target Grading Scale = tu escala interna (igual)
   - Método de conversión = `identity`
   - Enviar. Las políticas enviadas pueden ser referenciadas por registros de Partner Seminary; los borradores no.
2. **Crea el registro de Partner Seminary**
   - Nombre: p. ej., `ESWA Legacy (pre-2026)`
   - `Is Internal Legacy`: marcado (este indicador es de solo lectura tras la creación, evita la eliminación y oculta el registro de las vistas de lista predeterminadas)
   - `Counts in GPA`: marcado (las calificaciones heredadas SON las propias de tu institución — deben participar en el cálculo del GPA)
   - `Relación de unidades de crédito`: `1,0`
   - Default Grading Scale = tu escala interna
   - Política de conversión predeterminada = `Identity (Internal)`
3. **Crear en lote las equivalencias de cursos**
   - Abre la vista de lista de Partner Seminary Course Equivalence.
   - Haz clic en **Create Legacy Integration** (solo System Manager).
   - Elige el Partner Seminary heredado que acabas de crear.
   - Se crea una equivalencia `legacy_identity` enviada por cada curso de tu catálogo, autovinculando el curso consigo mismo. Los cursos ya mapeados se omiten — la acción es idempotente.

Después de esto, el Partner Seminary heredado está listo para recibir importaciones de expedientes. Ve al paso 3 para el flujo de importación propiamente dicho.

## 2. Configuración única (socio externo)

Para un socio verdaderamente externo (un seminario par que transfiere créditos):

1. Crea (o reutiliza) la **Grading Scale** del socio si es diferente de la tuya. Enviar.
2. Crea la **Grade Conversion Policy** desde la escala del socio a tu escala interna:
   - Elige un `conversion_method`: `identity`, `linear_multiplier`, `linear_with_offset`, `interval_map`, o `manual_per_course`.
   - Para `linear_*`, establece el `multiplier` (y el `offset` si corresponde). P. ej. Francófona 0–20 → Porcentaje interno = ×5.
   - Para `interval_map`, completa la tabla de asignación símbolo por símbolo. Los desplegables Source Symbol y Target Symbol se autocompletan a partir de las respectivas escalas — cada símbolo de origen debe mapearse (se permiten símbolos de destino sin origen).
   - Enviar.
3. Crea el registro **Partner Seminary** para la institución:
   - `Is Internal Legacy`: desmarcado
   - `Counts in GPA`: normalmente desmarcado (por defecto en el sector — los créditos transferidos cuentan para el grado pero no para el GPA)
   - `Relación de unidades de crédito`: horas-crédito internas por 1 unidad de crédito del socio (p. ej., `0,5` para ECTS → horas semestrales de EE. UU. con la mitad de peso)
   - `Minimum Transferable Grade`: código de calificación en tu escala interna por debajo del cual las transferencias se bloquean en el momento de confirmar (p. ej., `C`)
   - Default Grading Scale / Default Conversion Policy = lo que acabas de crear
4. Crea **Partner Seminary Course Equivalences** una por una desde el curso del socio a tu curso interno:
   - Rellena `source_course_code`, `source_course_name`, `source_credit_value` y el `internal_course` de destino.
   - Anulaciones opcionales por curso: `credit_override` (para forzar un recuento específico de créditos), `conversion_policy_override` (para un curso en una escala diferente a la predeterminada del socio — p. ej., un departamento de música con aprobado/suspenso).
   - Adjunta un `Supporting Document` (aprobación de dirección, acta de comité, carta del acreditador) para la pista de auditoría.
   - Enviar. Solo las equivalencias enviadas se pueden usar durante la importación.

Las equivalencias de curso son enviables: para cambiar una, cancélala y modifícala — la versión antigua se conserva mediante `amended_from`, y las filas de expediente existentes siguen haciendo referencia al original.

## 3. Importación de expedientes

Partner Transcript Import Batch sirve tanto para el caso manual de un solo estudiante como para el caso masivo por CSV. Cada lote incluye:

- `Partner Seminary`: de qué socio provienen los datos de este lote
- `Target Program`: el programa interno al que se aplican los créditos
- `Target Academic Term`: el periodo académico interno al que se anclan estas filas (normalmente el periodo actual del estudiante para transferencias externas, o un periodo legado designado para la carga histórica)

### Entrada manual (un estudiante)

1. Crea un nuevo **Partner Transcript Import Batch**.
2. Elige Partner Seminary, Target Program y Target Academic Term. Guardar. _(Los autocompletados se activan solo después del primer guardado.)_
3. En la tabla Rows, añade una fila por curso:
   - `Student` (Link) O `Student Email` — cualquiera identifica al estudiante. Si solo se proporciona el correo electrónico, el Dry-Run lo resuelve al registro del estudiante a través de `Student.user`.
   - `Source Course Code` — desplegable alimentado desde las equivalencias enviadas para este socio. Al seleccionar un código se autocompletan `Source Course Name` y `Source Credit Value` desde la equivalencia.
   - `Source Term` — texto libre (los términos del socio no se registran aquí como registros de Academic Term).
   - `Source Grade` — desplegable alimentado con los códigos de calificación de la escala de calificaciones predeterminada del socio.
   - `External Reference` — ID opcional del sistema de origen; tiene prioridad sobre la clave natural de idempotencia.
4. **Guardar**, luego haz clic en **Run Dry-Run**.
5. Si el Dry-Run está limpio, el estado avanza a `Dry-Run Clean`. Haz clic en **Enviar**.

### Entrada masiva por CSV

1. Usa la herramienta integrada de Frappe **Data Import** (usa la barra de búsqueda) --> Add Data Import

2. Tipo de documento: Partner Transcript Import Batch Import
   Tipo de importación: Insert New records
   La única casilla marcada debe ser Don't send emails.
   **Guardar**

3. Puedes descargar una plantilla CSV desde la herramienta para cargar tus datos. Ten en cuenta que no necesitas repetir los campos iniciales (seminario asociado, programa objetivo y periodo académico objetivo)

    ```csv
    Seminario asociado,Programa de destino,Periodo académico de destino,Código de curso de origen (Filas),Calificación de origen (Filas),Periodo de origen (Filas),Correo electrónico del estudiante (Filas)
    T-LINK,Master of Divinity,2025-2026 (SP26),SFD-101,A,1S 24,modest@gmail.com
    ,,,THM-201,A,1S24,modest@gmail.com
    ```

4. Tras una importación correcta, abre el lote — todas las filas deberían estar en la cuadrícula con `Student` en blanco y `Student Email` rellenado.

5. Haz clic en **Run Dry-Run**. Cada fila se resuelve:
   - Correo electrónico → Enlace del estudiante
   - Curso de origen → curso interno mediante la equivalencia
   - Crédito de origen → crédito interno (a través de `credit_override`, `source_credit_value` de la equivalencia, o el valor propio de la fila × `credit_unit_ratio`)
   - Calificación de origen → calificación de destino mediante la política de conversión

6. Corrige cualquier advertencia (ver referencia más abajo) y luego envía.

## 4) Referencia de advertencias del Dry-Run

| Advertencia                    | Significado                                                                                                                                        | Solución                                                                                                                                |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `unknown_student_email`        | Ningún registro de Student tiene un campo `user` que coincida con el correo electrónico.                                           | Corrige el correo en la fila o actualiza el enlace de usuario del Student.                                              |
| `no_submitted_equivalence`     | No hay una Course Equivalence enviada para este socio + código de origen.                                                          | Crea y envía la equivalencia, o corrige el código de origen.                                                            |
| `zero_credits`                 | El crédito de origen de la fila está en blanco y la equivalencia no tiene `source_credit_value` / `credit_override`.               | Rellena el `source_credit_value` de la fila, o edita la equivalencia para incluir un valor predeterminado.              |
| `below_minimum_transferable`   | La calificación convertida está por debajo de la `Minimum Transferable Grade` del socio.                                           | Criterio de la secretaría académica — omite la fila o añade una `Override Note` para aceptarla.                         |
| `clamped_high` / `clamped_low` | La conversión lineal produjo un valor fuera de la escala de destino; el resultado se recortó a los límites.                        | Generalmente aceptable; informativa. Revisa el multiplicador de la política si el recorte es frecuente. |
| `no_mapping`                   | Una conversión `interval_map` no tenía fila para este símbolo de origen, o la calificación no se encontró en la escala de destino. | Modifica el mapa de la política para cubrir el símbolo faltante.                                                        |
| `unparseable_source`           | La conversión lineal no pudo interpretar la calificación de origen como un número.                                                 | Corrige la calificación de origen o cambia la política a `interval_map` / `manual_per_course`.                          |

Una fila con una advertencia bloquea el estado Dry-Run Clean a menos que la secretaría académica complete `Override Note` en esa fila. La confirmación está además protegida: cada fila debe tener un `Student` resuelto antes de que Enviar tenga éxito.

## 5. Enviar

Al enviar:

- Cada fila se convierte en una entrada transferida de `Program Enrollment Course` en la Program Enrollment del estudiante para (Target Program, Target Academic Term). Se marca `Is Transfer`; `Partner Seminary`, `Mapping Type`, `Course Equivalence`, `Conversion Policy Applied`, `Source Course Code`, `Source Term`, `Source Grade`, `External Reference` quedan registrados para auditoría.
- El `Total Credits` de la Program Enrollment se recalcula a partir de la SUMA de las filas aprobadas.
- Se recalculan los créditos del itinerario de énfasis; se aplican los énfasis automáticos.
- La vista de expediente para el estudiante muestra los cursos transferidos junto a los internos.

## 6. Reejecución y modificaciones

El lote es idempotente. Volver a enviar un lote con las mismas filas actualiza las entradas de expediente existentes en su lugar (emparejadas por `partner_seminary + source_course_code + source_term`, o por `external_reference` cuando está presente). Para corregir datos:

- **Corrección en el mismo término** — Crea un nuevo lote con las filas corregidas; las filas PEC existentes se actualizan. Los totales se actualizan.
- **Término incorrecto seleccionado** — Cancela el lote original (supervisado; bloqueado si aún existen filas de expediente), y crea un nuevo lote con el `Target Academic Term` correcto.
- **Corrección de la política** — Modifica la Grade Conversion Policy (la enmienda incorporada de Frappe crea la línea `amended_from`). Los expedientes existentes siguen haciendo referencia al ID de la política original; las nuevas importaciones usan la versión modificada. Esto preserva la reproducibilidad histórica.

## Relacionado

- [Initial Setup](initial-setup.md) — la secuencia completa de la primera instalación
- [Importación de datos de Frappe](https://docs.frappe.io/framework/user/en/data-import)
