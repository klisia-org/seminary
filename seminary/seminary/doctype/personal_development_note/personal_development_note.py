# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Personal Development Note (ADR 065 section 8a).

A student's journal about their own formation. Some formation goals are never
"Achieved" -- spiritual vitality, besetting sin, vocational clarity -- and a
status field that only offers completion quietly tells a student their real
struggles are failures. Notes are where that work lives instead.

They are deliberately not private. The student's active mentors can read them,
resolved live rather than granted, so access ends when the mentoring
relationship does. The portal says so where the student writes, because a
journal whose readership the writer has to guess is worse than one with no
readers at all.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

STAFF_ROLES = {"Seminary Manager", "System Manager", "Program Chair"}


class PersonalDevelopmentNote(Document):
    def validate(self):
        self.set_defaults()
        self.validate_anchors()

    def set_defaults(self):
        if not self.note_date:
            self.note_date = now_datetime()
        if not self.program_enrollment and self.student:
            self.program_enrollment = frappe.db.get_value(
                "Program Enrollment",
                {"student": self.student, "docstatus": 1},
                "name",
                order_by="pgmenrol_active desc, creation desc",
            )

    def validate_anchors(self):
        """A note may be anchored loosely, but never wrongly."""
        if self.dimension_code and not self.course_competency:
            frappe.throw(_("Choose a competency before naming a dimension."))
        if self.development_plan:
            owner = frappe.db.get_value(
                "Personal Development Plan", self.development_plan, "student"
            )
            if owner != self.student:
                frappe.throw(
                    _("Plan {0} belongs to another student.").format(
                        self.development_plan
                    )
                )


def _reader_scope(user):
    """(is_staff, student, instructor) for the user asking."""
    roles = set(frappe.get_roles(user))
    return (
        bool(STAFF_ROLES & roles),
        frappe.db.get_value("Student", {"user": user}, "name"),
        frappe.db.get_value("Instructor", {"user": user}, "name"),
    )


def get_permission_query_conditions(user=None):
    """Own notes, plus the notes of students one currently mentors.

    Mentees are resolved at read time and written into the condition as a fixed
    list. That is the honest shape: the relationship lives in Program Enrollment
    Mentor rows and section instructor rows, which no SQL join from this table
    can express, and materialising it per request is what makes access end when
    the relationship does.
    """
    from seminary.seminary import cbe

    user = user or frappe.session.user
    is_staff, student, instructor = _reader_scope(user)
    if is_staff:
        return ""

    allowed = set()
    if student:
        allowed.add(student)
    if instructor:
        allowed.update(cbe.mentees_of(instructor))
    if not allowed:
        return "1=0"

    joined = ", ".join(frappe.db.escape(s) for s in sorted(allowed))
    return f"`tabPersonal Development Note`.student in ({joined})"


def has_permission(doc, user=None, permission_type=None):
    """Students write their own; mentors only ever read.

    The write side is checked here as well as on the endpoint, because a mentor
    holds the Instructor role and would otherwise inherit whatever the doctype
    grants that role.
    """
    from seminary.seminary import cbe

    user = user or frappe.session.user
    is_staff, student, instructor = _reader_scope(user)
    if is_staff:
        return True
    if student and doc.student == student:
        return True
    if permission_type in (None, "read", "select", "report"):
        return bool(instructor) and cbe.is_mentor_of(instructor, doc.student)
    return False
