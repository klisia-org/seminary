// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Person Document', {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === 'Submitted' || frm.doc.status === 'Rejected') {
			frm.add_custom_button(__('Accept'), () => {
				frappe.call({
					method: 'seminary.seminary.requirements.accept_document',
					args: { person_document: frm.doc.name },
				}).then(() => frm.reload_doc());
			}).addClass('btn-primary');
		}
		if (frm.doc.status === 'Submitted' || frm.doc.status === 'Accepted') {
			frm.add_custom_button(__('Reject'), () => {
				frappe.prompt(
					{ fieldname: 'reason', fieldtype: 'Small Text', label: __('Reason'), reqd: 1,
					  description: __('The person sees this and is asked to upload the document again.') },
					(v) => frappe.call({
						method: 'seminary.seminary.requirements.reject_document',
						args: { person_document: frm.doc.name, reason: v.reason },
					}).then(() => frm.reload_doc()),
					__('Reject document'),
					__('Reject'),
				);
			});
		}
	},
});
