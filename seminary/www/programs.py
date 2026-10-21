import frappe

from seminary.seminary.seo import page_metatags
from seminary.seminary.website_data import programs_catalogue


def get_context(context):
    """Public Programs catalogue (ADR 061): published programs grouped by
    their level's tier (p016), ordered by the levels' web_order. The page heading uses a
    singular/plural label based on how many programs are published, or the
    Website Branding override when set. The data comes from website_data (p021)."""
    context.no_cache = 1

    catalogue = programs_catalogue()
    context.groups = catalogue.groups
    context.program_count = catalogue.program_count
    context.programs_label = catalogue.programs_label
    context.title = context.programs_label
    context.metatags = page_metatags(
        context.programs_label,
        frappe._("Explore the degree and certificate programs we offer."),
        image=catalogue.programs[0].image_blurb if catalogue.programs else None,
    )
