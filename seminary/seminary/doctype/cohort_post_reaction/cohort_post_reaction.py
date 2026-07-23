# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CohortPostReaction(Document):
    def validate(self):
        # One reaction of a given type per person per target (post or comment).
        # An unset comment is NULL, not "", so normalize in Python rather than
        # trust an equality filter.
        rows = frappe.get_all(
            "Cohort Post Reaction",
            filters={
                "post": self.post,
                "person": self.person,
                "reaction_type": self.reaction_type,
            },
            fields=["name", "comment"],
        )
        mine = self.comment or None
        if any(
            r.name != (self.name or "") and (r.comment or None) == mine for r in rows
        ):
            frappe.throw(_("You have already reacted that way here."))
