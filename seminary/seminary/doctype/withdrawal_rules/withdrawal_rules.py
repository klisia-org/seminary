from frappe.model.document import Document


class WithdrawalRules(Document):
    def validate(self):
        if self.grade_treatment != "Flat Symbol":
            self.transcript_symbol = ""
