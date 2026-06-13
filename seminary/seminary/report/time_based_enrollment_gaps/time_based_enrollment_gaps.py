import frappe
from frappe import _

from seminary.seminary.required_enrollment import _already_covered, unmet_prerequisites


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "fieldname": "program_enrollment",
            "label": _("Enrollment"),
            "fieldtype": "Link",
            "options": "Program Enrollment",
            "width": 150,
        },
        {
            "fieldname": "student",
            "label": _("Student"),
            "fieldtype": "Link",
            "options": "Student",
            "width": 130,
        },
        {
            "fieldname": "student_name",
            "label": _("Student Name"),
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
            "fieldname": "current_std_term",
            "label": _("Term"),
            "fieldtype": "Int",
            "width": 70,
        },
        {
            "fieldname": "course",
            "label": _("Course"),
            "fieldtype": "Link",
            "options": "Course",
            "width": 180,
        },
        {
            "fieldname": "course_name",
            "label": _("Course Name"),
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "fieldname": "reason",
            "label": _("Reason"),
            "fieldtype": "Data",
            "width": 220,
        },
    ]


def get_data(filters):
    # Active Time-based enrollments only.
    pe_conditions = (
        "pe.docstatus = 1 AND pe.pgmenrol_active = 1 AND p.program_type = 'Time-based'"
    )
    params = {}
    if filters.get("program"):
        pe_conditions += " AND pe.program = %(program)s"
        params["program"] = filters["program"]

    pes = frappe.db.sql(
        f"""SELECT pe.name, pe.student, pe.program, pe.current_std_term
            FROM `tabProgram Enrollment` pe
            INNER JOIN `tabProgram` p ON p.name = pe.program
            WHERE {pe_conditions}""",
        params,
        as_dict=True,
    )
    if not pes:
        return []

    # Courses with an open offering for the term we measure against — the
    # explicit Offering Term filter, else the flagged current term.
    offering_term = filters.get("academic_term") or frappe.db.get_value(
        "Academic Term", {"iscurrent_acterm": 1}, "name"
    )
    open_courses = set()
    if offering_term:
        open_courses = set(
            frappe.get_all(
                "Course Schedule",
                filters={
                    "academic_term": offering_term,
                    "workflow_state": "Open for Enrollment",
                },
                pluck="course",
            )
        )

    student_names = {}

    def student_name(student):
        if student not in student_names:
            student_names[student] = (
                frappe.db.get_value("Student", student, "student_name") or ""
            )
        return student_names[student]

    data = []
    for pe in pes:
        term = pe.current_std_term or 0
        if not term:
            continue
        # Expected courses for the student's current term. A student past the
        # last populated course_term matches nothing here (correct — graduated /
        # beyond curriculum students produce no gaps).
        expected = frappe.get_all(
            "Program Course",
            filters={"parent": pe.program, "course_term": term, "disabled": 0},
            fields=["course", "course_name"],
        )
        for ec in expected:
            course = ec.course
            if _already_covered(pe.name, course):
                continue

            reason = _classify_gap(pe.name, course, open_courses)
            data.append(
                {
                    "program_enrollment": pe.name,
                    "student": pe.student,
                    "student_name": student_name(pe.student),
                    "program": pe.program,
                    "current_std_term": pe.current_std_term,
                    "course": course,
                    "course_name": ec.course_name or course,
                    "reason": reason,
                }
            )

    return data


def _classify_gap(pe_name, course, open_courses):
    """Single, highest-priority reason a not-yet-covered expected course is a
    gap. Order = most-actionable first for the registrar."""
    failed_before = frappe.db.exists(
        "Program Enrollment Course",
        {"parent": pe_name, "course_name": course, "status": "Fail"},
    )
    if failed_before:
        return _("Failed previously")

    missing = unmet_prerequisites(pe_name, course)
    if missing:
        return _("Unmet prerequisite: {0}").format(", ".join(missing))

    if course not in open_courses:
        return _("No open offering this term")

    return _("Not yet enrolled")
