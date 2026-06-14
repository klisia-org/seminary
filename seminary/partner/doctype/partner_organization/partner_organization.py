import frappe
from frappe import _
from frappe.model.document import Document


class PartnerOrganization(Document):
    def validate(self):
        self._validate_primary_contact()

    def _validate_primary_contact(self):
        """At most one contact row may be marked as the primary point of
        contact, so downstream features (and the future portal) can resolve a
        single primary unambiguously."""
        primaries = [c for c in self.contacts if c.is_primary]
        if len(primaries) > 1:
            frappe.throw(_("Only one contact can be marked as the primary contact."))
