import frappe
from frappe.model.document import Document


class TermWithdrawalRules(Document):
    def validate(self):
        self.validate_applies_until()
        self.validate_no_date_overlap()

    def validate_applies_until(self):
        if not self.academic_term or not self.applies_until:
            return
        term_end = frappe.db.get_value(
            "Academic Term", self.academic_term, "term_end_date"
        )
        if term_end and self.applies_until > str(term_end):
            frappe.throw(
                f"'Applies Until' ({self.applies_until}) cannot be after the term end date ({term_end})."
            )

    def validate_no_date_overlap(self):
        if not self.academic_term or not self.applies_until:
            return
        existing = frappe.db.get_all(
            "Term Withdrawal Rules",
            filters={
                "academic_term": self.academic_term,
                "applies_until": self.applies_until,
                "name": ("!=", self.name),
            },
            limit=1,
        )
        if existing:
            frappe.throw(
                f"A Term Withdrawal Rule already exists for {self.academic_term} with the same 'Applies Until' date."
            )
