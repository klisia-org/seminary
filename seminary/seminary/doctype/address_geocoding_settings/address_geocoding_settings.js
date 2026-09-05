// Copyright (c) 2026, Klisia and contributors
// For license information, please see license.txt

// Base URL per provider. Vendor proxy has none to guess — it is whatever
// endpoint the host runs — so it is left for the admin to paste rather than
// pre-filled with something plausible and wrong.
const PROVIDER_BASE_URL = {
	Google: "https://maps.googleapis.com",
	"Vendor proxy": "",
};

const KNOWN_BASE_URLS = Object.values(PROVIDER_BASE_URL).filter(Boolean);

frappe.ui.form.on("Address Geocoding Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), () => test_connection(frm));
		hint(frm);
	},

	provider(frm) {
		// Only fill a blank, or replace another provider's default. A URL the
		// admin typed themselves is theirs to keep.
		const current = (frm.doc.base_url || "").trim();
		if (current && !KNOWN_BASE_URLS.includes(current)) return;
		frm.set_value("base_url", PROVIDER_BASE_URL[frm.doc.provider] || "");
		hint(frm);
	},
});

function hint(frm) {
	const google = frm.doc.provider === "Google";
	frm.set_df_property(
		"api_key",
		"description",
		google
			? __("Google Cloud key with the Geocoding API enabled. Restrict it by IP.")
			: __("The site token issued by whoever hosts this seminary.")
	);
	frm.set_df_property(
		"base_url",
		"description",
		google
			? __("Leave as the Google endpoint unless you proxy it yourself.")
			: __("The hosting provider's geocoding endpoint.")
	);
}

function test_connection(frm) {
	frappe.dom.freeze(__("Asking the provider..."));
	frappe
		.call({ doc: frm.doc, method: "test_connection" })
		.then((r) => {
			frappe.dom.unfreeze();
			const res = r.message || {};
			if (!res.ok) {
				frappe.msgprint({
					title: __("Geocoding failed"),
					indicator: "red",
					message: frappe.utils.escape_html(res.message || __("Unknown error")),
				});
				return;
			}
			frappe.msgprint({
				title: __("Geocoding works"),
				indicator: "green",
				message: `${__("Resolved {0} to {1}, {2} ({3}).", [
					frappe.utils.escape_html(res.address),
					res.latitude,
					res.longitude,
					frappe.utils.escape_html(res.precision || "—"),
				])}`,
			});
		})
		.catch(() => frappe.dom.unfreeze());
}
