# Roles de usuario

SeminaryERP utiliza el sistema de permisos basado en roles de Frappe para controlar el acceso.

## Roles principales

- **Seminary Admin** — acceso completo a todos los doctypes del seminario y a la configuración
- **Instructor** — gestiona cursos, califica entregas, modera discusiones
- **Student** — se inscribe en cursos, entrega trabajos, participa en discusiones
- **Evaluator** — califica entregas sin los privilegios completos de instructor

## Acceso: Portal vs Desk

Los estudiantes y los instructores utilizan principalmente el portal del LMS (frontend). Los administradores trabajan en Frappe Desk para la configuración y la generación de informes.
