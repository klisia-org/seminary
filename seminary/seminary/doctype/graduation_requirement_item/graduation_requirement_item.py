# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class GraduationRequirementItem(Document):
    """A reusable library item. It is no longer submittable: instead of
    cancel/amend (impossible while programs and student snapshots reference it),
    a requirement is Retired via its workflow (Active <-> Retired). Retiring only
    hides it from the Program Graduation Requirement picker — existing references
    keep resolving by name (snapshot semantics, ADR 012). Deletion stays blocked
    by Frappe's link integrity while anything still points here.
    """

    def validate(self):
        self._resolve_linked_document()

    def _resolve_linked_document(self):
        """Derive the underlying `link_doctype` from the curated Allowed Graduation
        Document picker (ADR 054). Legacy items that already carry a raw
        `link_doctype` (no picker) keep working."""
        if self.requirement_type != "Linked Document":
            return
        if self.allowed_document:
            self.link_doctype = frappe.db.get_value(
                "Allowed Graduation Document", self.allowed_document, "document_type"
            )
        elif not self.link_doctype:
            frappe.throw(
                _("Select a Fulfilling Document for a Linked Document requirement.")
            )
