// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Internship Placement", {
	onload: scope_to_org,
	refresh: scope_to_org,
});

function scope_to_org(frm) {
	// partner_org is fetched from the application; the set_query closures read it
	// when the dropdown opens, so they work even before the fetch completes.
	frm.set_query("location", () => ({
		filters: { partner_org: frm.doc.partner_org },
	}));
	frm.set_query("site_supervisor", () => ({
		query: "seminary.partner.queries.org_contact_person_query",
		filters: { partner_org: frm.doc.partner_org },
	}));
}
