# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The catalog of rules the cohort planner can apply (ADR 067 section 8).

`handler` names a function in `discipleship.criteria`, and it is validated
against that hard-coded registry rather than trusted. A free-text dotted path an
admin can type is remote code execution by form field, so the field is
`read_only`, seeded, and re-checked on every save -- because `read_only` is a UI
hint that a REST insert never sees.

A school owns the display name and the description; it does not own which code
runs. That split is why `handler` is the docname and `criterion_name` is only the
title.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class CohortAssignmentCriterion(Document):
    def validate(self):
        self.validate_handler_is_real()

    def validate_handler_is_real(self):
        from seminary.seminary.discipleship import criteria

        known = criteria.registry().get(self.handler)
        if not known:
            frappe.throw(
                _(
                    "{0} is not a rule this system knows how to run. Assignment "
                    "rules ship with the application -- you can rename, describe "
                    "and retire them, but not invent one here."
                ).format(frappe.bold(self.handler or _("(empty)")))
            )

        # The kind and the field it reads are properties of the code, not
        # choices: a Ranking recorded as a Filter would be ANDed into the pool,
        # where it can only ever return "yes".
        self.kind = known.kind
        self.requires_field = known.requires_field
