# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The financial-backend interface and its null implementation.

Seminary never imports ERPNext or oikonomos. When it needs a financial fact
("how much of this enrollment is paid?") or a financial side effect ("raise the
enrollment invoice"), it goes through `get_financial_backend()`, which resolves
the implementation registered under the `seminary_financial_backend` hook. With
no financial app installed the resolver returns `NullFinancialBackend`, whose
answers make academic flows behave as if everything is free / fully paid — the
supported Frappe-only deployment.

The interface deliberately exposes *plain data* (no ERPNext doctypes leak across
the seam) so it can later be promoted to a whitelisted/HTTP API unchanged.

Phase 0 wires only the methods with live call sites today: payment-status reads
for CEI / Graduation Request and enrollment-invoice generation. The interface
will grow (outstanding_for_student, payers_for_enrollment, fees_for_program,
application/extension invoices, refunds) as later phases move their call sites.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import frappe


@dataclass
class PaymentAggregate:
    """A financial snapshot the academic side can reason about without knowing
    anything about Sales Invoices.

    `paid_percent` is carried explicitly (not derived) so the null backend can
    report "fully paid" (100.0) while reporting zero invoiced/paid — i.e. there
    is no billing system, so there is nothing to owe.
    """

    invoiced: float = 0.0
    paid: float = 0.0
    si_count: int = 0
    paid_percent: float = 0.0


class FinancialBackend(ABC):
    """Contract seminary depends on. Implemented by oikonomos (ERPNext-backed);
    falls back to `NullFinancialBackend` when no financial app is installed."""

    @abstractmethod
    def has_financials(self) -> bool:
        """True when a real billing backend is present. Academic code can use
        this to hide payment UI / workflow states."""

    @abstractmethod
    def payment_status_for_cei(self, cei_name: str) -> PaymentAggregate:
        """Aggregate of submitted invoices linked to a Course Enrollment
        Individual."""

    @abstractmethod
    def payment_status_for_graduation(self, gr_name: str) -> PaymentAggregate:
        """Aggregate of submitted invoices linked to a Graduation Request."""

    @abstractmethod
    def generate_enrollment_invoice(self, cei_doc) -> int:
        """Raise the Sales Invoice(s) for a non-free Course Enrollment Individual
        and return how many payer lines were billed. Idempotency on the CEI
        (`cei_si`) is handled by the caller, which must only flag the enrollment
        as invoiced when the return is non-zero — a 0 means nothing was billable
        (no fee wired up / missing price), not 'successfully free'."""

    @abstractmethod
    def generate_program_enrollment_invoices(self, pfc_doc) -> dict:
        """Raise the Program-Enrollment Sales Invoices for a Payers Fee Category
        PE. Returns a {"created", "skipped", "failed"} count dict."""

    @abstractmethod
    def process_withdrawal_refunds(self, withdrawal_doc) -> None:
        """Generate credit notes (and any scholarship clawback invoice) for a
        withdrawn enrollment, per its Withdrawal Rule. Called by the seminary
        withdrawal dispatcher when the workflow reaches the refund transition."""

    @abstractmethod
    def charge_readmission(self, pe_name: str, effective_date) -> None:
        """Bill the readmission fee for an enrollment returning from leave.

        The readmission policy (whether a fee is charged and which Fee Category)
        lives on the Program Level as oikonomos-owned custom fields, so the
        backend reads it. No-op with no financial app — readmission is free."""

    @abstractmethod
    def sync_enrollment_payers(self, pe_name: str) -> None:
        """(Re)build the billing payer snapshot (Payers Fee Category PE + rows)
        for a Program Enrollment from its program's current Program Fees. Called
        from the PE form's save action; a no-op with no financial app — a
        Frappe-only seminary has no payer rows to keep in sync."""

    @abstractmethod
    def student_scholarships(self, student: str) -> list:
        """Active Scholarship Award(s) for a student, with retention info, for the
        Fees portal. Empty with no financial app — scholarships are an oikonomos
        concept."""

    @abstractmethod
    def available_scholarships(self, student: str) -> list:
        """Scholarship templates the student may apply for on the portal. Empty
        with no financial app."""

    @abstractmethod
    def apply_for_scholarship(
        self, program_enrollment: str, scholarship: str, comment: str | None = None
    ) -> str | None:
        """Create a Scholarship Award request from the portal. Raises with no
        financial app — there are no scholarships to apply for."""

    # -- Student-facing invoice reads + payment-gateway URLs -----------------
    # The portal (Fees / Enrollment / Program Audit pages, the applicant web
    # form) calls these; a Frappe-only seminary returns empty / None (no
    # invoices, no gateway).

    @abstractmethod
    def student_invoices(self, student: str | None = None) -> list:
        """The student's submitted invoices, formatted for the Fees page."""

    @abstractmethod
    def pe_unpaid_invoices(self, program_enrollment: str) -> list:
        """Unpaid invoices for a Program Enrollment, grouped by payer."""

    @abstractmethod
    def unpaid_invoice_for_cei(self, cei_name: str) -> dict | None:
        """The latest unpaid invoice for a Course Enrollment Individual, or None."""

    @abstractmethod
    def graduation_request_invoices(self, gr_name: str) -> list:
        """Submitted invoices linked to a Graduation Request."""

    @abstractmethod
    def application_payment_url(self, applicant_name: str) -> dict | None:
        """Payment URL + instructions for an applicant's Application invoice."""

    @abstractmethod
    def invoice_payment_url(self, invoice_name: str) -> dict | None:
        """Gateway payment URL for one of the student's invoices."""

    @abstractmethod
    def student_balance_payment_url(self) -> dict | None:
        """Gateway payment URL for the student's full outstanding balance."""

    @abstractmethod
    def student_partial_balance_payment_url(
        self, amount=None, invoices=None
    ) -> dict | None:
        """Gateway payment URL for a partial balance payment."""

    @abstractmethod
    def cei_invoices(self, cei_name: str, include_cancelled: bool = False) -> list:
        """Names of the invoices linked to a Course Enrollment Individual. Used by
        the regenerate-invoice action. Empty with no financial app."""

    @abstractmethod
    def set_enrollment_payers_active(self, pe_name: str, active: bool) -> None:
        """Sync the active flag on a Program Enrollment's payer snapshot when its
        billability changes (terminal / leave transitions). No-op with no
        financial app — there are no payer rows."""

    # -- ERPNext company context (the bridge owns the Company / Holiday List) ---

    @abstractmethod
    def company_country(self) -> str | None:
        """Country of the configured billing Company, or None with no financial
        app (callers fall back to the system default)."""

    @abstractmethod
    def company_holiday_dates(self) -> set:
        """Holiday dates from the billing Company's holiday list. Empty with no
        financial app."""


class NullFinancialBackend(FinancialBackend):
    """No financial app installed. Everything reads as free / fully paid so
    academic flows never block on payment and never try to bill."""

    def has_financials(self) -> bool:
        return False

    def payment_status_for_cei(self, cei_name: str) -> PaymentAggregate:
        return PaymentAggregate(paid_percent=100.0)

    def payment_status_for_graduation(self, gr_name: str) -> PaymentAggregate:
        return PaymentAggregate(paid_percent=100.0)

    def generate_enrollment_invoice(self, cei_doc) -> int:
        return 0

    def generate_program_enrollment_invoices(self, pfc_doc) -> dict:
        return {"created": 0, "skipped": 0, "failed": 0}

    def process_withdrawal_refunds(self, withdrawal_doc) -> None:
        return None

    def charge_readmission(self, pe_name: str, effective_date) -> None:
        return None

    def sync_enrollment_payers(self, pe_name: str) -> None:
        return None

    def student_scholarships(self, student: str) -> list:
        return []

    def available_scholarships(self, student: str) -> list:
        return []

    def apply_for_scholarship(
        self, program_enrollment: str, scholarship: str, comment: str | None = None
    ) -> str | None:
        frappe.throw(frappe._("Scholarship applications are not enabled."))

    def student_invoices(self, student: str | None = None) -> list:
        return []

    def pe_unpaid_invoices(self, program_enrollment: str) -> list:
        return []

    def unpaid_invoice_for_cei(self, cei_name: str) -> dict | None:
        return None

    def graduation_request_invoices(self, gr_name: str) -> list:
        return []

    def application_payment_url(self, applicant_name: str) -> dict | None:
        return None

    def invoice_payment_url(self, invoice_name: str) -> dict | None:
        return None

    def student_balance_payment_url(self) -> dict | None:
        return None

    def student_partial_balance_payment_url(
        self, amount=None, invoices=None
    ) -> dict | None:
        return None

    def cei_invoices(self, cei_name: str, include_cancelled: bool = False) -> list:
        return []

    def set_enrollment_payers_active(self, pe_name: str, active: bool) -> None:
        return None

    def company_country(self) -> str | None:
        return None

    def company_holiday_dates(self) -> set:
        return set()


def get_financial_backend() -> FinancialBackend:
    """Resolve the registered financial backend, or the null fallback.

    The last registration wins (standard Frappe hook-override semantics), so an
    app installed later can supersede an earlier one.
    """
    paths = frappe.get_hooks("seminary_financial_backend")
    if not paths:
        return NullFinancialBackend()
    return frappe.get_attr(paths[-1])()
