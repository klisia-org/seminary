# Personalización},{

Cómo adaptar SeminaryERP a las necesidades de su institución.

## Getting Started with SeminaryERP

This workspace will guide your configurations. They are numbered as often one configuration impacts others, and divided with sub-headings for easier configuration: The main configurations, Financial Setup (excluding ERPNext Customizations), Infrastructure, Academic Setup, and Optional configurations (Payment Gateways, Bible).

## Ajustes seminarios

Configuración centralizada para su institución. Acceda mediante **Frappe Desk > Seminary Settings**.

## Configuración a nivel de período académico

Muchas políticas (plazos de inscripción, reglas de retiro, períodos de calificación) se configuran por período académico en lugar de globalmente, lo que permite que su institución adapte sus políticas con el tiempo.

## Ayuda integrada en la aplicación

SeminaryERP includes a contextual help system with two parts:

- **Documentation link.** A form shows a Help icon in its header when its doctype
  has a "Documentation Link" set by the developers. Clicking it opens that page of this documentation in a new tab. No setup
  is needed. Available on Desk by default.
- **Local notes.** Create a **Seminary Help Entry** for a doctype and fill in
  _Local Notes_ — your institution-specific "how we do it here" instructions.
  They appear in a collapsible panel at the top of that doctype's form.

These two parts of the contextual help are available both for Desk and for the Portal. Since the portal does not use the Doctype binding, the default behavior is no contextual help (we strived for a clean, easy to navigate, portal). However, it can be included via the **Seminary Help Entry** per portal page. In this case, a blue help icon will float at the bottom right corner of the page (the weblink added will be at the bottom of the Local notes).
