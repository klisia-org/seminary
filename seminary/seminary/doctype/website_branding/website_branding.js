// Copyright (c) 2026, Seminary and contributors
// For license information, please see license.txt

frappe.ui.form.on("Website Branding", {
	refresh(frm) {
		// The hero and display options only serve the seminary's own public
		// pages; hide them while Seminary Settings turns those pages off.
		frappe.call({
			method: "seminary.seminary.doctype.website_branding.website_branding.public_website_enabled",
			callback: (r) => {
				for (const field of ["homepage_section", "labels_section"]) {
					frm.toggle_display(field, !!r.message);
				}
			},
		});
	},
});
