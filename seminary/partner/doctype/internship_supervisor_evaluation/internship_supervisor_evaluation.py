# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class InternshipSupervisorEvaluation(Document):
    def on_submit(self):
        # Submitting the evaluation may complete the placement (when hours are met).
        from seminary.partner import internship

        internship.maybe_advance_placement_status(self.internship_placement)
