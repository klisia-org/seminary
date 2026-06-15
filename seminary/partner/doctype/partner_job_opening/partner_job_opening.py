# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PartnerJobOpening(Document):
    def validate(self):
        self._validate_doctrinal_alignment()

    def _validate_doctrinal_alignment(self):
        """Requiring doctrinal alignment is meaningless unless the organization
        actually publishes a doctrinal statement for applicants to respond to."""
        if not self.require_doctrinal_alignment:
            return
        statement = frappe.db.get_value(
            "Partner Organization", self.partner_org, "doctrinal_statement"
        )
        if not statement or not frappe.utils.strip_html(statement).strip():
            frappe.throw(
                _(
                    "{0} has no doctrinal statement, so doctrinal alignment can't be required. "
                    "Add a doctrinal statement to the organization first, or uncheck "
                    '"Require Doctrinal Alignment".'
                ).format(frappe.bold(self.partner_org))
            )
