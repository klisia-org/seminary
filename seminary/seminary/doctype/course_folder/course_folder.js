// Copyright (c) 2025, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Course Folder", {
    after_save: function(frm) {
        console.log("after_save triggered for Course Folder");
        console.log("Folder name:", frm.doc.foldername);

        frappe.call({
            method: "frappe.core.api.file.create_new_folder",
            args: {
                file_name: frm.doc.foldername,
                folder: 'Home'
            },
            callback: function(r) {
                console.log("Response from create_new_folder:", r);
                if (r.message) {
                    frappe.show_alert({
                        message: __('Folder created successfully'),
                        indicator: 'green'
                    });
                } else {
                    console.error("Folder creation failed. Response:", r);
                }
            },
            error: function(err) {
                console.error("Error during frappe.call:", err);
            }
        });
    }
});
