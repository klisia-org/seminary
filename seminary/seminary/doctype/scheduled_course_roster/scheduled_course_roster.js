
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
            frappe.call('seminary.seminary.api.grade_thisstudent', {name: name}) // Pass the 'name' argument
            .then(r => {
                if (r.message) {
                    return frappe.call('seminary.seminary.api.fgrade_this_std', {name: name});
                }
            })
                     .then(r => {
                        if (r && r.message) {
                             frm.refresh();
                }
            })
        })

        // Registrar / Program Chair: fail (or un-fail) for unexcused absences.
        const canFailForAbsence = ["Registrar", "Program Chair", "Seminary Manager", "System Manager"]
            .some(r => frappe.user_roles.includes(r));
        if (canFailForAbsence) {
            if (!frm.doc.failed_for_absence) {
                frm.add_custom_button(__('Fail for Absence'), function() {
                    frappe.confirm(
                        __('Fail {0} for unexcused absences? Their final grade becomes the FA code (Fail) regardless of scores.', [frm.doc.stuname_roster || frm.doc.student]),
                        () => frappe.call('seminary.seminary.api.fail_for_absence', { name: frm.doc.name })
                            .then(r => { if (r.message) { frappe.show_alert({ message: __('Failed for absence'), indicator: 'orange' }); frm.reload_doc(); } })
                    );
                });
            } else {
                frm.add_custom_button(__('Undo Fail for Absence'), function() {
                    frappe.call('seminary.seminary.api.undo_fail_for_absence', { name: frm.doc.name })
                        .then(r => { if (r.message) { frappe.show_alert({ message: __('Reverted'), indicator: 'green' }); frm.reload_doc(); } });
                });
            }
        }
    }

});
function afterSubmit(frm) {
    // This function will be called after the document is submitted
        var name = frm.doc.name;
        frappe.call('seminary.seminary.api.grade_thisstudent', {name: name}) // Pass the 'name' argument
        .then(r => {
            if (r.message) {
                return frappe.call('seminary.seminary.api.fgrade_this_std', {name: name});
            }
        })
                 .then(r => {
                    if (r && r.message) {
                         frm.refresh();
            }
        })
}
