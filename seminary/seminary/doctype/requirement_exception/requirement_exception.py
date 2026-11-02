# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class RequirementException(Document):
    """A course substitution, course waiver or requirement waiver for one
    enrollment (decisions/098). Status moves only through the actions in
    `seminary.seminary.exceptions`."""

    def before_insert(self):
        from seminary.seminary import exceptions

        exceptions.before_insert(self)

    def validate(self):
        from seminary.seminary import exceptions

        exceptions.validate(self)

    def after_insert(self):
        from seminary.seminary import exceptions

        exceptions.after_insert(self)
