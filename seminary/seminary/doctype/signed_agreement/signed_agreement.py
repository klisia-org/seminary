# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SignedAgreement(Document):
    """An agreement as signed, with its evidence (ADR 091 §8). Made only by
    `requirements.sign`; never edited after submit, except by countersigning."""

    def before_insert(self):
        if not self.flags.ignore_permissions:
            frappe.throw(_("Agreements are signed from the portal."))

    def on_submit(self):
        self._recompute()

    def on_update_after_submit(self):
        self._recompute()

    def on_cancel(self):
        self._recompute()

    def _recompute(self):
        from seminary.seminary import requirements

        requirements.recompute(self.person_requirement)
