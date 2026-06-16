// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Internship Position", {
	onload: scope_to_org,
	refresh: scope_to_org,
	partner_org(frm) {
		// The location and supervisor belong to the org; drop stale picks when it changes.
		frm.set_value("location", null);
		frm.set_value("default_site_supervisor", null);
		scope_to_org(frm);
	},
});

function scope_to_org(frm) {
	frm.set_query("location", () => ({
		filters: { partner_org: frm.doc.partner_org },
	}));
	frm.set_query("default_site_supervisor", () => ({
		query: "seminary.partner.queries.org_contact_person_query",
		filters: { partner_org: frm.doc.partner_org },
	}));
}
