# Copyright (c) 2026, Murilo Melo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CommunicationTemplate(Document):
    def validate(self):
        seen = set()
        for row in self.versions:
            key = (row.channel, row.language or "")
            if key in seen:
                frappe.throw(
                    _("Duplicate version for channel {0} / language {1}.").format(
                        row.channel, row.language or _("(any)")
                    )
                )
            seen.add(key)

    def get_version(self, channel, language=None):
        """Fallback chain: (channel, language) -> (channel, blank) -> first
        version for the channel. Returns the child row or None."""
        rows = [r for r in self.versions if r.channel == channel]
        if language:
            exact = next((r for r in rows if r.language == language), None)
            if exact:
                return exact
        blank = next((r for r in rows if not r.language), None)
        if blank:
            return blank
        return rows[0] if rows else None
