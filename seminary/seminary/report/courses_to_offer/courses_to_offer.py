import frappe
from frappe import _


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "fieldname": "course",
            "label": _("Course"),
            "fieldtype": "Link",
            "options": "Course",
            "width": 200,
        },
        {
            "fieldname": "students_needing",
            "label": _("Students Needing"),
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "fieldname": "graduating_next_term",
            "label": _("Graduating Next Term"),
            "fieldtype": "Int",
            "width": 150,
        },
        {
            "fieldname": "graduating_two_terms",
            "label": _("Graduating in 2 Terms"),
            "fieldtype": "Int",
            "width": 150,
        },
    ]


def get_data(filters):
    # Get all active program enrollments
    pe_filters = {"pgmenrol_active": 1, "docstatus": 1}
    if filters.get("program"):
        pe_filters["program"] = filters["program"]

    enrollments = frappe.get_all(
        "Program Enrollment",
        filters=pe_filters,
        fields=["name", "program", "totalcredits"],
    )

    if not enrollments:
        return []

    # Get program credit requirements
    program_credits = {}
    for pe in enrollments:
        if pe.program not in program_credits:
            program_credits[pe.program] = (
                frappe.db.get_value("Program", pe.program, "credits_complete") or 0
            )

    # Collect all mandatory courses across programs
    # Key: course name -> aggregated counts
    course_demand = {}

    for pe in enrollments:
        credits_complete = program_credits[pe.program]
        credits_remaining = max(0, credits_complete - (pe.totalcredits or 0))

        # Estimate terms to graduation (assume ~15 credits per term)
        credits_per_term = 15
        terms_to_grad = (
            round(credits_remaining / credits_per_term) if credits_per_term else 99
        )

        # Get mandatory program courses not yet passed by this student
        mandatory_not_passed = frappe.db.sql(
            """SELECT pc.course, pc.course_name
			FROM `tabProgram Course` pc
			WHERE pc.parent = %s AND pc.required = 1
				AND pc.course NOT IN (
					SELECT pec.course_name
					FROM `tabProgram Enrollment Course` pec
					WHERE pec.parent = %s AND pec.status = 'Pass'
				)""",
            (pe.program, pe.name),
            as_dict=True,
        )

        # Get mandatory track courses not yet passed
        mandatory_track_not_passed = frappe.db.sql(
            """SELECT ptc.program_track_course AS course
			FROM `tabProgram Track Courses` ptc
			INNER JOIN `tabProgram Enrollment Emphasis` pee
				ON pee.parent = %s AND pee.emphasis_track = ptc.program_track
				AND pee.status IN ('Active', 'Completed')
			WHERE ptc.parent = %s AND ptc.pgm_track_course_mandatory = 1
				AND ptc.program_track_course NOT IN (
					SELECT pec.course_name
					FROM `tabProgram Enrollment Course` pec
					WHERE pec.parent = %s AND pec.status = 'Pass'
				)""",
            (pe.name, pe.program, pe.name),
            as_dict=True,
        )

        all_needed = set()
        for row in mandatory_not_passed:
            all_needed.add((row.course, row.course_name or row.course))
        for row in mandatory_track_not_passed:
            course_name = (
                frappe.db.get_value("Course", row.course, "course_name") or row.course
            )
            all_needed.add((row.course, course_name))

        for course, course_name in all_needed:
            if course not in course_demand:
                course_demand[course] = {
                    "course": course,
                    "course_name": course_name,
                    "students_needing": 0,
                    "graduating_next_term": 0,
                    "graduating_two_terms": 0,
                }

            course_demand[course]["students_needing"] += 1

            if terms_to_grad <= 1:
                course_demand[course]["graduating_next_term"] += 1
            elif terms_to_grad <= 2:
                course_demand[course]["graduating_two_terms"] += 1

    # Sort by demand (students needing, descending)
    data = sorted(
        course_demand.values(), key=lambda x: x["students_needing"], reverse=True
    )

    return data
