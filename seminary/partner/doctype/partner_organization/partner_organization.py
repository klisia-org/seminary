import frappe
from frappe import _
from frappe.model.document import Document


class PartnerOrganization(Document):
    def validate(self):
        self._validate_primary_contact()

    def on_update(self):
        self._grant_portal_roles()

    def _validate_primary_contact(self):
        """At most one contact row may be marked as the primary point of
        contact, so downstream features (and the future portal) can resolve a
        single primary unambiguously."""
        primaries = [c for c in self.contacts if c.is_primary]
        if len(primaries) > 1:
            frappe.throw(_("Only one contact can be marked as the primary contact."))

    def _grant_portal_roles(self):
        """Any contact granted portal access must hold the Partner role so the
        partner portal (ADR 053) and its record-level scoping recognize them.
        Driven from the parent because Frappe doesn't auto-run child validate."""
        for contact in self.contacts:
            if not (contact.portal_access and contact.portal_user):
                continue
            if "Partner" not in set(frappe.get_roles(contact.portal_user)):
                user_doc = frappe.get_doc("User", contact.portal_user)
                # add_roles() saves the User; a partner staffer triggering this
                # (e.g. inviting a colleague) can't write User, so ignore perms.
                user_doc.flags.ignore_permissions = True
                user_doc.add_roles("Partner")
            # Link the contact's Person to this portal user so the portal can
            # resolve "my Person" (for reviews, etc.) — only if neither side is
            # already linked elsewhere.
            if (
                contact.person
                and not frappe.db.get_value("Person", contact.person, "user")
                and not frappe.db.exists("Person", {"user": contact.portal_user})
            ):
                frappe.db.set_value(
                    "Person", contact.person, "user", contact.portal_user
                )
