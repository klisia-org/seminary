# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from erpnext.accounts.doctype.payment_request.payment_request import (
    PaymentRequest,
    _get_payment_gateway_controller,
)


class SeminaryPaymentRequest(PaymentRequest):
    def get_payment_url(self):
        if self.reference_doctype == "Student Balance":
            data = frappe.db.get_value(
                "Student Balance",
                self.reference_name,
                ["company", "customer"],
                as_dict=True,
            )
            customer_name = frappe.db.get_value(
                "Customer", data.customer, "customer_name"
            )

            controller = _get_payment_gateway_controller(self.payment_gateway)
            controller.validate_transaction_currency(self.currency)

            if hasattr(controller, "validate_minimum_transaction_amount"):
                controller.validate_minimum_transaction_amount(
                    self.currency, self.grand_total
                )

            return controller.get_payment_url(
                **{
                    "amount": flt(self.grand_total, self.precision("grand_total")),
                    "title": data.company,
                    "description": self.subject,
                    "reference_doctype": "Payment Request",
                    "reference_docname": self.name,
                    "payer_email": self.email_to or frappe.session.user,
                    "payer_name": customer_name,
                    "order_id": self.name,
                    "currency": self.currency,
                    "payment_gateway": self.payment_gateway,
                }
            )
        return super().get_payment_url()

    def on_payment_authorized(self, payment_status):
        if self.reference_doctype == "Student Balance":
            if payment_status in ("Authorized", "Completed"):
                sb = frappe.get_doc("Student Balance", self.reference_name)
                redirect = sb.on_payment_authorized(payment_status)
                self.db_set({"status": "Paid", "outstanding_amount": 0})
                return redirect
        # For non-Student Balance references, fall through to default behavior

    def create_payment_entry(self, submit=True):
        if self.reference_doctype == "Student Balance":
            sb = frappe.get_doc("Student Balance", self.reference_name)
            return sb.create_payment_entry(
                payment_account=self.payment_account,
                amount=self.outstanding_amount,
            )
        return super().create_payment_entry(submit=submit)
