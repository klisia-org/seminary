# Copyright (c) 2026, Murilo Melo and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


# Per-provider config: bare key the adapter reads -> (doc fieldname, is_secret).
# Secrets are Password fields (encrypted at rest); read via get_password.
CONFIG_FIELDS = {
    "twilio": [
        ("account_sid", "twilio_account_sid", False),
        ("auth_token", "twilio_auth_token", True),
        ("from_number", "twilio_from_number", False),
        ("messaging_service_sid", "twilio_messaging_service_sid", False),
        ("public_url", "public_url", False),
    ],
    "telegram": [
        ("bot_token", "telegram_bot_token", True),
        ("webhook_secret", "telegram_webhook_secret", True),
        ("bot_username", "telegram_bot_username", False),
        ("public_url", "public_url", False),
    ],
}


class ChannelProviderAccount(Document):
    def before_validate(self):
        # Telegram needs a webhook secret, but the operator shouldn't have to
        # invent one — generate it from the bot token they paste.
        if self.provider == "telegram" and not self.telegram_webhook_secret:
            self.telegram_webhook_secret = frappe.generate_hash(length=32)

    def on_update(self):
        if self.provider == "telegram" and self.enabled:
            self._provision_telegram()

    def _provision_telegram(self):
        """Best-effort, post-save automation so a Telegram account works with
        just a bot token: cache the bot @username, and register the webhook
        when the site is publicly reachable over HTTPS. Both are non-fatal —
        on dev (no public URL) the operator uses the *Register Telegram
        Webhook* button with a tunnel base URL instead."""
        if not self.get_password("telegram_bot_token", raise_exception=False):
            return
        from seminary.seminary import telegram_adapter

        if not self.telegram_bot_username:
            try:
                username = telegram_adapter._bot_username(self)
                if username:
                    self.db_set(
                        "telegram_bot_username", username, update_modified=False
                    )
            except Exception:
                frappe.log_error(frappe.get_traceback(), "Telegram getMe on save")

        if frappe.utils.get_url().startswith("https://"):
            try:
                telegram_adapter.setup_webhook(self.name)
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(), "Telegram auto webhook registration"
                )

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
        if self.provider == "twilio" and not (
            self.twilio_from_number or self.twilio_messaging_service_sid
        ):
            frappe.throw(
                _("Provide a From Number or a Messaging Service SID for Twilio.")
            )

    def get_config(self):
        """The effective provider configuration the adapter consumes: the
        typed credential fields (secrets decrypted) overlaid on the optional
        raw Extra Settings JSON. Typed fields win."""
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
