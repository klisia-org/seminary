# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from urllib.parse import urlparse


class SeminaryHelpEntry(Document):
    def autoname(self):
        """Derive name from mkdocs_url + target for uniqueness.

        Examples:
          .../en/modules/enrollment/                     (doctype: Course Enrollment)  -> modules-enrollment
          .../en/modules/academic-calendar/               (doctype: Academic Year)      -> modules-academic-calendar--academic-year
          .../en/modules/academic-calendar/#academic-term (doctype: Academic Term)      -> modules-academic-calendar-academic-term
        """
        parsed = urlparse(self.mkdocs_url)
        path = parsed.path.strip("/")
        parts = path.split("/")
        # Strip language prefix (2-letter code like "en", "pt", "fr")
        if len(parts) > 1 and len(parts[0]) == 2:
            parts = parts[1:]
        base = "-".join(parts) if parts else "help"

        # Include anchor fragment if present (e.g. #academic-year)
        if parsed.fragment:
            base = f"{base}-{parsed.fragment}"

        # If no anchor, disambiguate by target to avoid collisions
        # when the same page is linked to multiple doctypes/pages
        elif self.document_type:
            suffix = self.document_type.lower().replace(" ", "-")
            if suffix not in base:
                base = f"{base}--{suffix}"
        elif self.frontend_page:
            suffix = self.frontend_page.lower().replace(" ", "-")
            if suffix not in base:
                base = f"{base}--{suffix}"

        self.name = base

    def validate(self):
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
