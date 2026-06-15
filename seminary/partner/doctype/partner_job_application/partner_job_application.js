// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Partner Job Application", {
	setup(frm) {
		// New applications should only target openings still accepting applicants.
		frm.set_query("job_opening", () => {
			return frm.is_new() ? { filters: { status: "Open" } } : {};
		});
	},
});
