// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Academic Unit Membership', {
	refresh(frm) {
		faculty_badge(frm);
	},

	person(frm) {
		// Find the Person first; derive their Instructor record (if any) for
		// immediate feedback. The server re-derives on save, so this is UX only.
		if (!frm.doc.person) {
			frm.set_value('instructor', null).then(() => faculty_badge(frm));
			return;
		}
		frappe.db.get_value('Instructor', { person: frm.doc.person }, 'name').then((r) => {
			frm.set_value('instructor', (r.message && r.message.name) || null)
				.then(() => faculty_badge(frm));
		});
	},
});

function faculty_badge(frm) {
	if (frm.doc.instructor) {
		frm.dashboard.add_indicator(__('Faculty'), 'green');
	} else if (frm.doc.person) {
		frm.dashboard.add_indicator(__('Non-instructor · board/committee only'), 'orange');
	}
}
