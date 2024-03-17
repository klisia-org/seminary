// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Course Enrollment Individual", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Course Enrollment Individual", {
    refresh(frm) {
             
        frm.set_query("student_ce", function() {
            return {
                filters: {
                    program: frm.doc.program_ce
                }
            };
        });
        
        frm.set_query("program_ce", function() {
            return {
                filters: {
                    student: frm.doc.student_ce
                }
            };
        });
        frm.set_query("coursesc_ce", "program_ce", function(doc, cdt, cdn) {
            var d = locals[cdt][cdn];
            return {
                filters: {
                    program: d.program_ce,
                    no_prereq: true,
                    audit: true
                }
            };
        });
    },
    submit(frm) {
        frappe.call('make_copies')
            .then(r => {
                frappe.msgprint('Course Enrollment has been submitted');
            });
    }
    });
