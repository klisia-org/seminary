import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "fieldname": "course_term",
            "label": _("Term"),
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "fieldname": "course",
            "label": _("Course"),
            "fieldtype": "Link",
            "options": "Course",
            "width": 200,
        },
        {
            "fieldname": "course_name",
            "label": _("Course Name"),
            "fieldtype": "Data",
            "width": 240,
        },
        {
            "fieldname": "pgmcourse_credits",
            "label": _("Credits"),
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "fieldname": "required",
            "label": _("Mandatory"),
            "fieldtype": "Check",
            "width": 90,
        },
    ]


def get_data(filters):
    program = filters.get("program")
    if not program:
        return []

    # Ordered so per-term groups are contiguous; NULL/0 terms sort last and are
    # surfaced as "Unassigned" — those rows never auto-enroll (no course_term).
    rows = frappe.db.sql(
        """SELECT pc.course_term, pc.course, pc.course_name,
                  pc.pgmcourse_credits, pc.required
           FROM `tabProgram Course` pc
           WHERE pc.parent = %(program)s AND pc.disabled = 0
           ORDER BY IF(IFNULL(pc.course_term, 0) = 0, 999999, pc.course_term), pc.course""",
        {"program": program},
        as_dict=True,
    )

    data = []
    grand_count = 0
    grand_credits = 0
    started = False
    group_term = None
    group_count = 0
    group_credits = 0

    def subtotal_row(term, credits):
        label = (
            _("Term {0} subtotal").format(term) if term else _("Unassigned subtotal")
        )
        return {"course_name": label, "pgmcourse_credits": credits}

    for r in rows:
        term = r.course_term or 0
        if started and term != group_term:
            data.append(subtotal_row(group_term, group_credits))
            group_count = 0
            group_credits = 0
        group_term = term
        started = True

        credits = r.pgmcourse_credits or 0
        data.append(
            {
                "course_term": r.course_term,
                "course": r.course,
                "course_name": r.course_name,
                "pgmcourse_credits": r.pgmcourse_credits,
                "required": r.required,
            }
        )
        group_count += 1
        group_credits += credits
        grand_count += 1
        grand_credits += credits

    if started:
        data.append(subtotal_row(group_term, group_credits))
        data.append(
            {
                "course_name": _("Total: {0} course(s)").format(grand_count),
                "pgmcourse_credits": grand_credits,
            }
        )

    return data
