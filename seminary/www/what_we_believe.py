import frappe

from seminary.seminary.seo import page_metatags


def get_context(context):
    """Public "What We Believe" page (ADR 061): renders the Doctrinal Statement
    flagged for the website. If several are flagged, prefer the active one, then
    the most recently updated."""
    context.no_cache = 1
    context.title = frappe._("What We Believe")

    statements = frappe.get_all(
        "Doctrinal Statement",
        filters={"ds_web": 1, "docstatus": ("<", 2)},
        fields=["name", "ds_title", "doctrinal_statement", "active"],
        order_by="active desc, docstatus desc, modified desc",
        limit=1,
    )
    context.statement = statements[0] if statements else None

    description = (
        context.statement.doctrinal_statement if context.statement else None
    ) or frappe._("What our community believes and confesses.")
    context.metatags = page_metatags(frappe._("What We Believe"), description)
