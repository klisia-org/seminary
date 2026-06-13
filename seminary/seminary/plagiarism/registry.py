"""Provider registry — the plagiarism analogue of comms.get_adapter_registry.

Adapters are declared in hooks.py as ``plagiarism_providers = {key: dotted.path}``
so other apps can add a provider with one class and one Provider Account row.
"""

import frappe
from frappe import _

ADAPTER_HOOK = "plagiarism_providers"


def get_adapter_registry() -> dict:
    registry = {}
    hooked = frappe.get_hooks(ADAPTER_HOOK) or {}
    for key, value in hooked.items():
        registry[key] = value[-1] if isinstance(value, list) else value
    return registry


def get_adapter(provider_key: str):
    path = get_adapter_registry().get(provider_key)
    if not path:
        frappe.throw(
            _("No plagiarism adapter registered for provider {0}.").format(provider_key)
        )
    return frappe.get_attr(path)()
