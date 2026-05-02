# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Graduation Request controller.

Lifecycle (mirrors ADR 016 — Course Enrollment Individual):
    Draft → Awaiting Payment → Approved
                            ↓
                        Cancelled

Sales Invoice generation runs in `on_submit` (regardless of which
post-submit state the workflow lands in). The `gr_si` flag is the
idempotency guard — re-saves never re-bill.
"""

import frappe
import erpnext
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today


class GraduationRequest(Document):
    def validate(self):
        self._fetch_program_and_dates()
        self._guard_unique_active_request()

    def before_submit(self):
        program = frappe.get_cached_doc("Program", self.program)
        if not program.students_can_request_graduation:
            frappe.throw(
                _("Program {0} does not allow Graduation Requests.").format(
                    self.program
                )
            )
        if not program.graduation_request_trigger:
            frappe.throw(
                _("Program {0} has no graduation_request_trigger configured.").format(
                    self.program
                )
            )
        candidate = frappe.db.get_value(
            "Program Enrollment", self.program_enrollment, "grad_candidate"
        )
        if not candidate:
            frappe.throw(
                _(
                    "Student is not yet a graduation candidate on enrollment {0}. "
                    "Wait until the program's trigger condition is met."
                ).format(self.program_enrollment)
            )

    def on_submit(self):
        if self.gr_si:
            return
        if self.is_free:
            self.db_set("gr_si", 1, update_modified=False)
            return
        self._generate_sales_invoices()
        self.db_set("gr_si", 1, update_modified=False)

    def on_cancel(self):
        """Stamp workflow_state and cancel any unpaid linked Sales Invoices.

        When the cancellation cascades from a PE withdrawal, the fee is
        non-refundable per the per-program policy — `flags.cascade_from_pe_withdrawal`
        is checked to skip SI cancellation in that path.
        """
        frappe.db.set_value(
            self.doctype,
            self.name,
            "workflow_state",
            "Cancelled",
            update_modified=False,
        )

        if getattr(self.flags, "cascade_from_pe_withdrawal", False):
            return

        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "custom_graduation_request": self.name,
                "docstatus": 1,
                "is_return": 0,
            },
            fields=["name", "outstanding_amount", "grand_total"],
        )
        for inv in invoices:
            # Only cancel if fully unpaid; partial payments leave the SI alone
            # so registrar can decide on refund handling explicitly.
            if flt(inv.outstanding_amount) == flt(inv.grand_total):
                si = frappe.get_doc("Sales Invoice", inv.name)
                si.flags.ignore_permissions = True
                si.cancel()

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    def _fetch_program_and_dates(self):
        """Backfill program / expected_graduation_date / is_free / student
        from PE in case the form was submitted without triggering fetch_from
        (programmatic insert from the audit endpoint)."""
        if not self.program_enrollment:
            return
        pe = frappe.db.get_value(
            "Program Enrollment",
            self.program_enrollment,
            ["student", "program", "expected_graduation_date"],
            as_dict=True,
        )
        if not pe:
            frappe.throw(
                _("Program Enrollment {0} not found.").format(self.program_enrollment)
            )
        self.student = self.student or pe.student
        self.program = self.program or pe.program
        self.expected_graduation_date = (
            self.expected_graduation_date or pe.expected_graduation_date
        )
        if self.program:
            self.is_free = frappe.db.get_value("Program", self.program, "is_free") or 0

    def _guard_unique_active_request(self):
        """Block duplicate active requests on the same enrollment."""
        existing = frappe.get_all(
            "Graduation Request",
            filters={
                "program_enrollment": self.program_enrollment,
                "docstatus": ("!=", 2),
                "name": ("!=", self.name or ""),
                "workflow_state": (
                    "in",
                    (
                        "Draft",
                        "Awaiting Payment",
                        "Academic Review",
                        "Financial Review",
                        "Approved",
                    ),
                ),
            },
            pluck="name",
        )
        if existing:
            frappe.throw(
                _(
                    "An active Graduation Request already exists for this enrollment: {0}."
                ).format(existing[0])
            )

    # ------------------------------------------------------------------
    # Sales Invoice generation (mirrors get_inv_data_ce in CEI)
    # ------------------------------------------------------------------

    def _generate_sales_invoices(self):
        """Generate one Sales Invoice per payer configured for this PE
        with `pep_event = 'Graduation Request'`. Mirrors the CEI pattern.

        Resolved progressively so the error message points at the actual
        missing piece (payer row, fee category, item, item price,
        customer group price list) instead of a blanket "not configured".
        """
        payer_rows = frappe.db.sql(
            """SELECT pep.name AS pep_name,
                      pep.fee_category,
                      pep.payer AS customer,
                      pfc.pf_custgroup,
                      pep.pay_percent,
                      pep.payterm_payer
               FROM `tabPayers Fee Category PE` pfc
               INNER JOIN `tabpgm_enroll_payers` pep ON pep.parent = pfc.name
               WHERE pfc.pf_pe = %s
                 AND pep.pep_event = 'Graduation Request'""",
            (self.program_enrollment,),
            as_dict=True,
        )

        if not payer_rows:
            frappe.throw(
                _(
                    "No 'Graduation Request' payer is configured on Program Enrollment {0}. "
                    "Open the enrollment's Payers Fee Category section and add a payer row "
                    "with Event = 'Graduation Request' before submitting."
                ).format(self.program_enrollment)
            )

        company = frappe.defaults.get_defaults().company
        currency = erpnext.get_company_currency(company)
        receivable_account = frappe.db.get_single_value(
            "Seminary Settings", "receivable_account"
        )
        submit_invoice = frappe.db.get_single_value(
            "Seminary Settings", "auto_submit_sales_invoice"
        )
        cost_center = frappe.db.get_single_value("Seminary Settings", "cost_center")
        sch_cost_center = frappe.db.get_single_value(
            "Seminary Settings", "scholarship_cc"
        )
        sch_customer = frappe.db.get_single_value(
            "Seminary Settings", "scholarship_cust"
        )

        income_account_row = frappe.db.sql(
            "SELECT default_income_account FROM `tabCompany` WHERE name=%s", company
        )
        income_account = income_account_row[0][0] if income_account_row else None

        for payer in payer_rows:
            item, price_list, price_list_rate = self._resolve_pricing(payer)
            qty = flt(payer.pay_percent) / 100.0
            grand_total = qty * flt(price_list_rate)
            row_cost_center = (
                sch_cost_center if payer.customer == sch_customer else cost_center
            )
            discount = 100 if payer.customer == sch_customer else 0
            summary = _("Graduation Request: {0}").format(self.name)

            sales_invoice = frappe.get_doc(
                {
                    "doctype": "Sales Invoice",
                    "naming_series": "ACC-SINV-.YYYY.-",
                    "posting_date": today(),
                    "company": company,
                    "currency": currency,
                    "debit_to": receivable_account,
                    "income_account": income_account,
                    "conversion_rate": 1,
                    "customer": payer.customer,
                    "selling_price_list": price_list,
                    "base_grand_total": grand_total,
                    "payment_terms_template": payer.payterm_payer,
                    "remarks": summary,
                    "items": [
                        {
                            "doctype": "Sales Invoice Item",
                            "item_code": item,
                            "qty": qty,
                            "rate": 0,
                            "description": summary,
                            "income_account": income_account,
                            "cost_center": row_cost_center,
                            "base_rate": 0,
                            "price_list_rate": price_list_rate,
                        }
                    ],
                    "cost_center": row_cost_center,
                    "custom_student": self.student,
                    "custom_graduation_request": self.name,
                    "additional_discount_percentage": discount,
                    "seminary_summary": summary,
                }
            )
            # Authorization was already enforced at the endpoint and in
            # before_submit; the SI is a trusted side effect (the Student
            # role doesn't hold Sales Invoice permissions).
            sales_invoice.flags.ignore_permissions = True
            sales_invoice.insert(ignore_permissions=True)
            if submit_invoice == 1:
                sales_invoice.submit()

    def _resolve_pricing(self, payer):
        """Look up item + price list rate for one payer row. Each lookup
        throws a specific error if the supporting data is missing."""
        item = frappe.db.get_value("Fee Category", payer.fee_category, "item")
        if not item:
            frappe.throw(
                _(
                    "Fee Category {0} has no Item set; cannot generate an invoice."
                ).format(payer.fee_category)
            )

        price_list = frappe.db.get_value(
            "Customer Group", payer.pf_custgroup, "default_price_list"
        )
        if not price_list:
            frappe.throw(
                _(
                    "Customer Group {0} has no default Price List; cannot price the "
                    "Graduation Request fee."
                ).format(payer.pf_custgroup)
            )

        price_list_rate = frappe.db.get_value(
            "Item Price",
            {"item_code": item, "price_list": price_list},
            "price_list_rate",
        )
        if price_list_rate is None:
            frappe.throw(
                _(
                    "No Item Price found for Item {0} on Price List {1}. "
                    "Add an Item Price before submitting the Graduation Request."
                ).format(item, price_list)
            )

        return item, price_list, price_list_rate
