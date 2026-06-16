"""Internship Placement Roster — every internship placement with its student,
organization, supervisor, status, and hours progress. The registrar's at-a-glance
view of who is interning where, how far along they are, and what still needs a
site or supervisor (ADR 054)."""

import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {
            "fieldname": "student",
            "label": _("Student"),
            "fieldtype": "Link",
            "options": "Student",
            "width": 110,
        },
        {
            "fieldname": "student_name",
            "label": _("Name"),
            "fieldtype": "Data",
            "width": 170,
        },
        {
            "fieldname": "internship_type",
            "label": _("Type"),
            "fieldtype": "Link",
            "options": "Internship Type",
            "width": 150,
        },
        {
            "fieldname": "organization_name",
            "label": _("Organization"),
            "fieldtype": "Data",
            "width": 170,
        },
        {
            "fieldname": "supervisor_name",
            "label": _("Supervisor"),
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "fieldname": "placement_status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "hours_logged",
            "label": _("Hours"),
            "fieldtype": "Float",
            "width": 80,
        },
        {
            "fieldname": "hours_allocated",
            "label": _("Allocated"),
            "fieldtype": "Int",
            "width": 90,
        },
        {"fieldname": "pct", "label": _("% Done"), "fieldtype": "Percent", "width": 90},
        {
            "fieldname": "actual_start",
            "label": _("Start"),
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "fieldname": "actual_end",
            "label": _("End"),
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "fieldname": "placement",
            "label": _("Placement"),
            "fieldtype": "Link",
            "options": "Internship Placement",
            "width": 120,
        },
    ]


def get_data(filters):
    conditions = []
    values = {}
    if filters.get("placement_status"):
        conditions.append("pl.placement_status = %(placement_status)s")
        values["placement_status"] = filters["placement_status"]
    if filters.get("internship_type"):
        conditions.append("app.internship_type = %(internship_type)s")
        values["internship_type"] = filters["internship_type"]
    if filters.get("partner_org"):
        conditions.append("pl.partner_org = %(partner_org)s")
        values["partner_org"] = filters["partner_org"]
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            app.student            AS student,
            stu.student_name       AS student_name,
            app.internship_type    AS internship_type,
            org.organization_name  AS organization_name,
            sup.full_name          AS supervisor_name,
            pl.placement_status    AS placement_status,
            pl.hours_logged        AS hours_logged,
            pl.hours_allocated     AS hours_allocated,
            pl.actual_start        AS actual_start,
            pl.actual_end          AS actual_end,
            pl.name                AS placement
        FROM `tabInternship Placement` pl
        JOIN `tabInternship Application` app ON app.name = pl.internship_application
        LEFT JOIN `tabStudent` stu ON stu.name = app.student
        LEFT JOIN `tabPartner Organization` org ON org.name = pl.partner_org
        LEFT JOIN `tabPerson` sup ON sup.name = pl.site_supervisor
        {where}
        ORDER BY pl.placement_status, org.organization_name, stu.student_name
        """,
        values,
        as_dict=True,
    )
    for r in rows:
        allocated = r.get("hours_allocated") or 0
        r["pct"] = (
            round((r.get("hours_logged") or 0) / allocated * 100, 1) if allocated else 0
        )
    return rows
