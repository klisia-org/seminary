# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Program Enrollments by Mentor (ADR 065).

Mentors are recorded once on a student's Program Enrollment and the system
derives their presence in each course section from there. That saves the
registrar a great deal of work, but it also means a gap — a student with no
mentor of a required type — is invisible until grading time. This report is
where that gap is meant to be caught: it is both a mentor's own caseload and the
registrar's coverage check.

The Unmentored filter answers the question the derivation cannot: which active
students have nobody assigned.
"""

import frappe
from frappe import _
from frappe.utils import getdate, today


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
    enrollments = _enrollments(filters)
    if not enrollments:
        return []
    by_name = {e.name: e for e in enrollments}

    mentor_filters = {"parent": ("in", list(by_name))}
    if filters.get("instructor"):
        mentor_filters["instructor"] = filters["instructor"]
    if filters.get("instructor_category"):
        mentor_filters["instructor_category"] = filters["instructor_category"]
    if not filters.get("include_closed"):
        mentor_filters["active"] = 1

    mentors = frappe.get_all(
        "Program Enrollment Mentor",
        filters=mentor_filters,
        fields=[
            "parent",
            "instructor",
            "instructor_name",
            "instructor_category",
            "from_date",
            "to_date",
            "active",
        ],
        order_by="instructor_name asc, from_date asc",
    )

    rows = []
    for m in mentors:
        e = by_name[m.parent]
        rows.append(
            {
                "instructor": m.instructor,
                "instructor_name": m.instructor_name,
                "instructor_category": m.instructor_category,
                "student": e.student,
                "student_name": e.student_name,
                "program_enrollment": e.name,
                "program": e.program,
                "status": e.status,
                "current_std_term": e.current_std_term,
                "from_date": m.from_date,
                "to_date": m.to_date,
                "active": m.active,
                "issue": _issue(m),
            }
        )
    return rows


def _issue(mentor_row):
    """Flag rows whose dates contradict the active flag.

    Evaluator resolution filters mentor rows by date as well as by the flag, so
    a row that is marked active but has already ended will quietly stop
    producing an evaluator. Saying so here is the whole point of the report.
    """
    if (
        mentor_row.active
        and mentor_row.to_date
        and getdate(mentor_row.to_date) < getdate(today())
    ):
        return _("Marked active but the end date has passed")
    if not mentor_row.active and not mentor_row.to_date:
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
                "assignment_source": "Program Enrollment Mentor",
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

        held = {
            m.instructor_category
            for m in frappe.get_all(
                "Program Enrollment Mentor",
                filters={"parent": e.name, "active": 1},
                fields=["instructor_category"],
            )
        }
        for r in required:
            if r.instructor_category in held:
                continue
            rows.append(
                {
                    "instructor": None,
                    "instructor_name": None,
                    "instructor_category": r.instructor_category,
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
