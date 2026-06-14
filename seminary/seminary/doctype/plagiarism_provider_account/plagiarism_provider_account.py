# Copyright (c) 2026, Murilo Melo and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

# Per-provider config: bare key the adapter reads -> (doc fieldname, is_secret).
# Secrets are Password fields (encrypted at rest); read via get_password.
CONFIG_FIELDS = {
    "internal": [],
    "external-http": [
        ("endpoint", "api_endpoint", False),
        ("api_key", "api_key", True),
        ("auth_header", "auth_header", False),
        ("auth_scheme", "auth_scheme", False),
        ("timeout", "timeout", False),
        ("request_template", "request_template", False),
        ("response_score_path", "response_score_path", False),
        ("response_sources_path", "response_sources_path", False),
    ],
}


class PlagiarismProviderAccount(Document):
    def validate(self):
        from seminary.seminary.plagiarism.registry import get_adapter_registry

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
                frappe.throw(_("Extra Settings must be valid JSON."))
        if self.provider == "external-http" and not self.api_endpoint:
            frappe.throw(_("An API Endpoint is required for an external provider."))

    def get_config(self):
        """Effective provider configuration: typed credential fields (secrets
        decrypted) overlaid on the optional raw Extra Settings JSON. Typed
        fields win. Mirrors Channel Provider Account.get_config()."""
        try:
            cfg = json.loads(self.settings or "{}")
        except ValueError:
            cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
        for key, fieldname, is_secret in CONFIG_FIELDS.get(self.provider, []):
            value = (
                self.get_password(fieldname, raise_exception=False)
                if is_secret
                else self.get(fieldname)
            )
            if value:
                cfg[key] = value
        return cfg
