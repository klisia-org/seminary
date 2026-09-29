import frappe
from frappe import _

"""The registrar's enrollment check for a term (ADR 083 §5): every active
Time-based enrollment × every course its term expects, with the enrollment and
its state, or the reason there is none. "Gaps only" is on by default, and
ticked gaps can be sent to a new Bulk Course Enrollment."""

from seminary.seminary.required_enrollment import unmet_prerequisites
from seminary.seminary.term_plan import expected_courses, time_based_enrollments


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
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "fieldname": "cei",
            "label": _("Course Enrollment"),
            "fieldtype": "Link",
            "options": "Course Enrollment Individual",
            "width": 170,
        },
        {
            "fieldname": "course_schedule",
            "label": _("Section"),
            "fieldtype": "Link",
            "options": "Course Schedule",
            "width": 170,
        },
        {
            "fieldname": "reason",
            "label": _("Reason"),
            "fieldtype": "Data",
            "width": 220,
        },
        {"fieldname": "gap", "label": _("Gap"), "fieldtype": "Check", "hidden": 1},
    ]


STATE_LABELS = {
    "Submitted": "Enrolled",
    "Concluded": "Enrolled",
    "Awaiting Payment": "Awaiting Payment",
    "Waitlisted": "Waitlisted",
    "Draft": "Draft",
    "Unseated": "Unseated",
}


def get_data(filters):
    academic_term = filters.get("academic_term")
    if not academic_term:
        return []
    gaps_only = int(filters.get("gaps_only") or 0)
    programs = [filters["program"]] if filters.get("program") else None
    pes = time_based_enrollments(academic_term, programs=programs)
    if not pes:
        return []

    # Every non-cancelled section in the term, by course: open ones and the rest.
    open_courses, closed_courses = set(), set()
    for cs in frappe.get_all(
        "Course Schedule",
        filters={"academic_term": academic_term, "workflow_state": ["!=", "Cancelled"]},
        fields=["course", "workflow_state"],
    ):
        if cs.workflow_state == "Open for Enrollment":
            open_courses.add(cs.course)
        else:
            closed_courses.add(cs.course)

    data = []
    for pe in pes:
        for ec in expected_courses(pe):
            row = {
                "program_enrollment": pe.name,
                "student": pe.student,
                "student_name": pe.student_name,
                "program": pe.program,
                "current_std_term": pe.current_std_term,
                "course": ec.course,
                "course_name": ec.course_name or ec.course,
                "status": None,
                "cei": None,
                "course_schedule": None,
                "reason": None,
                "gap": 0,
            }
            cei = _live_enrollment(pe.name, ec.course, academic_term)
            if cei:
                row.update(
                    status=_(
                        STATE_LABELS.get(cei.workflow_state, cei.workflow_state or "")
                    ),
                    cei=cei.name,
                    course_schedule=cei.coursesc_ce,
                )
            elif _passed(pe.name, ec.course):
                row["status"] = _("Passed")
            else:
                row.update(
                    status=_("Missing"),
                    reason=_classify_gap(
                        pe.name, ec.course, open_courses, closed_courses
                    ),
                    gap=1,
                )
            if gaps_only and not row["gap"]:
                continue
            data.append(row)
    return data


def _live_enrollment(pe_name, course, academic_term):
    """The student's live, non-audit enrollment in the course, preferring one in
    this term."""
    rows = frappe.db.sql(
        """SELECT cei.name, cei.workflow_state, cei.coursesc_ce,
                  (cei.academic_term = %(term)s) AS this_term
           FROM `tabCourse Enrollment Individual` cei
           WHERE cei.program_ce = %(pe)s AND cei.course_data = %(course)s
             AND cei.audit = 0 AND cei.docstatus != 2
             AND cei.course_cancelled = 0 AND cei.withdrawn = 0
           ORDER BY this_term DESC, cei.creation DESC
           LIMIT 1""",
        {"pe": pe_name, "course": course, "term": academic_term},
        as_dict=True,
    )
    return rows[0] if rows else None


def _passed(pe_name, course):
    return bool(
        frappe.db.exists(
            "Program Enrollment Course",
            {
                "parent": pe_name,
                "course_name": course,
                "pec_finalgradecode": ["is", "set"],
                "status": ["!=", "Fail"],
            },
        )
    )


def _classify_gap(pe_name, course, open_courses, closed_courses):
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

    if course in open_courses:
        return _("Not yet enrolled")
    if course in closed_courses:
        return _("Offering closed")
    return _("No open offering this term")
