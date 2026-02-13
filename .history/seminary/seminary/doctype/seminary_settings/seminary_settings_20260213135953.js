// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Seminary Settings', {
	onload: function(frm) {
		frm.set_query("current_academic_term", (doc) => {
			return {
				filters: {
					"academic_year": doc.current_academic_year
				}
			}
		});
	}
});
frappe.ui.form.on('Seminary Settings', {
    refresh: function(frm) {
        if (!frm.doc.demo_data_installed && !frm.doc.no_more_demo) {
            frm.add_custom_button(__('Install Demo Data'), () => {
                frappe.confirm(
                    'This will create sample programs, courses, students, and enrollments. Continue?',
                    () => {
                        frappe.call({
                            method: 'seminary.demo.install_demo',
                            freeze: true,
                            freeze_message: __('Installing demo data...'),
                            callback: (r) => frm.reload_doc()
                        });
                    }
                );
            }, __('Demo'));
        } else {
            frm.add_custom_button(__('Remove Demo Data'), () => {
                frappe.confirm(
                    '<strong>This will permanently delete all demo records.</strong> Continue?',
                    () => {
                        frappe.call({
                            method: 'seminary.demo.remove_demo',
                            freeze: true,
                            freeze_message: __('Removing demo data...'),
                            callback: (r) => frm.reload_doc()
                        });
                    }
                );
            }, __('Demo'));
        }
		
    }
});