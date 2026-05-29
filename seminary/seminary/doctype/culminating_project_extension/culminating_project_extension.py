# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary.billing import create_extension_invoices


class CulminatingProjectExtension(Document):
    def on_submit(self):
        self._bill_extension()

    def on_cancel(self):
        self._cancel_invoices()

    def _bill_extension(self):
        """Charge the extension fee to the enrollment's payers. The fee is whatever
        Fee Category carries the 'Culminating Project Extension' trigger — no fee or
        quantity is chosen here. Billing only: no Program Enrollment Course row is
        created, so credits/grade/GPA/transcript are untouched (ADR 024).
        Idempotent via `invoiced`."""
        if self.invoiced:
            return
        if not self.program_enrollment:
            self.program_enrollment = frappe.db.get_value(
                "Culminating Project", self.culminating_project, "program_enrollment"
            )
        summary = _("Culminating Project Extension: {0} ({1})").format(
            self.culminating_project, self.academic_term
        )
        invoices = create_extension_invoices(
            self.program_enrollment,
            self.student,
            summary,
        )
        self.db_set("sales_invoices", "\n".join(invoices))
        self.db_set("invoiced", 1)

    def _cancel_invoices(self):
        """Cancel the Sales Invoices this extension created."""
        for name in (self.sales_invoices or "").splitlines():
            name = name.strip()
            if not name:
                continue
            if frappe.db.get_value("Sales Invoice", name, "docstatus") != 1:
                continue
            invoice = frappe.get_doc("Sales Invoice", name)
            invoice.flags.ignore_permissions = True
            invoice.cancel()
