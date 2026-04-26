# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today


class CulminatingProject(Document):
    def validate(self):
        self._update_round_counter()
        self._stamp_submission_metadata()
        self._derive_milestone_dates()

    def on_submit(self):
        self._link_to_sgr()

    def on_update_after_submit(self):
        self._reflect_state_to_sgr()

    def _update_round_counter(self):
        rounds = [int(s.round or 0) for s in self.submissions or []]
        self.current_round = max(rounds) if rounds else 0

    def _stamp_submission_metadata(self):
        """Auto-stamp submitted_by/submitted_on when a row is added without them."""
        for row in self.submissions or []:
            if not row.submitted_by:
                row.submitted_by = frappe.session.user
            if not row.submitted_on:
                row.submitted_on = now_datetime()
            if (
                row.reviewer_decision
                and row.reviewer_decision != "Pending"
                and not row.reviewed_on
            ):
                row.reviewed_on = now_datetime()

    def _derive_milestone_dates(self):
        """Set proposal_approved_on the first time a Proposal row is Accepted."""
        if self.proposal_approved_on:
            return
        for row in self.submissions or []:
            if (
                row.submission_type == "Proposal"
                and row.reviewer_decision == "Accepted"
            ):
                self.proposal_approved_on = today()
                break

    def _link_to_sgr(self):
        if not self.student_grad_requirement or not self.program_enrollment:
            return
        pe = frappe.get_doc("Program Enrollment", self.program_enrollment)
        dirty = False
        for row in pe.graduation_requirements or []:
            if row.name == self.student_grad_requirement:
                if row.linked_doc != self.name:
                    row.linked_doc = self.name
                    row.link_doctype = "Culminating Project"
                    row.status = "In Progress"
                    dirty = True
                break
        if dirty:
            pe.save(ignore_permissions=True)

    def _reflect_state_to_sgr(self):
        if not self.student_grad_requirement or not self.program_enrollment:
            return

        mapping = {
            "Proposal Submitted": "Submitted",
            "Proposal Approved": "In Progress",
            "Drafting": "In Progress",
            "Under Review": "Submitted",
            "Revisions Required": "In Progress",
            "Approved": "In Progress",
            "Defended": "In Progress",
            "Completed": "Fulfilled",
            "Rejected": "Failed",
        }
        new_status = mapping.get(self.workflow_state)
        if not new_status:
            return

        pe = frappe.get_doc("Program Enrollment", self.program_enrollment)
        dirty = False
        for row in pe.graduation_requirements or []:
            if row.name != self.student_grad_requirement:
                continue
            if row.status != new_status:
                row.status = new_status
                if new_status == "Fulfilled":
                    row.fulfilled_on = today()
                dirty = True
            break
        if dirty:
            pe.save(ignore_permissions=True)


@frappe.whitelist()
def add_submission(name, submission_type, attachment, student_note=None):
    """Whitelisted endpoint for the student to add a new submission round."""
    doc = frappe.get_doc("Culminating Project", name)
    if not _user_owns_project(doc):
        frappe.throw(
            _("You can only submit to your own project."), frappe.PermissionError
        )
    row = doc.append(
        "submissions",
        {
            "round": (doc.current_round or 0) + 1,
            "submission_type": submission_type,
            "attachment": attachment,
            "student_note": student_note,
            "submitted_by": frappe.session.user,
            "submitted_on": now_datetime(),
            "reviewer": doc.advisor,
            "reviewer_decision": "Pending",
        },
    )
    doc.save(ignore_permissions=True)
    return {"round": row.round}


def _user_owns_project(doc):
    user_email = frappe.session.user
    student_email = frappe.db.get_value("Student", doc.student, "student_email_id")
    return user_email == student_email
