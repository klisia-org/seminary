# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Temporary in-seminary ERPNext-backed financial backend (Phase 0).

This is the real implementation of `FinancialBackend` while the refactor is in
flight. It still lives in seminary and is registered from seminary's own
hooks.py (`seminary_financial_backend`). In a later phase its body moves to the
`oikonomos` app and this module — together with seminary's temporary
registration — is deleted.

It is the ONLY place in seminary (besides the modules being migrated) that reads
ERPNext doctypes for these flows; concentrating the SQL here is the point of the
seam.
"""

import frappe
from frappe.utils import flt

from seminary.seminary.financial.backend import FinancialBackend, PaymentAggregate


class SeminaryErpnextBackend(FinancialBackend):
    def has_financials(self) -> bool:
        return True

    def payment_status_for_cei(self, cei_name: str) -> PaymentAggregate:
        return _aggregate_invoices("custom_cei", cei_name)

    def payment_status_for_graduation(self, gr_name: str) -> PaymentAggregate:
        return _aggregate_invoices("custom_graduation_request", gr_name)

    def generate_enrollment_invoice(self, cei_doc) -> None:
        # The billing body still lives on the CEI controller (get_inv_data_ce ->
        # billing.build_and_create_invoice). A later phase relocates that body
        # here / into oikonomos.
        cei_doc.get_inv_data_ce()


def _aggregate_invoices(link_field: str, link_value: str) -> PaymentAggregate:
    """Sum submitted, non-return Sales Invoices linked via `link_field`.

    `link_field` is a fixed identifier chosen by the caller (never user input),
    so interpolating it into the query is safe.
    """
    rows = frappe.db.sql(
        """SELECT COALESCE(SUM(grand_total), 0) AS invoiced,
                  COALESCE(SUM(grand_total - outstanding_amount), 0) AS paid,
                  COUNT(*) AS si_count
           FROM `tabSales Invoice`
           WHERE {field} = %s
             AND docstatus = 1
             AND is_return = 0""".format(
            field=link_field
        ),
        (link_value,),
        as_dict=True,
    )
    invoiced = flt(rows[0].invoiced) if rows else 0.0
    paid = flt(rows[0].paid) if rows else 0.0
    si_count = int(rows[0].si_count) if rows else 0

    if invoiced > 0:
        paid_percent = paid / invoiced * 100.0
    elif si_count > 0:
        # All linked invoices are $0 (e.g. full scholarship) — vacuously paid.
        paid_percent = 100.0
    else:
        paid_percent = 0.0

    return PaymentAggregate(
        invoiced=invoiced, paid=paid, si_count=si_count, paid_percent=paid_percent
    )
