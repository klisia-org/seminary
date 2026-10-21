"""Point the Registrar's "Regenerate Current-Term Invoices" button at seminary's
billing action instead of oikonomos (aretenic decision 051 §3).

The block is created once and never overwritten, so a site keeps its stored
script; only the method path is swapped, and any local edit around it stays.
"""

import frappe

BLOCK = "Registrar - Regenerate Current-Term Invoices"
OLD = "oikonomos.financial.invoicing.regenerate_current_term_invoices"
NEW = "seminary.seminary.financial.actions.regenerate_current_term_charges"


def execute():
    script = frappe.db.get_value("Custom HTML Block", BLOCK, "script")
    if script and OLD in script:
        frappe.db.set_value(
            "Custom HTML Block",
            BLOCK,
            "script",
            script.replace(OLD, NEW),
            update_modified=False,
        )
