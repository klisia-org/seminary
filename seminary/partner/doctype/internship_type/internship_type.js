// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Internship Type', {
	refresh(frm) {
		// Draw advisors from an active Academic Unit's Internship Advisor pool.
		frm.set_query('academic_unit', function () {
			return { filters: { is_active: 1 } };
		});
	},
});
