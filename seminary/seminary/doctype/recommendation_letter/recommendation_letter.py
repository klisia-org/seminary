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

    def _send_request_email(self, resend=False):
        """Email the recommender the tokenized link. Returns the Communication
        Log name, or None when nothing was sent (manual delivery, no address,
        or deduped).

        The first request is deduped per letter; a `resend` (a regenerated
        token) is deduped per token instead, so the recommender receives the
        new link rather than being silenced by the original send's key."""
        if self.delivery_method == "Manual Upload":
            return None
        if not self.recommender_email:
            return None

        from seminary.seminary import comms
        from seminary.seminary.person import find_person

        portal_url = get_url(
            f"/recommender-form/{self.name}?token={self.request_token}"
        )
        student_name = (
            frappe.db.get_value("Student", self.student, "student_name") or ""
        )
        dedupe_key = f"recommendation-request::{self.name}"
        if resend:
            dedupe_key += f"::{self.request_token}"
        log = comms.send(
            find_person(email=self.recommender_email),
            "recommendation-request",
            to_address=self.recommender_email,
            context={
                "recommender": self.recommender_name,
                "student": student_name,
                "url": portal_url,
                "expires": self.token_expires_on,
            },
            reference_doctype=self.doctype,
            reference_name=self.name,
            triggered_by="recommendation-request",
            dedupe_key=dedupe_key,
        )
        self.db_set("request_sent_on", now_datetime(), update_modified=False)
        _advance_state(self, "Requested")
        return log

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
    """Issue a new token (e.g. when the recommender lost the email) and email
    it to the recommender (p006 F12).

    Requires write on the letter — Student has no write row, so the student
    the letter is about cannot mint links for their own recommender. The
    token itself is never returned: it travels only in the recommender's
    email. The response carries what the Desk needs to confirm the resend."""
    frappe.has_permission("Recommendation Letter", "write", doc=name, throw=True)
    doc = frappe.get_doc("Recommendation Letter", name)
    doc.db_set("request_token", _generate_token(), update_modified=False)
    doc.db_set(
        "token_expires_on", add_days(today(), TOKEN_TTL_DAYS), update_modified=False
    )
    sent_to = None
    try:
        if doc._send_request_email(resend=True):
            sent_to = doc.recommender_email
    except Exception:
        # The token is already rotated; a delivery failure must not undo that
        # or hide the new expiry from the Desk. Logged for follow-up.
        frappe.log_error(
            title=f"Recommendation Letter {name}: resend failed",
            message=frappe.get_traceback(),
        )
    return {"expires_on": doc.token_expires_on, "sent_to": sent_to}
