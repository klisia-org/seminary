import frappe
from frappe import _
from seminary.seminary.api import get_program_audit


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "fieldname": "student_name",
            "label": _("Student"),
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "fieldname": "program",
            "label": _("Program"),
            "fieldtype": "Link",
            "options": "Program",
            "width": 150,
        },
        {
            "fieldname": "emphasis",
            "label": _("Emphasis"),
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "fieldname": "credits_earned",
            "label": _("Credits Earned"),
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "fieldname": "credits_required",
            "label": _("Credits Required"),
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "fieldname": "percent_complete",
            "label": _("% Complete"),
            "fieldtype": "Percent",
            "width": 100,
        },
        {
            "fieldname": "mandatory_remaining",
            "label": _("Mandatory Remaining"),
            "fieldtype": "Int",
            "width": 140,
        },
        {
            "fieldname": "graduation_eligible",
            "label": _("Graduation Eligible"),
            "fieldtype": "Data",
            "width": 130,
        },
    ]


def get_data(filters):
    pe_filters = {"docstatus": 1}

    if filters.get("active_only"):
        pe_filters["pgmenrol_active"] = 1

    if filters.get("program"):
        pe_filters["program"] = filters["program"]

    enrollments = frappe.get_all(
        "Program Enrollment",
        filters=pe_filters,
        fields=["name", "student_name", "program", "totalcredits"],
        order_by="student_name asc",
    )

    data = []
    for pe in enrollments:
        try:
            audit = get_program_audit(pe.name)
        except Exception as e:
            frappe.log_error(f"Program audit failed for {pe.name}: {e}")
            continue

        credits_required = audit.get("effective_credits_required", 0)
        credits_earned = audit.get("credits_earned", 0)
        percent_complete = (
            round((credits_earned / credits_required) * 100, 1)
            if credits_required
            else 0
        )

        emphases = audit.get("emphases", [])
        emphasis_names = ", ".join(e["track_name"] for e in emphases) or "—"

        mandatory_remaining = sum(
            1
            for mc in audit.get("mandatory_courses", [])
            if mc["status"] != "Completed"
        )

        data.append(
            {
                "student_name": pe.student_name,
                "program": pe.program,
                "emphasis": emphasis_names,
                "credits_earned": credits_earned,
                "credits_required": credits_required,
                "percent_complete": percent_complete,
                "mandatory_remaining": mandatory_remaining,
                "graduation_eligible": (
                    _("Yes") if audit.get("graduation_eligible") else _("No")
                ),
            }
        )

    return data
