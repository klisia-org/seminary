"""Data behind the public program pages (p021).

The programs catalogue, a program's open admission windows and its continuous
term used to be computed inside the page controllers. They live here so the
pages and anything else that shows the same data (aretenic's website widgets)
compute it once, the same way.
"""

import frappe
from frappe import _
from frappe.utils import format_date, getdate, today

#: Program fields a catalogue card needs.
CATALOGUE_FIELDS = [
    "name",
    "program_name",
    "blurb",
    "image_blurb",
    "program_level",
    "program_duration",
    "duration_unit",
    "route",
    "order_pd",
]


def programs_catalogue():
    """Published programs grouped by their level's tier (p016), ordered by the
    levels' web_order, plus the page label."""
    programs = frappe.get_all(
        "Program",
        filters={"published": 1},
        fields=CATALOGUE_FIELDS,
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
            groups.append({"level": _(tier), "programs": by_tier.pop(tier)})
    # Programs with no level — append last.
    for progs in by_tier.values():
        groups.append({"level": _("Programs"), "programs": progs})

    return frappe._dict(
        groups=groups,
        programs=programs,
        program_count=len(programs),
        programs_label=programs_label(len(programs)),
    )


def programs_label(count):
    override = frappe.db.get_single_value("Website Branding", "programs_label_override")
    if override:
        return override
    return _("Our Program") if count == 1 else _("Our Programs")


def program_enrollment(program):
    """The live part of a program page: its open windows (Timed) or the term it
    enrolls into (Continuous), and the apply form's route."""
    from seminary.seminary.api import get_application_web_form_route

    out = frappe._dict(
        open_windows=[],
        continuous_term=None,
        apply_route=get_application_web_form_route(program.name),
    )
    if program.enrollment_mode == "Timed":
        out.open_windows = open_admission_windows(program.name)
    elif program.enrollment_mode == "Continuous" and program.display_cta:
        out.continuous_term = continuous_term()
        if not out.continuous_term:
            frappe.log_error(
                f"Program {program.name} is Continuous with display_cta=1 "
                "but no current/upcoming Academic Term is configured.",
                "program.get_context",
            )
    return out


def open_admission_windows(program=None):
    """Published, submitted Term Admissions that have not closed, earliest first.

    With `program`, only the windows that admit it. Without, every window, each
    carrying `programs`: the published programs it admits that show their
    windows on the website.
    """
    windows = frappe.db.sql(
        """
        SELECT DISTINCT ta.name, ta.academic_term, ta.admission_start_date,
               ta.admission_end_date, ta.introduction,
               at.term_name, at.term_for_web,
               at.term_start_date, at.term_end_date
        FROM `tabTerm Admission` ta
        INNER JOIN `tabTerm Admission Program` tap
                ON tap.parent = ta.name
               AND tap.parenttype = 'Term Admission'
        INNER JOIN `tabAcademic Term` at
                ON at.name = ta.academic_term
        WHERE ta.docstatus = 1
          AND ta.published = 1
          AND ta.admission_end_date >= %(today)s
          AND (%(program)s IS NULL OR tap.program = %(program)s)
        ORDER BY ta.admission_start_date ASC
        """,
        {"today": today(), "program": program},
        as_dict=True,
    )
    today_d = getdate()
    for w in windows:
        w["term_label"] = w.term_for_web or w.term_name or w.academic_term
        w["apply_window_display"] = "{} – {}".format(
            format_date(w.admission_start_date), format_date(w.admission_end_date)
        )
        w["term_window_display"] = (
            "{} – {}".format(
                format_date(w.term_start_date), format_date(w.term_end_date)
            )
            if w.term_start_date and w.term_end_date
            else None
        )
        start = getdate(w.admission_start_date)
        end = getdate(w.admission_end_date)
        if start > today_d:
            w["status_label"] = _("Opens soon")
            w["status"] = "opens_soon"
            w["indicator"] = "blue"
        elif end == today_d:
            w["status_label"] = _("Last day to apply")
            w["status"] = "last_day"
            w["indicator"] = "red"
        else:
            w["status_label"] = _("Now accepting applications")
            w["status"] = "open"
            w["indicator"] = "green"

    if program is None:
        _attach_programs(windows)
        windows = [w for w in windows if w.programs]
    return windows


def _attach_programs(windows):
    if not windows:
        return
    from seminary.seminary.api import get_application_web_form_route

    rows = frappe.db.sql(
        """
        SELECT tap.parent AS window, p.name, p.program_name, p.route, p.display_cta
        FROM `tabTerm Admission Program` tap
        INNER JOIN `tabProgram` p ON p.name = tap.program
        WHERE tap.parenttype = 'Term Admission'
          AND tap.parent IN %(windows)s
          AND p.published = 1
          AND p.display_enrollment_window = 1
        ORDER BY p.order_pd ASC, p.program_name ASC
        """,
        {"windows": [w.name for w in windows]},
        as_dict=True,
    )
    by_window = {}
    for r in rows:
        r["apply_route"] = get_application_web_form_route(r.name)
        by_window.setdefault(r.pop("window"), []).append(r)
    for w in windows:
        w["programs"] = by_window.get(w.name, [])


def continuous_term():
    """The current Academic Term, else the next one to start."""
    fields = [
        "name",
        "term_name",
        "term_for_web",
        "term_start_date",
        "term_end_date",
    ]
    current = frappe.db.get_value(
        "Academic Term",
        {"iscurrent_acterm": 1},
        fields,
        as_dict=True,
    )
    if not current:
        upcoming = frappe.get_all(
            "Academic Term",
            filters={"term_start_date": [">", today()]},
            fields=fields,
            order_by="term_start_date asc",
            limit=1,
        )
        current = upcoming[0] if upcoming else None
    if not current:
        return None
    current["term_label"] = (
        current.get("term_for_web") or current.get("term_name") or current["name"]
    )
    if current.get("term_start_date") and current.get("term_end_date"):
        current["term_window_display"] = "{} – {}".format(
            format_date(current["term_start_date"]),
            format_date(current["term_end_date"]),
        )
    else:
        current["term_window_display"] = None
    return current
