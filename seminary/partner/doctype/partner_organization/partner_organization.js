// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

// Location (ADR 068 §7). The coordinates are resolved from the address and
// never typed, so the form shows what the last lookup concluded rather than
// four read-only numbers with no explanation. A failed lookup is deliberately
// silent at save time — this is where it becomes visible.
// Shared with the Person form: public/js/geo_location.bundle.js.

frappe.ui.form.on("Partner Organization", {
	refresh(frm) {
		// The tax ID is bound before the early return: it is typed on a new
		// record too, and it is the address surface below that needs a saved
		// doc, not this.
		bind_tax_id(frm);
		if (frm.is_new()) return;
		window.seminary?.renderLocationSummary(frm);
		window.seminary?.bindFormAddressAutocomplete(frm, { country_field: "country" });
	},

	// The country decides which registration number is wanted, so changing it
	// has to re-label and re-mask the field (ADR 071).
	country(frm) {
		bind_tax_id(frm);
	},
});

// Shared with the Person and Student Applicant forms:
// public/js/tax_id.bundle.js. An organization is billed as an entity, so in
// Brazil this is a CNPJ rather than a CPF.
function bind_tax_id(frm) {
	window.seminary?.bindTaxIdField(frm, {
		country_fields: ["country"],
		subject: "organization",
	});
}
