import frappe

from seminary.seminary.seo import page_metatags


def get_context(context):
    """Public Programs catalogue (ADR 061): published programs grouped by
    their level's tier (p016), ordered by the levels' web_order. The page heading uses a
    singular/plural label based on how many programs are published, or the
    Website Branding override when set."""
    context.no_cache = 1

    programs = frappe.get_all(
        "Program",
        filters={"published": 1},
        fields=[
            "name",
            "program_name",
            "blurb",
            "image_blurb",
            "program_level",
            "program_duration",
            "duration_unit",
            "route",
            "order_pd",
        ],
        order_by="order_pd asc, program_name asc",
    )

    # One section per tier (p016), ordered by the lowest web order among its levels.
    levels = frappe.get_all(
        "Program Level",
        fields=["name", "degree_tier", "web_order"],
        order_by="web_order asc, pgm_level asc",
    )
    tier_of = {lvl.name: lvl.degree_tier for lvl in levels}
    tier_order = []
    for lvl in levels:
        if lvl.degree_tier and lvl.degree_tier not in tier_order:
            tier_order.append(lvl.degree_tier)

    by_tier = {}
    for p in programs:
        by_tier.setdefault(tier_of.get(p.program_level) or "", []).append(p)

    groups = []
    for tier in tier_order:
        if tier in by_tier:
            groups.append({"level": frappe._(tier), "programs": by_tier.pop(tier)})
    # Programs with no level — append last.
    for progs in by_tier.values():
        groups.append({"level": frappe._("Programs"), "programs": progs})

    context.groups = groups
    context.program_count = len(programs)
    context.programs_label = _programs_label(len(programs))
    context.title = context.programs_label
    context.metatags = page_metatags(
        context.programs_label,
        frappe._("Explore the degree and certificate programs we offer."),
        image=programs[0].image_blurb if programs else None,
    )


def _programs_label(count):
    override = frappe.db.get_single_value("Website Branding", "programs_label_override")
    if override:
        return override
    return frappe._("Our Program") if count == 1 else frappe._("Our Programs")
