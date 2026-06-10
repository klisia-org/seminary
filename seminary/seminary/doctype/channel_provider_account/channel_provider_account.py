# Copyright (c) 2026, Murilo Melo and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


class ChannelProviderAccount(Document):
    def validate(self):
        from seminary.seminary.comms import get_adapter_registry

        registry = get_adapter_registry()
        if self.provider not in registry:
            frappe.throw(
                _("Unknown provider {0}. Registered providers: {1}").format(
                    self.provider, ", ".join(sorted(registry)) or _("none")
                )
            )
        if self.settings:
            try:
                json.loads(self.settings)
            except ValueError:
                frappe.throw(_("Settings must be valid JSON."))
