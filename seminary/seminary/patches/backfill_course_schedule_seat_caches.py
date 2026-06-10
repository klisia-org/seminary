"""Backfill the Course Schedule seat/demand caches on existing sites.

ADR 035 replaced the increment-only ``enrollments`` counter (which drifted
upward because withdrawals never decremented it) with four caches recomputed
from enrollment state: enrollments, seats_used, registrations, waitlist_count.
This recomputes them once for every Course Schedule so the numbers are correct
from the first migrate.
"""

import frappe

from seminary.seminary.waitlist import recount


def execute():
    for name in frappe.get_all("Course Schedule", pluck="name"):
        try:
            recount(name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"backfill_course_schedule_seat_caches failed: {name}",
            )
    frappe.db.commit()
