# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SeminaryHelpEntry(Document):
    def autoname(self):
        """Name from the help target (doctype or frontend page).

        The entry now centres on `local_notes`; `mkdocs_url` is optional, so the
        name is derived from the target rather than the URL. Frappe appends a
        numeric suffix on collision. Existing rows keep their names (autoname
        runs only on insert).
        """
        target = self.document_type or self.frontend_page or "help"
        self.name = frappe.scrub(target).replace("_", "-")

    def validate(self):
        if self.frontend_page:
            # The frontend matches on the Vue route name (e.g. "Courses"), which
            # never carries a file extension — tolerate a pasted "Courses.vue".
            self.frontend_page = self.frontend_page.strip()
            if self.frontend_page.endswith(".vue"):
                self.frontend_page = self.frontend_page[: -len(".vue")]

        if not self.document_type and not self.frontend_page:
            frappe.throw(
                _("At least one of Document Type or Frontend Page must be set.")
            )


@frappe.whitelist(allow_guest=False)
def get_help_entry(document_type=None, frontend_page=None):
    """Fetch active help entry for a given doctype or frontend page."""
    filters = {"is_active": 1}
    if document_type:
        filters["document_type"] = document_type
    elif frontend_page:
        filters["frontend_page"] = frontend_page
    else:
        return None

    return frappe.db.get_value(
        "Seminary Help Entry",
        filters,
        ["name", "mkdocs_url", "local_notes", "show_students"],
        as_dict=True,
    )
