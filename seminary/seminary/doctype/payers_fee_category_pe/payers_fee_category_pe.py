# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PayersFeeCategoryPE(Document):
    def validate(self):
        if self.is_new():
            return
        before = self.get_doc_before_save()
        if not before:
            return
        if self._payer_rows_changed(before) and not (self.change_reason or "").strip():
            frappe.throw(
                _(
                    "Payer shares changed. Enter a Change reason before saving "
                    "(e.g. who requested the change and why)."
                )
            )

    def on_update(self):
        # Clear the reason after it's captured in the Version log, so the next
        # edit forces a fresh reason rather than re-using a stale one.
        if self.change_reason:
            frappe.db.set_value(
                self.doctype,
                self.name,
                "change_reason",
                "",
                update_modified=False,
            )

    def _payer_rows_changed(self, before):
        def sig(doc):
            return sorted(
                (r.fee_category, r.payer, float(r.pay_percent or 0), r.pep_event)
                for r in (doc.pf_payers or [])
            )

        return sig(self) != sig(before)

    @frappe.whitelist()
    def get_inv_data_pe(self):
        """Raise this enrollment's Program-Enrollment Sales Invoices via the
        financial backend. The billing engine lives in the oikonomos bridge;
        seminary keeps this whitelisted entry point for the desk button. With no
        backend installed this is a no-op (returns zero counts)."""
        from seminary.seminary.financial.backend import get_financial_backend

        return get_financial_backend().generate_program_enrollment_invoices(self)

    @frappe.whitelist()
    # Method to check if the sum of the percentages is equal to 100
    def check_percentages(self):
        pay_data = []
        pay_data = frappe.db.sql(
            """select pep.fee_category, sum(pep.pay_percent) as percentage
		from `tabpgm_enroll_payers` pep
		where pep.parent = %s
		group by pep.fee_category
		having percentage != 100""",
            self.name,
            as_list=1,
        )

        if pay_data:
            frappe.throw(
                "The sum of the percentages paid for a Fee Category is not equal to 100"
            )
