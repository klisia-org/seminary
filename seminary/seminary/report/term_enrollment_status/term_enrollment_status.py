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
            "fieldname": "course_schedule",
            "label": _("Course Schedule"),
            "fieldtype": "Link",
            "options": "Course Schedule",
            "width": 260,
        },
        {
            "fieldname": "academic_term",
            "label": _("Academic Term"),
            "fieldtype": "Link",
            "options": "Academic Term",
            "width": 140,
        },
        {
            "fieldname": "workflow_state",
            "label": _("State"),
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "fieldname": "minimum_enrollment",
            "label": _("Min"),
            "fieldtype": "Int",
            "width": 70,
        },
        {
            "fieldname": "current_enrollment",
            "label": _("Current"),
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "fieldname": "delta",
            "label": _("Delta"),
            "fieldtype": "Int",
            "width": 70,
        },
        {
            "fieldname": "course",
            "label": _("Course"),
            "fieldtype": "Link",
            "options": "Course",
            "width": 200,
        },
    ]


def get_data(filters):
    conditions = ["1 = 1"]
    params = {}

    if filters.get("academic_term"):
        conditions.append("cs.academic_term = %(academic_term)s")
        params["academic_term"] = filters["academic_term"]
    else:
        # Default to the current academic term if the user didn't pick one.
        conditions.append("aterm.iscurrent_acterm = 1")

    if filters.get("workflow_state"):
        conditions.append("cs.workflow_state = %(workflow_state)s")
        params["workflow_state"] = filters["workflow_state"]

    rows = frappe.db.sql(
        f"""
		SELECT
			cs.name AS course_schedule,
			cs.academic_term,
			cs.workflow_state,
			cs.course,
			COALESCE(cs.minimum_enrollment, c.default_minimum_enrollment) AS minimum_enrollment,
			(
				SELECT COUNT(*)
				FROM `tabCourse Enrollment Individual` cei
				WHERE cei.coursesc_ce = cs.name
				  AND cei.docstatus = 1
				  AND cei.withdrawn = 0
				  AND IFNULL(cei.course_cancelled, 0) = 0
				  AND cei.audit = 0
			) AS current_enrollment
		FROM `tabCourse Schedule` cs
		JOIN `tabAcademic Term` aterm ON aterm.name = cs.academic_term
		JOIN `tabCourse` c ON c.name = cs.course
		WHERE {' AND '.join(conditions)}
		ORDER BY cs.academic_term DESC, cs.name
		""",
        params,
        as_dict=True,
    )

    for row in rows:
        minimum = row["minimum_enrollment"] or 0
        current = row["current_enrollment"] or 0
        row["delta"] = current - minimum if minimum else None

    if filters.get("below_minimum_only"):
        rows = [r for r in rows if r["delta"] is not None and r["delta"] < 0]

    return rows
