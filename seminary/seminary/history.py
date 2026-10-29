# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""A school's history imported from another system (ADR 094).

While ``frappe.flags.in_import`` is set, seminary records the past without
acting on it. Frappe's Data Import sets the flag, and so do our own importers
of a school's history. Under the flag:

- no fee, notice, requirement or automatic enrolment fires (§1);
- a Program Enrollment arrives with its final status and the date it ended
  (§2);
- a course row may carry attendance as a summary, as sessions attended out of
  sessions held (§3);
- an accepted document counts its validity from when it was submitted, not
  from today (§4).
"""

import frappe
from frappe import _
from frappe.utils import cint, getdate

from seminary.seminary.program_status import (
    ACTIVE_STATUS,
    TERMINAL_STATUSES,
    _upsert_leaving_record,
)

IMPORTABLE_STATUSES = {ACTIVE_STATUS} | TERMINAL_STATUSES


def importing():
    return bool(frappe.flags.in_import)


def settle_enrollment(pe):
    """A new Program Enrollment, imported: set its status directly, without
    the transitions in program_status (§2)."""
    pe.status = pe.status or ACTIVE_STATUS
    if pe.status not in IMPORTABLE_STATUSES:
        frappe.throw(
            _(
                "An enrollment cannot be imported as {0}. Import it as Active, "
                "then place it on leave."
            ).format(_(pe.status))
        )
    pe.pgmenrol_active = 1 if pe.status == ACTIVE_STATUS else 0
    if pe.status == ACTIVE_STATUS:
        return
    if not pe.date_of_conclusion:
        frappe.throw(
            _("A {0} enrollment needs the date it ended (Date of Conclusion).").format(
                _(pe.status)
            )
        )
    if pe.enrollment_date and getdate(pe.date_of_conclusion) < getdate(
        pe.enrollment_date
    ):
        frappe.throw(_("Date of Conclusion cannot be before the Enrollment Date."))
    if not any(row.to_status == pe.status for row in pe.status_history):
        pe.append(
            "status_history",
            {
                "effective_date": pe.date_of_conclusion,
                "from_status": ACTIVE_STATUS,
                "to_status": pe.status,
                "category": "System",
                "reason": _("Imported history"),
                "actor": frappe.session.user,
            },
        )


def record_leaving(pe):
    """The Student Leaving Record a terminal transition would have written."""
    if pe.status in TERMINAL_STATUSES:
        _upsert_leaving_record(pe, pe.status, pe.date_of_conclusion, None, None)


def check_attendance(rows):
    """Attendance summaries on course rows (§3) must add up."""
    for row in rows:
        attended, held = cint(row.sessions_attended), cint(row.sessions_held)
        if attended < 0 or held < 0:
            frappe.throw(_("Row {0}: sessions cannot be negative.").format(row.idx))
        if attended > held:
            frappe.throw(
                _(
                    "Row {0}: sessions attended ({1}) cannot be more than sessions held ({2})."
                ).format(row.idx, attended, held)
            )
