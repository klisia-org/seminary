# Customization

How to adapt SeminaryERP to your institution's needs.

## Getting Started with SeminaryERP
This workspace will guide your configurations. They are numbered as often one configuration impacts others, and divided with sub-headings for easier configuration: The main configurations, Financial Setup (excluding ERPNext Customizations), Infrastructure, Academic Setup, and Optional configurations (Payment Gateways, Bible).

## Seminary Settings

Central configuration for your institution. Access via **Frappe Desk > Seminary Settings**.

## Term-level configuration

Many policies (enrollment windows, withdrawal rules, grading periods) are configured per academic term rather than globally, allowing your institution to evolve its policies over time.

## In-app help

SeminaryERP includes a contextual help system with two parts:

- **Documentation link.** A form shows a Help icon in its header when its doctype
  has a "Documentation Link" set by the developers. Clicking it opens that page of this documentation in a new tab. No setup
is needed. Available on Desk by default.
- **Local notes.** Create a **Seminary Help Entry** for a doctype and fill in
  *Local Notes* — your institution-specific "how we do it here" instructions.
  They appear in a collapsible panel at the top of that doctype's form.

These two parts of the contextual help are available both for Desk and for the Portal. Since the portal does not use the Doctype binding, the default behavior is no contextual help (we strived for a clean, easy to navigate, portal). However, it can be included via the **Seminary Help Entry** per portal page. In this case, a blue help icon will float at the bottom right corner of the page (the weblink added will be at the bottom of the Local notes). 
