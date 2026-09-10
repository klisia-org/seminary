import frappe
from frappe import _
from frappe.model.document import Document


class PartnerOrganization(Document):
    def validate(self):
        self._validate_primary_contact()
        self._validate_tax_id()

    def on_update(self):
        self._grant_portal_roles()
        self._refresh_coordinates()

    def _validate_primary_contact(self):
        """At most one contact row may be marked as the primary point of
        contact, so downstream features (and the future portal) can resolve a
        single primary unambiguously."""
        primaries = [c for c in self.contacts if c.is_primary]
        if len(primaries) > 1:
            frappe.throw(_("Only one contact can be marked as the primary contact."))

    def _validate_tax_id(self):
        """Check the registration number against the organization's country and
        store it stripped of punctuation (ADR 071). An organization is billed as
        an entity, so in Brazil that is a CNPJ rather than a CPF."""
        from seminary.seminary import tax_ids

        tax_ids.assert_on(self)

    def _refresh_coordinates(self):
        """Queue a geocode when the address changed (ADR 068 §7).

        Same contract as `Person.refresh_coordinates`: queued and never inline,
        so a provider outage cannot fail the save, and only when the address
        actually moved — every other save would otherwise spend money on an
        address that has not changed.
        """
        from seminary.seminary.integrations import geocoding

        if not geocoding.is_enabled():
            return
        if geocoding.address_changed(self):
            geocoding.enqueue_for(self.doctype, self.name)

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
