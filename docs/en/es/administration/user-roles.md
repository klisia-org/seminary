# Roles de usuario

SeminaryERP utiliza el sistema de permisos basado en roles de Frappe para controlar el acceso. The
module defines and owns the following roles. Un usuario puede tener más
de un rol. ERPNext roles (for accounting, etc.) should be selected per your policy.
See [ERPNext Module Access documentation.](https://docs.frappe.io/erpnext/adding-users#27-allow-module-access)

## Funciones del personal (Pabilia)

- **Administrador seminario** — administrador de módulos. Acceso total a los tipos de configuración académicos y
  , incluyendo las acciones de flujo de trabajo.
- **Registrar** — student-records lifecycle: admissions, enrollment, academic
  terms, withdrawals, graduation and transcripts, and disciplinary records.
- \*\* Programa \*\* — programas y autoridad curricular: programas, cursos,
  evaluaciones, calificación y política académica. (Este rol se llamó anteriormente
  _Usuario Académicos_.)
- **Instructor**: enseña y califica sus propios cursos y puede reportar incidentes disciplinarios
  .

## Roles del portal (frontend)

- **Student** — enrols in courses, submits work, and views their own records and
  published curriculum.
- **Alumni**: estudiantes graduados; acceso al portal de ex alumnos y sus propios registros
  .
- **Solicitud de estudiantes** — estudiantes potenciales que completan la aplicación
  formulario web.

## Acceso: Portal vs Desk

Estudiantes, antiguos alumnos y solicitantes utilizan el portal LMS (frontend) y no tienen acceso a un escritorio
; son redireccionados al portal de inicio de sesión. El personal trabaja en el escritorio de Frappe
para configuración, registros y reportes.

## Notas

- `System Manager` (Frappe core) conserva acceso super-admin en todas partes.
