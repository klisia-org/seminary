# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Program Enrollments by Mentor (ADR 065, amended by ADR 066).

A mentor reaches a student one of two ways: through the student's cohort, or
written directly on the enrollment for a student no cohort covers. Either way
the system derives their presence in each course section from there, which saves
the registrar a great deal of work — and means a gap, a student with no mentor of
a required type, is invisible until grading time. This report is where that gap
is meant to be caught: it is both a mentor's own caseload and the registrar's
coverage check.

The Source column says which origin a row has, because that is where it would be
changed: a Cohort row is edited on the cohort, an Authored one here.

The Unmentored filter answers the question the derivation cannot: which active
students have nobody assigned from either origin.
"""

import frappe
from frappe import _
from frappe.utils import getdate, today

from seminary.seminary import cbe


def execute(filters=None):
    filters = filters or {}
    if filters.get("unmentored"):
        return columns(), unmentored_rows(filters)
    return columns(), mentored_rows(filters)


def columns():
    return [
        {
            "label": _("Mentor"),
            "fieldname": "instructor",
            "fieldtype": "Link",
            "options": "Instructor",
            "width": 180,
        },
        {
            "label": _("Mentor Name"),
            "fieldname": "instructor_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Mentor Type"),
            "fieldname": "instructor_category",
            "fieldtype": "Link",
            "options": "Instructor Category",
            "width": 140,
        },
        {
            "label": _("Student"),
            "fieldname": "student",
            "fieldtype": "Link",
            "options": "Student",
            "width": 110,
        },
        {
            "label": _("Student Name"),
            "fieldname": "student_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Program Enrollment"),
            "fieldname": "program_enrollment",
            "fieldtype": "Link",
            "options": "Program Enrollment",
            "width": 200,
        },
        # Where the statement comes from decides where it is changed: a Cohort
        # mentor is edited on the cohort, an Authored one on the enrollment.
        {
            "label": _("Source"),
            "fieldname": "source",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": _("Cohort"),
            "fieldname": "cohort",
            "fieldtype": "Link",
            "options": "Cohort",
            "width": 160,
        },
        {
            "label": _("Program"),
            "fieldname": "program",
            "fieldtype": "Link",
            "options": "Program",
            "width": 160,
        },
        {
            "label": _("Enrollment Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Term"),
            "fieldname": "current_std_term",
            "fieldtype": "Int",
            "width": 60,
        },
        {
            "label": _("From"),
            "fieldname": "from_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {"label": _("To"), "fieldname": "to_date", "fieldtype": "Date", "width": 100},
        {
            "label": _("Active"),
            "fieldname": "active",
            "fieldtype": "Check",
            "width": 60,
        },
        {"label": _("Issue"), "fieldname": "issue", "fieldtype": "Data", "width": 200},
    ]


def _enrollment_filters(filters):
    ef = {"docstatus": 1}
    if filters.get("program"):
        ef["program"] = filters["program"]
    if filters.get("academic_term"):
        ef["academic_term"] = filters["academic_term"]
    if not filters.get("include_inactive"):
        ef["status"] = "Active"
    return ef


def _enrollments(filters):
    return frappe.get_all(
        "Program Enrollment",
        filters=_enrollment_filters(filters),
        fields=[
            "name",
            "student",
            "student_name",
            "program",
            "status",
            "current_std_term",
        ],
        order_by="program asc, student_name asc",
    )


def mentored_rows(filters):
    """Both origins in one list, because a caseload does not care which it is.

    A mentor asking "whose formation am I following" wants every student, cohort
    or not. The Source column is there for the registrar reading the same list
    with the other question: where do I go to change this.
    """
    enrollments = _enrollments(filters)
    if not enrollments:
        return []

    rows = []
    for e in enrollments:
        for m in cbe.mentors_for_enrollment(e.name):
            if filters.get("instructor") and m["instructor"] != filters["instructor"]:
                continue
            if (
                filters.get("instructor_category")
                and m["instructor_category"] != filters["instructor_category"]
            ):
                continue
            if not filters.get("include_closed") and not m["active"]:
                continue
            rows.append(
                {
                    "instructor": m["instructor"],
                    "instructor_name": m["instructor_name"],
                    "instructor_category": m["instructor_category"],
                    "source": m["source"],
                    "cohort": m["cohort"],
                    "student": e.student,
                    "student_name": e.student_name,
                    "program_enrollment": e.name,
                    "program": e.program,
                    "status": e.status,
                    "current_std_term": e.current_std_term,
                    "from_date": m["from_date"],
                    "to_date": m["to_date"],
                    "active": m["active"],
                    "issue": _issue(m),
                }
            )
    rows.sort(key=lambda r: (r["instructor_name"] or "", r["student_name"] or ""))
    return rows


def _issue(mentor_row):
    """Flag rows whose dates contradict the active flag.

    Only authored rows can contradict themselves. A derived row is a live read
    of a cohort membership -- it is active because the membership is open, so
    there is no second field for it to disagree with.
    """
    if mentor_row["source"] != cbe.AUTHORED:
        return ""
    if (
        mentor_row["active"]
        and mentor_row["to_date"]
        and getdate(mentor_row["to_date"]) < getdate(today())
    ):
        return _("Marked active but the end date has passed")
    if not mentor_row["active"] and not mentor_row["to_date"]:
        return _("Closed without an end date")
    return ""


def unmentored_rows(filters):
    """Active enrollments in competency-based programs with no mentor of the
    required type. Only competency-based programs are considered, since a mentor
    is not expected anywhere else."""
    enrollments = _enrollments(filters)
    if not enrollments:
        return []

    frameworks = {}
    rows = []
    for e in enrollments:
        if e.program not in frameworks:
            frameworks[e.program] = frappe.db.get_value(
                "Program", e.program, "competency_framework"
            )
        framework = frameworks[e.program]
        if not framework:
            continue

        required = frappe.get_all(
            "Competency Framework Evaluator",
            filters={
                "parent": framework,
                "assignment_source": "Program Cohort",
            },
            fields=["instructor_category", "required"],
        )
        if filters.get("instructor_category"):
            required = [
                r
                for r in required
                if r.instructor_category == filters["instructor_category"]
            ]
        if not required:
            continue

        # Resolved the same way the grading engine resolves it, so the coverage
        # check and the thing it is checking cannot drift apart. A student whose
        # cohort supplies the mentor is covered without anyone typing anything.
        held = {
            m["instructor_category"]
            for m in cbe.mentors_for_enrollment(e.name)
            if m["active"]
        }
        for r in required:
            if r.instructor_category in held:
                continue
            rows.append(
                {
                    "instructor": None,
                    "instructor_name": None,
                    "instructor_category": r.instructor_category,
                    "source": None,
                    "cohort": None,
                    "student": e.student,
                    "student_name": e.student_name,
                    "program_enrollment": e.name,
                    "program": e.program,
                    "status": e.status,
                    "current_std_term": e.current_std_term,
                    "active": 0,
                    "issue": (
                        _("No mentor assigned (required)")
                        if r.required
                        else _("No mentor assigned")
                    ),
                }
            )
    return rows
