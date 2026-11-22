// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Web Meeting Account", {
	onload(frm) {
		frappe
			.call("seminary.seminary.school_meetings.provider_names")
			.then((r) => frm.set_df_property("provider", "options", r.message || []));
	},
});
