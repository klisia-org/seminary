# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Standard Development Question (ADR 065 section 8).

A prompt every development plan in a framework asks. Validation of the keys
lives on the parent Competency Framework controller, per ADR 023.
"""

from frappe.model.document import Document


class StandardDevelopmentQuestion(Document):
    pass
