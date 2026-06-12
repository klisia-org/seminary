# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

# The award is "active" (and therefore drives invoice-time discounts) only in this
# workflow state and within its effective window. Suspended/Ended/Rejected never bill.
ACTIVE_STATE = "Active"

# States that still occupy the enrollment's single-award slot. A new award/request
# cannot be saved while another award for the same Program Enrollment is in one of
# these (active or still-open-request) states — only Rejected/Ended free the slot.
OCCUPYING_STATES = ("Draft", "Submitted", "Under Review", "Active", "Suspended")


class ScholarshipAward(Document):
    def validate(self):
        self._snapshot_terms()
        self._enforce_single_award()

    def _snapshot_terms(self):
        """Copy the scholarship template's discounts onto the award the first time,
        so later edits to the template don't retroactively change a granted award."""
        if self.award_terms or not self.scholarship:
            return
        rows = frappe.get_all(
            "Scholarship Discounts",
            filters={"parent": self.scholarship, "parentfield": "sch_discounts"},
            fields=["pgm_fee", "mode", "value", "discount_"],
        )
        for r in rows:
            if not r.pgm_fee:
                continue
            mode = r.mode or "Percent"
            # Tolerate templates not yet migrated off the legacy percent-only field.
            value = r.value if (r.value or mode == "Flat") else (r.discount_ or 0)
            self.append(
                "award_terms",
                {"fee_category": r.pgm_fee, "mode": mode, "value": value},
            )

    def _enforce_single_award(self):
        """One award per Program Enrollment. Block a new request while another award
        for the same enrollment is still active or pending."""
        if not self.program_enrollment:
            return
        state = self.workflow_state or "Draft"
        if state not in OCCUPYING_STATES:
            return
        clash = frappe.db.exists(
            "Scholarship Award",
            {
                "program_enrollment": self.program_enrollment,
                "workflow_state": ["in", OCCUPYING_STATES],
                "name": ["!=", self.name or ""],
            },
        )
        if clash:
            frappe.throw(
                _(
                    "An active or pending Scholarship Award ({0}) already exists for "
                    "this Program Enrollment. Only one award per enrollment is allowed."
                ).format(clash)
            )

    def is_active(self):
        if (self.workflow_state or "") != ACTIVE_STATE:
            return False
        td = getdate(today())
        if self.effective_from and getdate(self.effective_from) > td:
            return False
        if self.effective_to and getdate(self.effective_to) < td:
            return False
        return True


def get_active_award(program_enrollment):
    """Return the name of the single active Scholarship Award for an enrollment, or
    None. 'Active' = workflow_state Active and today within the effective window.
    Used by the billing engine and the retention scheduler."""
    if not program_enrollment:
        return None
    td = today()
    rows = frappe.get_all(
        "Scholarship Award",
        filters={
            "program_enrollment": program_enrollment,
            "workflow_state": ACTIVE_STATE,
        },
        fields=["name", "effective_from", "effective_to"],
        order_by="effective_from desc",
    )
    for r in rows:
        if r.effective_from and getdate(r.effective_from) > getdate(td):
            continue
        if r.effective_to and getdate(r.effective_to) < getdate(td):
            continue
        return r.name
    return None
