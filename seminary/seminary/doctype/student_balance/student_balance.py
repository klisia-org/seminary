# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, nowdate
from frappe.model.document import Document


class StudentBalance(Document):
    def validate(self):
        self.validate_single_open()
        self.validate_no_duplicate_invoices()
        self.recalculate_totals()

    def validate_single_open(self):
        if not self.is_open:
            return
        existing = frappe.db.get_value(
            "Student Balance",
            {"student": self.student, "is_open": 1, "name": ["!=", self.name]},
            "name",
        )
        if existing:
            frappe.throw(
                _("Student {0} already has an open balance: {1}").format(
                    self.student, existing
                )
            )

    def validate_no_duplicate_invoices(self):
        seen = set()
        for row in self.invoices:
            if row.sales_invoice in seen:
                frappe.throw(
                    _("Duplicate invoice {0} in Student Balance").format(
                        row.sales_invoice
                    )
                )
            seen.add(row.sales_invoice)

    def recalculate_totals(self):
        total_invoiced = 0
        total_credits = 0
        net_outstanding = 0

        for row in self.invoices:
            if row.is_return:
                total_credits += flt(row.grand_total)
            else:
                total_invoiced += flt(row.grand_total)
            net_outstanding += flt(row.outstanding_amount)

        self.total_invoiced = total_invoiced
        self.total_credits = total_credits
        self.net_outstanding = net_outstanding
        self.total_paid = total_invoiced + total_credits - net_outstanding

    def refresh_outstanding(self):
        """Re-read outstanding_amount from each child Sales Invoice."""
        for row in self.invoices:
            outstanding = frappe.db.get_value(
                "Sales Invoice", row.sales_invoice, "outstanding_amount"
            )
            if outstanding is not None:
                row.outstanding_amount = flt(outstanding)

        self.recalculate_totals()
        self.save()

        if self.net_outstanding <= 0:
            self.close_and_rotate()

    def close_and_rotate(self, status="Closed"):
        """Close this balance and create a new open one.

        Carries forward any child rows with outstanding_amount > 0.
        """
        self.is_open = 0
        self.status = status
        self.save()

        # Collect rows to carry forward — include both unpaid invoices
        # and unsettled credit notes (outstanding != 0)
        carry_forward = []
        for row in self.invoices:
            if flt(row.outstanding_amount) != 0:
                carry_forward.append(
                    {
                        "sales_invoice": row.sales_invoice,
                        "posting_date": row.posting_date,
                        "due_date": row.due_date,
                        "grand_total": row.grand_total,
                        "outstanding_amount": row.outstanding_amount,
                        "allocated_amount": 0,
                        "is_return": row.is_return,
                        "return_against": row.return_against,
                    }
                )

        new_balance = frappe.new_doc("Student Balance")
        new_balance.update(
            {
                "student": self.student,
                "customer": self.customer,
                "company": self.company,
                "currency": self.currency,
                "posting_date": nowdate(),
                "is_open": 1,
                "status": "Open",
                "previous_balance": self.name,
            }
        )
        for row_data in carry_forward:
            new_balance.append("invoices", row_data)

        new_balance.insert(ignore_permissions=True)
        return new_balance

    def on_payment_authorized(self, payment_status):
        """Called by SeminaryPaymentRequest override after gateway success."""
        if payment_status not in ("Authorized", "Completed"):
            return

        # Use the Payment Request's grand_total as the source of truth
        # for the amount actually paid at the gateway.
        pr_amount = (
            flt(
                frappe.db.get_value(
                    "Payment Request", self.payment_request, "grand_total"
                )
            )
            if self.payment_request
            else flt(self.net_outstanding)
        )

        pe = self.create_payment_entry(payment_account=None, amount=pr_amount)

        # Refresh outstanding from the now-updated invoices
        self.refresh_outstanding()

        # close_and_rotate was already called by refresh_outstanding if
        # net_outstanding hit 0.  If it's still open (partial payment),
        # close it with "Partially Paid".
        if self.is_open:
            self.close_and_rotate(status="Partially Paid")

        return "/seminary/fees?payment=success"

    def create_payment_entry(
        self, payment_account=None, amount=None, mode_of_payment=None
    ):
        """Create a Payment Entry allocating across child invoices by due date."""
        from erpnext.accounts.party import get_party_account

        if not amount:
            amount = self.net_outstanding

        if not payment_account:
            settings = frappe.get_cached_doc("Seminary Settings")
            gateway_account_data = frappe.db.get_value(
                "Payment Gateway Account",
                {"payment_gateway": settings.payment_gateway},
                ["name", "payment_account"],
                as_dict=True,
            )
            payment_account = (
                gateway_account_data.payment_account if gateway_account_data else None
            )

        if not payment_account:
            frappe.throw(_("No payment account configured."))

        from erpnext.accounts.utils import get_account_currency

        paid_to = payment_account

        party_account = get_party_account("Customer", self.customer, self.company)

        # Pre-populate account currency and type so that set_missing_values()
        # skips the call to get_account_details() which requires Payment Entry
        # read permission that students don't have.
        paid_from_currency = get_account_currency(party_account)
        paid_from_type = frappe.get_cached_value(
            "Account", party_account, "account_type"
        )
        paid_to_currency = get_account_currency(paid_to)
        paid_to_type = frappe.get_cached_value("Account", paid_to, "account_type")

        pe = frappe.new_doc("Payment Entry")
        pe.update(
            {
                "payment_type": "Receive",
                "party_type": "Customer",
                "party": self.customer,
                "company": self.company,
                "paid_from": party_account,
                "paid_from_account_currency": paid_from_currency,
                "paid_from_account_type": paid_from_type,
                "paid_to": paid_to,
                "paid_to_account_currency": paid_to_currency,
                "paid_to_account_type": paid_to_type,
                "paid_amount": amount,
                "received_amount": amount,
                "mode_of_payment": mode_of_payment,
                "reference_no": self.name,
                "reference_date": nowdate(),
                "remarks": _("Payment against Student Balance {0}").format(self.name),
            }
        )

        # Reset allocated_amount on all rows before allocating
        for row in self.invoices:
            row.allocated_amount = 0

        # Phase 1: apply credit notes (negative outstanding) first.
        # These settle the credit note and reduce the cash needed.
        credits_applied = 0
        for row in self.invoices:
            if row.is_return and flt(row.outstanding_amount) < 0:
                credit_alloc = flt(row.outstanding_amount)  # negative
                row.allocated_amount = credit_alloc
                pe.append(
                    "references",
                    {
                        "reference_doctype": "Sales Invoice",
                        "reference_name": row.sales_invoice,
                        "total_amount": flt(row.grand_total),
                        "outstanding_amount": flt(row.outstanding_amount),
                        "allocated_amount": credit_alloc,
                    },
                )
                credits_applied += credit_alloc  # accumulates negative

        # Phase 2: allocate cash (amount) plus the absolute value of credits
        # to unpaid invoices by due date. The gross allocated to unpaid
        # = cash + |credits|.
        remaining = flt(amount) + abs(credits_applied)
        sorted_rows = sorted(self.invoices, key=lambda r: r.due_date or "9999-12-31")
        for row in sorted_rows:
            if row.is_return or flt(row.outstanding_amount) <= 0:
                continue
            alloc = min(flt(row.outstanding_amount), remaining)
            if alloc <= 0:
                continue
            row.allocated_amount = alloc
            pe.append(
                "references",
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": row.sales_invoice,
                    "total_amount": flt(row.grand_total),
                    "outstanding_amount": flt(row.outstanding_amount),
                    "allocated_amount": alloc,
                },
            )
            remaining -= alloc
            if remaining <= 0:
                break

        self.save(ignore_permissions=True)

        pe.setup_party_account_field()
        pe.set_missing_values()
        pe.set_missing_ref_details()
        pe.insert(ignore_permissions=True)
        pe.submit()

        return pe


# ---------------------------------------------------------------------------
# Whitelisted methods for Desk
# ---------------------------------------------------------------------------


@frappe.whitelist()
def refresh_from_sales_invoices(student_balance):
    """Rebuild the child table from current Sales Invoice state.

    Clears all child rows and re-queries Sales Invoices for the student
    where customer = balance's customer, including credit notes. Used to
    recover from data drift.
    """
    sb = frappe.get_doc("Student Balance", student_balance)

    if not sb.is_open:
        frappe.throw(_("Can only refresh an open Student Balance."))

    if not sb.customer:
        frappe.throw(_("Student Balance has no customer set."))

    # Get all submitted SIs for this student with matching customer
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "custom_student": sb.student,
            "customer": sb.customer,
            "docstatus": 1,
        },
        fields=[
            "name",
            "posting_date",
            "due_date",
            "grand_total",
            "outstanding_amount",
            "is_return",
            "return_against",
        ],
        order_by="posting_date asc",
    )

    # Only keep rows with outstanding != 0 (unpaid or unsettled credits)
    sb.invoices = []
    for inv in invoices:
        if flt(inv.outstanding_amount) == 0:
            continue
        sb.append(
            "invoices",
            {
                "sales_invoice": inv.name,
                "posting_date": inv.posting_date,
                "due_date": inv.due_date,
                "grand_total": inv.grand_total,
                "outstanding_amount": inv.outstanding_amount,
                "allocated_amount": 0,
                "is_return": inv.is_return,
                "return_against": inv.return_against,
            },
        )

    sb.recalculate_totals()
    sb.save(ignore_permissions=True)

    # Auto-close if nothing left to pay
    if flt(sb.net_outstanding) <= 0 and len(sb.invoices) == 0:
        sb.close_and_rotate()

    return {"invoices": len(sb.invoices), "net_outstanding": sb.net_outstanding}


@frappe.whitelist()
def record_payment(student_balance, amount, mode_of_payment=None):
    """Record a payment against a Student Balance from Desk.

    Creates a Payment Entry, refreshes outstanding, and closes/rotates the
    balance as needed.
    """
    sb = frappe.get_doc("Student Balance", student_balance)

    if not sb.is_open:
        frappe.throw(_("This Student Balance is already closed."))

    amount = flt(amount)
    if amount <= 0 or amount > flt(sb.net_outstanding):
        frappe.throw(_("Amount must be between 0 and {0}.").format(sb.net_outstanding))

    # Determine payment account from mode_of_payment if provided
    payment_account = None
    if mode_of_payment:
        payment_account = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": mode_of_payment, "company": sb.company},
            "default_account",
        )

    pe = sb.create_payment_entry(
        payment_account=payment_account,
        amount=amount,
        mode_of_payment=mode_of_payment,
    )

    sb.refresh_outstanding()

    # close_and_rotate is called by refresh_outstanding if net_outstanding = 0.
    # If still open (partial), close with "Partially Paid".
    if sb.is_open:
        sb.close_and_rotate(status="Partially Paid")

    return {"payment_entry": pe.name}


# ---------------------------------------------------------------------------
# Module-level hook functions
# ---------------------------------------------------------------------------


def create_student_balance(doc, method=None):
    """Hook: Student.after_insert — create the first open Student Balance."""
    settings = frappe.get_cached_doc("Seminary Settings")
    company = settings.get("company") or frappe.defaults.get_defaults().get("company")
    if not company:
        return

    currency = frappe.db.get_value("Company", company, "default_currency")

    sb = frappe.new_doc("Student Balance")
    sb.update(
        {
            "student": doc.name,
            "customer": doc.get("customer"),
            "company": company,
            "currency": currency,
            "posting_date": nowdate(),
            "is_open": 1,
            "status": "Open",
        }
    )
    sb.insert(ignore_permissions=True)


def add_invoice_to_student_balance(doc, method=None):
    """Hook: Sales Invoice.on_submit — append invoice to student's open balance.

    Only adds invoices where the customer is the student's own customer.
    Church/scholarship invoices are not part of the student's personal balance.
    """
    student = doc.get("custom_student")
    if not student:
        return

    student_customer = frappe.db.get_value("Student", student, "customer")
    if not student_customer or doc.customer != student_customer:
        return

    sb_name = frappe.db.get_value(
        "Student Balance", {"student": student, "is_open": 1}, "name"
    )
    if not sb_name:
        return

    sb = frappe.get_doc("Student Balance", sb_name)

    # Skip if already present
    existing_invoices = {row.sales_invoice for row in sb.invoices}
    if doc.name in existing_invoices:
        return

    sb.append(
        "invoices",
        {
            "sales_invoice": doc.name,
            "posting_date": doc.posting_date,
            "due_date": doc.due_date,
            "grand_total": doc.grand_total,
            "outstanding_amount": doc.outstanding_amount,
            "allocated_amount": 0,
            "is_return": doc.is_return,
            "return_against": doc.return_against,
        },
    )
    sb.recalculate_totals()
    sb.save(ignore_permissions=True)


def refresh_balance_on_invoice_update(doc, method=None):
    """Hook: Sales Invoice.on_update_after_submit — refresh outstanding amounts.

    Handles credit note cascading: when a credit note is submitted, it reduces
    the original invoice's outstanding. We refresh the balance to reflect this.
    """
    student = doc.get("custom_student")
    if not student:
        # For credit notes, get student from the original invoice
        if doc.is_return and doc.return_against:
            student = frappe.db.get_value(
                "Sales Invoice", doc.return_against, "custom_student"
            )
        if not student:
            return

    # Only act on invoices billed to the student's own customer
    student_customer = frappe.db.get_value("Student", student, "customer")
    if not student_customer or doc.customer != student_customer:
        return

    sb_name = frappe.db.get_value(
        "Student Balance", {"student": student, "is_open": 1}, "name"
    )
    if not sb_name:
        return

    sb = frappe.get_doc("Student Balance", sb_name)

    # If this is a new credit note, append it
    if doc.is_return:
        existing_invoices = {row.sales_invoice for row in sb.invoices}
        if doc.name not in existing_invoices:
            sb.append(
                "invoices",
                {
                    "sales_invoice": doc.name,
                    "posting_date": doc.posting_date,
                    "due_date": doc.due_date,
                    "grand_total": doc.grand_total,
                    "outstanding_amount": doc.outstanding_amount,
                    "allocated_amount": 0,
                    "is_return": 1,
                    "return_against": doc.return_against,
                },
            )

    sb.refresh_outstanding()


def remove_cancelled_invoice_from_balance(doc, method=None):
    """Hook: Sales Invoice.on_cancel — remove cancelled SI from Student Balance."""
    student = doc.get("custom_student")
    if not student:
        if doc.is_return and doc.return_against:
            student = frappe.db.get_value(
                "Sales Invoice", doc.return_against, "custom_student"
            )
        if not student:
            return

    sb_name = frappe.db.get_value(
        "Student Balance", {"student": student, "is_open": 1}, "name"
    )
    if not sb_name:
        return

    sb = frappe.get_doc("Student Balance", sb_name)

    # Remove the cancelled invoice row
    sb.invoices = [row for row in sb.invoices if row.sales_invoice != doc.name]

    sb.recalculate_totals()
    sb.save(ignore_permissions=True)

    if sb.net_outstanding <= 0:
        sb.close_and_rotate()
