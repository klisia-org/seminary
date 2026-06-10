// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Campus", {
	refresh(frm) {
		// Populate the Timezone Select from Frappe's own timezone list, the same
		// way System Settings does for its Time Zone field.
		frappe.call({
			method: "seminary.seminary.utils.get_timezones",
			callback(r) {
				if (r.message) {
					frm.set_df_property("timezone", "options", [""].concat(r.message));
				}
			},
		});
	},
});
