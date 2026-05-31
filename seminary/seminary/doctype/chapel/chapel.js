// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Chapel", {
	onload(frm) {
		// Seed the per-chapel sync default from the Seminary Settings master
		// toggle (the chaplain can still override it per service).
		if (frm.is_new() && !frm.doc.sync_with_google_calendar) {
			frappe.db
				.get_single_value("Seminary Settings", "sync_chapels_with_google_calendar")
				.then((v) => {
					if (v) frm.set_value("sync_with_google_calendar", 1);
				});
		}
	},
});
