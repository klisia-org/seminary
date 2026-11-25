// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Admission Decision", {
	setup(frm) {
		frm.set_query("student_applicant", () => ({
			filters: { application_status: ["in", ["In Review", "Waitlisted"]] },
		}));
	},
});
