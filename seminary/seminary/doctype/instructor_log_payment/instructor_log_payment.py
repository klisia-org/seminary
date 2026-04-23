# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class InstructorLogPayment(Document):
    def validate(self):
        self.validate_unique_log_event()

    def validate_unique_log_event(self):
        """Prevent two payment rows for the same (instructor_log, payment_event)."""
        duplicate = frappe.db.exists(
            "Instructor Log Payment",
            {
                "instructor_log": self.instructor_log,
                "payment_event": self.payment_event,
                "name": ["!=", self.name],
            },
        )
        if duplicate:
            frappe.throw(
                _(
                    "Instructor Log row {0} is already paid for event {1} "
                    "(existing record: {2})."
                ).format(self.instructor_log, self.payment_event, duplicate)
            )


def portion_already_paid(instructor_log: str) -> float:
    """Sum of portions for an Instructor Log row across non-cancelled slips."""
    rows = frappe.db.sql(
        """
        select coalesce(sum(ilp.portion), 0)
        from `tabInstructor Log Payment` ilp
        join `tabSalary Slip` ss on ss.name = ilp.salary_slip
        where ilp.instructor_log = %s
          and ss.docstatus != 2
        """,
        instructor_log,
    )
    return float(rows[0][0] or 0) if rows else 0.0


def events_already_paid(instructor_log: str) -> set[str]:
    """Set of payment_event values already recorded for this log row (non-cancelled)."""
    rows = frappe.db.sql(
        """
        select ilp.payment_event
        from `tabInstructor Log Payment` ilp
        join `tabSalary Slip` ss on ss.name = ilp.salary_slip
        where ilp.instructor_log = %s
          and ss.docstatus != 2
        """,
        instructor_log,
    )
    return {r[0] for r in rows}
