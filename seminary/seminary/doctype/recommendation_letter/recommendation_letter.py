# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import secrets

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, get_url, now_datetime, today

TOKEN_TTL_DAYS = 90


class RecommendationLetter(Document):
    def validate(self):
        if not self.request_token:
            self.request_token = _generate_token()
        if not self.token_expires_on:
            self.token_expires_on = add_days(today(), TOKEN_TTL_DAYS)

    def on_submit(self):
        self._link_to_sgr()
        self._send_request_email()

    def on_update_after_submit(self):
        self._reflect_state_to_sgr()

    def _link_to_sgr(self):
        """Write this letter's name onto the SGR row's linked_doc field."""
        if not self.student_grad_requirement or not self.program_enrollment:
            return
        pe = frappe.get_doc("Program Enrollment", self.program_enrollment)
        updated = False
        for row in pe.graduation_requirements or []:
            if row.name == self.student_grad_requirement:
                if row.linked_doc != self.name:
                    row.linked_doc = self.name
                    row.link_doctype = "Recommendation Letter"
                    row.status = "In Progress"
                    updated = True
                break
        if updated:
            pe.save(ignore_permissions=True)

    def _send_request_email(self):
        if self.delivery_method == "Manual Upload":
            return
        if not self.recommender_email:
            return

        portal_url = get_url(
            f"/recommender-form/{self.name}?token={self.request_token}"
        )
        student_name = (
            frappe.db.get_value("Student", self.student, "student_name") or ""
        )
        subject = _("Recommendation request for {0}").format(student_name)
        message = _(
            "Dear {0},<br><br>"
            "{1} has requested a recommendation letter from you for their seminary program. "
            "Please use the secure link below to submit your letter:<br><br>"
            '<a href="{2}">{2}</a><br><br>'
            "This link expires on {3}. Thank you."
        ).format(self.recommender_name, student_name, portal_url, self.token_expires_on)

        frappe.sendmail(
            recipients=[self.recommender_email],
            subject=subject,
            message=message,
            reference_doctype=self.doctype,
            reference_name=self.name,
        )
        self.db_set("request_sent_on", now_datetime(), update_modified=False)
        _advance_state(self, "Requested")

    def _reflect_state_to_sgr(self):
        """Mirror workflow_state changes onto the SGR row's status."""
        if not self.student_grad_requirement or not self.program_enrollment:
            return

        mapping = {
            "Requested": "In Progress",
            "Awaiting Response": "In Progress",
            "Submitted": "Submitted",
            "Under Review": "Submitted",
            "Approved": "Fulfilled",
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


def _generate_token():
    return secrets.token_urlsafe(32)


def _advance_state(doc, target_state):
    if doc.workflow_state == target_state:
        return
    doc.db_set("workflow_state", target_state, update_modified=False)


@frappe.whitelist()
def regenerate_token(name):
    """Issue a new token (e.g. when the recommender lost the email)."""
    doc = frappe.get_doc("Recommendation Letter", name)
    doc.db_set("request_token", _generate_token(), update_modified=False)
    doc.db_set(
        "token_expires_on", add_days(today(), TOKEN_TTL_DAYS), update_modified=False
    )
    return {"token": doc.request_token, "expires_on": doc.token_expires_on}
