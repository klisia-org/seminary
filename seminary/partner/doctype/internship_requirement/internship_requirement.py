# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from seminary.partner import internship

_PARTIES = ("student", "seminary", "partner")
_SIGNING = ("seminary", "partner")


class InternshipRequirement(Document):
    def before_save(self):
        self._stamp_submissions()
        self._stamp_signoffs()
        self._recompute_status()

    def on_update(self):
        # A completed hour-log requirement releases the placement's submittable
        # hours toward the total.
        if self.is_hour_log and self.internship_placement:
            internship.recompute_placement_hours(self.internship_placement)

    def _has_submission(self, party):
        return bool(
            self.get(f"{party}_attachment")
            or (self.get(f"{party}_submission_value") or "").strip()
            or self.get(f"{party}_acknowledged")
        )

    def _stamp_submissions(self):
        for party in _PARTIES:
            if self._has_submission(party) and not self.get(f"{party}_submitted_on"):
                self.set(f"{party}_submitted_on", now_datetime())
                self.set(f"{party}_submitted_by", frappe.session.user)

    def _stamp_signoffs(self):
        for party in _SIGNING:
            if self.get(f"{party}_signoff"):
                if not self.get(f"{party}_signed_on"):
                    self.set(f"{party}_signed_on", now_datetime())
                    self.set(f"{party}_signed_by", frappe.session.user)
            else:
                self.set(f"{party}_signed_on", None)
                self.set(f"{party}_signed_by", None)

    def _recompute_status(self):
        """Drive status from submissions and required sign-offs; never override a
        manual Waiver. Completion requires every party flagged to sign to have
        signed (when none sign, completion is a manual status change)."""
        if self.status == "Waived":
            return

        required = [p for p in _SIGNING if self.get(f"{p}_signs_complete")]
        all_signed = all(self.get(f"{p}_signoff") for p in required)
        submitted = any(self.get(f"{p}_submitted_on") for p in _PARTIES)

        if required and all_signed:
            self.status = "Completed"
        elif self.status == "Completed":
            # A required sign-off was withdrawn — fall back to in-progress.
            if required and not all_signed:
                self.status = "Submitted" if submitted else "In Progress"
        elif submitted and self.status == "Not Started":
            self.status = "Submitted" if not required else "In Progress"

        if self.status == "Completed" and not self.completed_on:
            self.completed_on = today()
        if self.status != "Completed":
            self.completed_on = None
