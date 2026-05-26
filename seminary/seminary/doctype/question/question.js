// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Question', {
    refresh: function (frm) {
        if (
            !frm.is_new() &&
            (frm.doc.type === 'Scripture Matching' ||
                frm.doc.type === 'Scripture Memorization')
        ) {
            frm.add_custom_button(__('Refresh from api.bible'), () => {
                frappe.confirm(
                    __('Re-fetch verse text from api.bible? Any unsaved edits will be saved first.'),
                    () => {
                        frappe.call({
                            method: 'seminary.seminary.doctype.question.question.refresh_scripture_text',
                            args: { name: frm.doc.name },
                            freeze: true,
                            freeze_message: __('Refetching from api.bible…'),
                            callback: () => {
                                frappe.show_alert({
                                    message: __('Verse text refreshed.'),
                                    indicator: 'green',
                                });
                                frm.reload_doc();
                            },
                        });
                    }
                );
            });
        }
    },
});
