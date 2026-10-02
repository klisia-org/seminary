// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Academic Unit Membership', {
	refresh(frm) {
		faculty_badge(frm);
		governance_lock(frm);
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

function governance_lock(frm) {
	// A governing body's members follow its seats in Aretenic (p014); roster order and
	// capabilities stay editable here.
	if (!frm.doc.unit || !frappe.boot.versions?.aretenic) return;
	frappe.db.get_value('Academic Unit', frm.doc.unit, 'kept_by_governance_record').then((r) => {
		const locked = !!(r.message && r.message.kept_by_governance_record);
		['unit', 'person', 'is_active'].forEach((f) => frm.set_df_property(f, 'read_only', locked ? 1 : 0));
		if (locked) {
			frm.set_intro(__('This membership follows a seat in the governance record. Roster order and capabilities can still be changed here.'), 'blue');
		}
	});
}
