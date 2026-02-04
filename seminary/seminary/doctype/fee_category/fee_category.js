// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fee Category', {
	refresh: function(frm) { frm.toggle_display("is_credit", frm.doc.feecategory_type !== "Tuition");

	},
	onload: function(frm) {
		frm.set_query("fc_event", function() {
			return {
				filters: {
					"active": 1
				}
			};
		});
	},
});
