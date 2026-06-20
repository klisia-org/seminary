import frappe

from seminary.seminary.seo import page_metatags


def get_context(context):
    """Public Programs catalogue (ADR 061): published programs grouped by
    Program Level (levels ordered by their web_order). The page heading uses a
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

    levels = frappe.get_all(
        "Program Level",
        fields=["name", "pgm_level"],
        order_by="web_order asc, pgm_level asc",
    )

    by_level = {}
    for p in programs:
        by_level.setdefault(p.program_level or "", []).append(p)

    groups = []
    for lvl in levels:
        if lvl.name in by_level:
            groups.append({"level": lvl.pgm_level, "programs": by_level.pop(lvl.name)})
    # Programs whose level has no row / no level — append last under their key.
    for lvl_name, progs in by_level.items():
        groups.append({"level": lvl_name or frappe._("Programs"), "programs": progs})

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
