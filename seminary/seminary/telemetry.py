import frappe

# `site_age` is still published by this module; import it explicitly. The
# removed `from frappe.utils.telemetry import ...` line below used to be what
# bound the submodule as an attribute of `frappe.utils`, so dropping it without
# this would turn the ImportError into an AttributeError at call time.
from frappe.utils.telemetry import site_age

# Frappe v16 dropped its PostHog integration (`refactor!: Drop posthog
# integration`, #39990) and replaced it with `frappe.utils.telemetry.pulse`.
# `POSTHOG_HOST_FIELD` / `POSTHOG_PROJECT_FIELD` no longer exist, so importing
# them from `frappe.utils.telemetry` raised ImportError the moment frappe was
# updated — a module-level failure, so every whitelisted method in this file
# became unreachable. The two keys are plain site-config names; define them here
# rather than depend on a constant frappe no longer publishes.
POSTHOG_PROJECT_FIELD = "posthog_project_id"
POSTHOG_HOST_FIELD = "posthog_host"


@frappe.whitelist()
def get_posthog_settings():
    return {
        "posthog_project_id": frappe.conf.get(POSTHOG_PROJECT_FIELD),
        "posthog_host": frappe.conf.get(POSTHOG_HOST_FIELD),
        "enable_telemetry": frappe.get_system_settings("enable_telemetry"),
        "telemetry_site_age": site_age(),
    }
