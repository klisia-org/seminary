# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Graduation Request controller.

Lifecycle (mirrors ADR 016 — Course Enrollment Individual):
    Draft → Awaiting Payment → Approved
                            ↓
                        Cancelled

This controller owns only the academic lifecycle (candidacy guard, diploma
issue/revoke, workflow stamping). Fee billing on submit and the cancellation of
unpaid invoices are owned by the oikonomos bridge
(`oikonomos.financial.graduation`, via doc_events); the `gr_si` idempotency flag
is stamped there. With no bridge installed the request is free.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


NAME_LOCKED_STATES = ("Academic Review", "Financial Review", "Approved")


class GraduationRequest(Document):
    def validate(self):
        self._fetch_program_and_dates()
        self._guard_unique_active_request()
        self._guard_name_edits_after_review()

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

    # Sales Invoice generation on submit is owned by the oikonomos bridge
    # (oikonomos.financial.graduation.on_submit, via doc_events). With no bridge
    # the graduation request submits free; oikonomos stamps gr_si.

    def on_update_after_submit(self):
        if self.workflow_state != "Approved":
            return
        if frappe.db.exists("Diploma", {"graduation_request": self.name}):
            return
        self._issue_diploma()

    def on_cancel(self):
        """Stamp workflow_state and revoke any issued diploma.

        Cancelling the linked Sales Invoices is owned by the oikonomos bridge
        (oikonomos.financial.graduation.on_cancel), which also honours the
        non-refundable `flags.cascade_from_pe_withdrawal` path.
        """
        frappe.db.set_value(
            self.doctype,
            self.name,
            "workflow_state",
            "Cancelled",
            update_modified=False,
        )

        self._revoke_diploma_if_issued()

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

    def _revoke_diploma_if_issued(self):
        """Mark the Diploma revoked rather than deleting it — preserves the
        verification hash for the future v2 page (which should report the
        Revoked state, not 404)."""
        diploma = frappe.db.get_value(
            "Diploma", {"graduation_request": self.name}, "name"
        )
        if not diploma:
            return
        reason = "Graduation Request cancelled"
        if getattr(self.flags, "cascade_from_pe_withdrawal", False):
            reason += " (cascade from PE withdrawal)"
        frappe.db.set_value(
            "Diploma",
            diploma,
            {
                "revoked": 1,
                "revoked_on": today(),
                "revocation_reason": reason,
            },
            update_modified=False,
        )

    def _guard_name_edits_after_review(self):
        """Lock the diploma name fields once Academic Review begins.

        Registrar (and Program Chair) can still correct typos at any state.
        """
        if self.is_new():
            return
        changed = self.has_value_changed(
            "legal_name_at_graduation"
        ) or self.has_value_changed("phonetic_name_snapshot")
        if not changed:
            return
        if self.workflow_state in NAME_LOCKED_STATES:
            roles = set(frappe.get_roles())
            if not (
                roles
                & {"Program Chair", "Registrar", "Seminary Manager", "System Manager"}
            ):
                frappe.throw(
                    _(
                        "Diploma name can only be changed before Academic Review. "
                        "Contact the registrar."
                    )
                )

    def _issue_diploma(self):
        """Create the Diploma record. Two layers of idempotency:
        the `frappe.db.exists` short-circuit in on_update_after_submit,
        and the unique constraint on Diploma.graduation_request."""
        diploma = frappe.get_doc(
            {
                "doctype": "Diploma",
                "graduation_request": self.name,
                "student": self.student,
                "program": self.program,
                "program_enrollment": self.program_enrollment,
                "legal_name": self.legal_name_at_graduation,
                "phonetic_name": self.phonetic_name_snapshot,
                "issued_on": today(),
                "expected_graduation_date": self.expected_graduation_date,
            }
        )
        diploma.flags.ignore_permissions = True
        diploma.insert(ignore_permissions=True)

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
