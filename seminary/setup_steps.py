# Copyright (c) 2026, Murilo R. Melo and contributors
# For license information, please see license.txt

"""Seminary's setup steps, in the order of the Initial Setup guide (privatedocs p024 §5)."""

import frappe
from frappe import _
from frappe.utils import today

GUIDE = "seminary/docs/en/getting-started/initial-setup.md"
MANAGERS = ["Seminary Manager"]
REGISTRARS = ["Registrar", "Seminary Manager"]


def _exists(doctype, filters=None):
    return bool(frappe.db.exists(doctype, filters or {}))


def _programs_with_courses():
    programs = frappe.get_all("Program", pluck="name")
    with_courses = set(
        frappe.get_all(
            "Program Course",
            filters={"parenttype": "Program", "parent": ["in", programs or [""]]},
            pluck="parent",
            distinct=True,
        )
    )
    return len(with_courses), len(programs)


def _staff_roles():
    """A person other than Administrator holds each office the school runs on."""
    roles = ("Seminary Manager", "Registrar")
    held = {
        r.role
        for r in frappe.get_all(
            "Has Role",
            filters={
                "parenttype": "User",
                "role": ["in", roles],
                "parent": ["not in", ["Administrator", "Guest"]],
            },
            fields=["role"],
        )
    }
    return len(held), len(roles)


def _term_ahead():
    return _exists("Academic Term", {"term_end_date": [">=", today()]})


def _schedules_ahead():
    terms = frappe.get_all(
        "Academic Term", filters={"term_end_date": [">=", today()]}, pluck="name"
    )
    return bool(terms) and _exists("Course Schedule", {"academic_term": ["in", terms]})


def setup_steps():
    return {
        "name": "Seminary",
        "label": _("Seminary"),
        "page": "seminary-setup",
        "roles": REGISTRARS,
        "steps": [
            {
                "key": "grading-scale",
                "title": _("Create the grading scale"),
                "tier": "Go-live",
                "check": lambda: _exists("Grading Scale"),
                "route": "/desk/grading-scale",
                "manual": f"{GUIDE}#1-grading-scale",
                "roles": MANAGERS,
            },
            {
                "key": "default-grading-scale",
                "title": _("Choose the default grading scale in Seminary Settings"),
                "tier": "Go-live",
                "check": lambda: bool(
                    frappe.db.get_single_value(
                        "Seminary Settings", "default_gradescale"
                    )
                ),
                "route": "/desk/seminary-settings",
                "manual": f"{GUIDE}#2-seminary-settings",
                "roles": MANAGERS,
            },
            {
                "key": "staff-roles",
                "title": _(
                    "Give the Seminary Manager and Registrar roles to your staff"
                ),
                "tier": "Go-live",
                "check": _staff_roles,
                "route": "/desk/user",
                "manual": f"{GUIDE}#13-user-roles",
                "roles": MANAGERS,
            },
            {
                "key": "academic-year",
                "title": _("Create the academic year"),
                "tier": "Go-live",
                "check": lambda: _exists("Academic Year"),
                "route": "/desk/academic-year",
                "manual": f"{GUIDE}#9-academic-year",
                "roles": REGISTRARS,
            },
            {
                "key": "academic-term",
                "title": _("Create the coming academic term"),
                "tier": "Go-live",
                "check": _term_ahead,
                "route": "/desk/academic-term",
                "manual": f"{GUIDE}#10-academic-term",
                "roles": REGISTRARS,
            },
            {
                "key": "programs",
                "title": _("Create your programs"),
                "tier": "Go-live",
                "check": lambda: _exists("Program"),
                "route": "/desk/program",
                "manual": f"{GUIDE}#11-program",
                "roles": REGISTRARS,
            },
            {
                "key": "program-courses",
                "title": _("Add courses to every program"),
                "description": _(
                    "Select courses in the Course list and use Actions, Add to Program."
                ),
                "tier": "Go-live",
                "check": _programs_with_courses,
                "route": "/desk/course",
                "manual": f"{GUIDE}#14-manual-input-or-import-the-following-data",
                "roles": REGISTRARS,
            },
            {
                "key": "instructors",
                "title": _("Add your instructors"),
                "tier": "Before the first term",
                "check": lambda: _exists("Instructor"),
                "route": "/desk/instructor",
                "manual": f"{GUIDE}#16-add-instructors",
                "roles": REGISTRARS,
            },
            {
                "key": "people",
                "title": _("Import your students"),
                "tier": "Before the first term",
                "check": lambda: _exists("Student"),
                "route": "/desk/person-import-batch",
                "manual": f"{GUIDE}#14-manual-input-or-import-the-following-data",
                "roles": REGISTRARS,
            },
            {
                "key": "program-enrollments",
                "title": _("Enroll students in their programs"),
                "tier": "Before the first term",
                "check": lambda: _exists("Program Enrollment"),
                "route": "/desk/program-enrollment",
                "manual": f"{GUIDE}#14-manual-input-or-import-the-following-data",
                "roles": REGISTRARS,
            },
            {
                "key": "course-schedules",
                "title": _("Schedule the coming term's courses"),
                "tier": "Before the first term",
                "check": _schedules_ahead,
                "route": "/desk/course-schedule",
                "manual": f"{GUIDE}#12-course-schedule-lifecycle",
                "roles": REGISTRARS,
            },
            {
                "key": "legacy-grades",
                "title": _("Import grades from your previous system"),
                "tier": "Optional",
                "check": lambda: _exists(
                    "Partner Transcript Import Batch", {"docstatus": 1}
                ),
                "route": "/desk/partner-transcript-import-batch",
                "manual": f"{GUIDE}#15-import-existing-grades",
                "roles": REGISTRARS,
            },
        ],
    }
