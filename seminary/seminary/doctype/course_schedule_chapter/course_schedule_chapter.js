// Copyright (c) 2025, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Course Schedule Chapter", {
	onload: function (frm) {
		frm.set_query("lesson", "lessons", function () {
			return {
				filters: {
					chapter: frm.doc.name,
				},
			};
		});
	},
});
