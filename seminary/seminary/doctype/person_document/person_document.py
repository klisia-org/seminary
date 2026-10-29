# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class PersonDocument(Document):
    """A file a person uploaded and whether the school accepted it (ADR 091 §6).

    It belongs to the Person, not to an enrollment: one accepted diploma
    satisfies every requirement that asks for one."""

    def validate(self):
        from seminary.seminary import requirements

        if not self.submitted_on:
            self.submitted_on = now_datetime()
        if self.is_new() and self.file:
            requirements.check_extension(
                self.document_type, self.file.rsplit("/", 1)[-1]
            )
        if (
            self.is_new()
            and self.status == "Submitted"
            and not frappe.db.get_value(
                "Document Type", self.document_type, "needs_review"
            )
        ):
            # Without review, an upload counts as soon as it arrives.
            self._mark_accepted(frappe.session.user)
        elif (
            self.is_new()
            and frappe.flags.in_import
            and self.status == "Accepted"
            and not self.reviewed_on
        ):
            # Accepted by the school's previous system (ADR 094 §4).
            self._mark_accepted(frappe.session.user, self.valid_until)

    def on_update(self):
        self._recompute()

    def after_delete(self):
        self._recompute()

    def _recompute(self):
        from seminary.seminary import requirements

        requirements.recompute_documents(self.person, self.document_type)

    def accept(self, by=None, valid_until=None):
        if self.status == "Accepted":
            return
        self._mark_accepted(by or frappe.session.user, valid_until)
        self.flags.ignore_permissions = True
        self.save()

    def _mark_accepted(self, by, valid_until=None):
        from seminary.seminary import requirements

        self.status = "Accepted"
        self.reviewed_by = by
        self.reviewed_on = now_datetime()
        self.rejection_reason = None
        # An imported document was valid from when it was submitted (ADR 094 §4).
        on = self.submitted_on if frappe.flags.in_import else None
        self.valid_until = valid_until or requirements.accepted_valid_until(
            self.document_type, on=on
        )

    def reject(self, reason, by=None):
        from seminary.seminary import requirements

        reason = (reason or "").strip()
        if not reason:
            frappe.throw(_("Say why the document cannot be accepted."))
        if self.status not in ("Submitted", "Accepted"):
            frappe.throw(_("Only a submitted or accepted document can be rejected."))
        self.status = "Rejected"
        self.reviewed_by = by or frappe.session.user
        self.reviewed_on = now_datetime()
        self.rejection_reason = reason
        self.flags.ignore_permissions = True
        self.save()
        requirements.notify_rejected(self)
