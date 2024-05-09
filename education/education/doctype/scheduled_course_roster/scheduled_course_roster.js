
// Copyright (c) 2024, Klisia and Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scheduled Course Roster", {
    on_submit(frm) {
        frm.validate().then(() => {
            afterSubmit(frm);
        });
    },
    refresh(frm) {
        frm.add_custom_button(__('Grade Student'), function() {
            var name = frm.doc.name;
            frappe.call('education.education.api.grade_thisstudent', {name: name}) // Pass the 'name' argument
            .then(r => {
                if (r.message) {
                    return frappe.call('education.education.api.fgrade_this_std', {name: name});
                }
            })
                     .then(r => {
                        if (r && r.message) {
                             frm.refresh();
                }
            })
        })}

}); 
function afterSubmit(frm) {
    // This function will be called after the document is submitted
        var name = frm.doc.name;
        frappe.call('education.education.api.grade_thisstudent', {name: name}) // Pass the 'name' argument
        .then(r => {
            if (r.message) {
                return frappe.call('education.education.api.fgrade_this_std', {name: name});
            }
        })
                 .then(r => {
                    if (r && r.message) {
                         frm.refresh();
            }
        })
}
