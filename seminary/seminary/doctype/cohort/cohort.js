// Copyright (c) 2026, Seminary and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cohort", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		frm.add_custom_button(__("Memberships"), () => {
			frappe.set_route("List", "Cohort Membership", { cohort: frm.doc.name });
		});
	},
});
