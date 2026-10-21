// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Person Requirement', {
	setup(frm) {
		frm.set_query('reference_doctype', () => ({
			filters: { name: ['in', ['Program Enrollment', 'Instructor']] },
		}));
	},
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === 'Waived') {
			frm.add_custom_button(__('Remove Waiver'), () => {
				frappe.call({
					method: 'seminary.seminary.requirements.unwaive_requirement',
					args: { requirement: frm.doc.name },
				}).then(() => frm.reload_doc());
			});
		} else if (frm.doc.status !== 'Satisfied') {
			frm.add_custom_button(__('Waive'), () => {
				frappe.prompt(
					{ fieldname: 'reason', fieldtype: 'Small Text', label: __('Reason'), reqd: 1 },
					(v) => frappe.call({
						method: 'seminary.seminary.requirements.waive_requirement',
						args: { requirement: frm.doc.name, reason: v.reason },
					}).then(() => frm.reload_doc()),
					__('Waive requirement'),
					__('Waive'),
				);
			});
		}
	},
});
