# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Personal Development Plan (ADR 065 section 8).

One plan per student per section, written at the end of a course. The framework
supplies the prompts; the goals are the student's own. Nothing carries forward
from a previous course's plan -- continuity is a reading concern, handled by the
aggregate view, not a storage one.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

STAFF_ROLES = {
    "Seminary Manager",
    "System Manager",
    "Program Chair",
    "Registrar",
    "Instructor",
}


class PersonalDevelopmentPlan(Document):
    def validate(self):
        self.set_context()
        self.validate_unique()
        self.validate_goals()
        self.stamp_submission()

    def set_context(self):
        """Derive the enrollment and student from the roster.

        The plan is anchored to a roster row, and everything else about who and
        where follows from it; deriving rather than trusting keeps a hand-built
        record from claiming to belong to a section the student is not in.
        """
        if not self.roster:
            return
        roster = frappe.db.get_value(
            "Scheduled Course Roster",
            self.roster,
            ["student", "course_sc"],
            as_dict=True,
        )
        if not roster:
            frappe.throw(_("Roster {0} does not exist.").format(self.roster))
        self.student = roster.student
        self.course_schedule = roster.course_sc
        if not self.program_enrollment:
            self.program_enrollment = frappe.db.get_value(
                "Program Enrollment",
                {"student": self.student, "docstatus": 1},
                "name",
                order_by="pgmenrol_active desc, creation desc",
            )

    def validate_unique(self):
        """One plan per roster row.

        Compared after the fact rather than filtered on `name != self.name`:
        autoname has already stamped a new doc, so that filter would exclude the
        very record being looked for and let the duplicate through.
        """
        duplicate = frappe.db.get_value(
            "Personal Development Plan", {"roster": self.roster}, "name"
        )
        if duplicate and (self.is_new() or duplicate != self.name):
            frappe.throw(
                _(
                    "This student already has a development plan for this course ({0})."
                ).format(duplicate)
            )

    def validate_goals(self):
        """Denormalise the prompt, and keep a competency's dimension honest."""
        questions = self._questions()
        for row in self.goals:
            if row.standard_question:
                if row.standard_question not in questions:
                    frappe.throw(
                        _("Row {0}: {1} is not a question in this framework.").format(
                            row.idx, row.standard_question
                        )
                    )
                # Denormalised on every save so a reworded prompt does not leave
                # stale text sitting above the answer it produced.
                row.question_text = frappe.utils.strip_html(
                    questions[row.standard_question] or ""
                ).strip()
            if row.dimension_code and not row.course_competency:
                frappe.throw(
                    _("Row {0}: choose a competency before naming a dimension.").format(
                        row.idx
                    )
                )

    def _questions(self):
        from seminary.seminary import cbe

        framework = cbe.framework_doc(self.course_schedule)
        if not framework:
            return {}
        return {
            q.question_key: q.question_text for q in framework.development_questions
        }

    def stamp_submission(self):
        if self.status != "Draft" and not self.submitted_on:
            self.submitted_on = now_datetime()


def get_permission_query_conditions(user=None):
    """Students see only their own plans.

    A plan is a student's account of where they most need to grow; the list view
    must not become a way to read a classmate's.
    """
    user = user or frappe.session.user
    if STAFF_ROLES & set(frappe.get_roles(user)):
        return ""
    student = frappe.db.get_value("Student", {"user": user}, "name")
    if not student:
        return "1=0"
    return "`tabPersonal Development Plan`.student = " f"{frappe.db.escape(student)}"


def has_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if STAFF_ROLES & set(frappe.get_roles(user)):
        return True
    student = frappe.db.get_value("Student", {"user": user}, "name")
    return bool(student) and doc.student == student
