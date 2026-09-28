# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

"""One student's own dates on one assessment (decisions/082 section 2).

Blank fields follow the assessment row. Saving or deleting re-prices that
student's grade card, so a later due date lifts a deduction already taken.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime


class StudentDueDateOverride(Document):
    def validate(self):
        row = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            self.course_assess,
            ["parent", "title", "due_date", "discussion"],
            as_dict=True,
        )
        if not row:
            frappe.throw(_("Choose an assessment of this section."))
        if self.course_schedule and self.course_schedule != row.parent:
            frappe.throw(
                _("{0} belongs to another section, not {1}.").format(
                    row.title, self.course_schedule
                )
            )
        self.course_schedule = row.parent
        self.assessment_title = row.title

        from seminary.seminary.guards import require_course_staff

        require_course_staff(self.course_schedule, include_registrar=True)

        if not frappe.db.exists(
            "Scheduled Course Roster",
            {"course_sc": self.course_schedule, "student": self.student},
        ):
            frappe.throw(
                _("{0} is not on the roster of {1}.").format(
                    self.student_name or self.student, self.course_schedule
                )
            )
        if frappe.db.exists(
            "Student Due Date Override",
            {
                "course_assess": self.course_assess,
                "student": self.student,
                "name": ["!=", self.name],
            },
        ):
            frappe.throw(
                _(
                    "{0} already has different dates for {1}. Edit that one instead."
                ).format(self.student_name or self.student, row.title)
            )
        if not any(
            (
                self.due_date,
                self.cutoff_date,
                self.replies_due_date,
                self.extra_minutes,
                self.extra_attempts,
            )
        ):
            frappe.throw(_("Set at least one date, extra minutes or extra attempts."))
        due = self.due_date or row.due_date
        if (
            self.cutoff_date
            and due
            and get_datetime(self.cutoff_date) < get_datetime(due)
        ):
            frappe.throw(
                _("The cut-off is before the due date. Move it after {0}.").format(
                    frappe.utils.format_datetime(due)
                )
            )
        if self.replies_due_date and not row.discussion:
            self.replies_due_date = None

    def on_update(self):
        self._reprice()

    def on_trash(self):
        from seminary.seminary.guards import require_course_staff

        require_course_staff(self.course_schedule, include_registrar=True)

    def after_delete(self):
        self._reprice()

    def _reprice(self):
        from seminary.seminary import deadlines

        deadlines.refresh(self.course_assess, [self.student])
