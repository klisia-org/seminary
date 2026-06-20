import frappe

from seminary.seminary import faculty
from seminary.seminary.seo import page_metatags


def get_context(context):
    """Public "Our Team" page (ADR 061): published Academic Units ordered by
    web_order. web_order==0 units render their roster inline (shown first);
    web_order>0 units show a card linking to the unit's own /team/<slug> page."""
    context.no_cache = 1
    context.title = frappe._("Our Team")
    context.show_salutations = bool(
        frappe.db.get_single_value("Website Branding", "show_team_salutations")
    )

    units = frappe.get_all(
        "Academic Unit",
        filters={"publish_on_web": 1, "is_active": 1},
        fields=["name", "unit_name", "description", "web_order", "route"],
        order_by="web_order asc, unit_name asc",
    )

    inline, cards = [], []
    for u in units:
        if (u.web_order or 0) == 0:
            u["roster"] = faculty.get_unit_roster(u.name, public=True)
            inline.append(u)
        else:
            cards.append(u)

    context.inline_units = inline
    context.card_units = cards
    context.metatags = page_metatags(
        frappe._("Our Team"),
        frappe._("Meet the faculty, leadership, and staff who serve our community."),
    )
