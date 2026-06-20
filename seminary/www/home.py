import frappe

from seminary.seminary.seo import page_metatags


def get_context(context):
    """Public Home page (ADR 061). Hero content comes from the Website Branding
    singleton so staff can edit it in Desk without a deploy."""
    context.no_cache = 1
    context.title = frappe._("Home")
    branding = None
    if frappe.db.exists("DocType", "Website Branding"):
        branding = frappe.get_cached_doc("Website Branding")
        context.branding = branding
    context.app_name = frappe.db.get_single_value(
        "Website Settings", "app_name"
    ) or frappe._("Welcome")

    headline = (branding and branding.hero_headline) or context.app_name
    subtext = (branding and branding.hero_subtext) or frappe._(
        "Theological education for the church."
    )
    context.metatags = page_metatags(
        headline, subtext, image=branding and branding.hero_image
    )
