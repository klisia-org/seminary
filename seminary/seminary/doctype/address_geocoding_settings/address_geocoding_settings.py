# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


#: A famously stable, unambiguously geocodable address. Used only by the Test
#: Connection button — one lookup, on demand, so it costs a fraction of a cent
#: and proves the key, the endpoint and the response shape in one go.
PROBE_ADDRESS = "1600 Pennsylvania Avenue NW, Washington, DC 20500, USA"


class AddressGeocodingSettings(Document):
    def validate(self):
        self.require_credentials_for_provider()

    @frappe.whitelist()
    def test_connection(self):
        """Geocode one known address and report what came back.

        Exists to take a class of support ticket off the table: a
        misconfigured key otherwise shows up as coordinates that never appear,
        with nothing on screen to say why — lookups are queued and their
        failures are deliberately silent so an address can always be saved.
        """
        from seminary.seminary.integrations import geocoding

        if not self.enabled:
            return {"ok": False, "message": _("Geocoding is not enabled.")}
        try:
            # Through the module's own accessor, so a Test Connection click
            # exercises exactly the configuration a real lookup would use.
            with geocoding.using(self):
                result = geocoding.lookup(PROBE_ADDRESS)
        except geocoding.GeocodingError as exc:
            # The provider answered and refused — a bad key, a disabled API, an
            # exhausted quota. Its own words are more useful than ours.
            return {"ok": False, "message": str(exc)}
        except Exception as exc:
            return {
                "ok": False,
                "message": _("Could not reach the provider: {0}").format(exc),
            }

        if not result:
            return {
                "ok": False,
                "message": _(
                    "The provider answered but matched nothing for a landmark "
                    "address, which usually means the endpoint is not a "
                    "geocoding service."
                ),
            }
        return {
            "ok": True,
            "address": PROBE_ADDRESS,
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "precision": result.get("precision"),
        }

    def require_credentials_for_provider(self):
        """A provider without its credential geocodes nothing, silently.

        Failures here leave coordinates null by design (an address save must
        never fail because a third party is down), which means a missing key
        would look exactly like "nobody has an address yet". Refuse the
        configuration instead of letting it fail quietly forever.
        """
        if not self.enabled:
            return
        if not self.base_url:
            frappe.throw(_("Address Geocoding Settings needs a Base URL."))
        if not self.get_password("api_key", raise_exception=False):
            frappe.throw(
                _(
                    "Address Geocoding Settings is enabled but has no server API key. For "
                    "Google this is the Geocoding API key; for Vendor proxy it "
                    "is the site token."
                )
            )
