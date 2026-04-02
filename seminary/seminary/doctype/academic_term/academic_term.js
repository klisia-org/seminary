// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Academic Term', {

    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Configure Withdrawal Dates'), function() {
                frappe.set_route('List', 'Term Withdrawal Rules', {
                    academic_term: frm.doc.name
                });
            }, __('Actions'));
        }
    },

    after_save: function(frm) {
        console.log("After Save was called");
        console.log(frm.doc.name);
        frappe.call({
            method: "seminary.seminary.api.first_term",
            args: {
                doc: frm.doc.name
            },
            callback: function(response) {
                console.log(response.message);
            }
        });
        frm.reload_doc();
    }

});

