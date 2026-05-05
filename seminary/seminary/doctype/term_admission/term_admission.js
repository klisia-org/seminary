frappe.ui.form.on('Term Admission', {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.docstatus !== 2) {
			frm.add_custom_button(__('Refresh from Programs'), () => {
				frappe.call({
					method: 'seminary.seminary.doctype.term_admission.term_admission.refresh_programs',
					args: { name: frm.doc.name },
					freeze: true,
					freeze_message: __('Looking for new Timed Programs...'),
					callback: (r) => {
						const added = (r.message && r.message.added) || 0;
						frappe.show_alert({
							message: added
								? __('Added {0} program(s).', [added])
								: __('No new Timed Programs to add.'),
							indicator: added ? 'green' : 'blue',
						});
						if (added) frm.reload_doc();
					},
				});
			});
		}
	},
});
