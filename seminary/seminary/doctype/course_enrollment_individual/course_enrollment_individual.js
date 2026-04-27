// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Course Enrollment Individual", {
// 	refresh(frm) {

// 	},
// });
function load_courses_for_program(frm) {
    if (!frm.doc.program_ce) return;
    frappe.call({
        method: "seminary.seminary.api.courses_for_student",
        args: { program_ce: frm.doc.program_ce },
        callback: function (response) {
            frm.courses = response.message || [];
            frm.refresh_field("coursesc_ce");
        },
    });
}

frappe.ui.form.on("Course Enrollment Individual", {
    onload(frm) {


        frappe.db.get_single_value('Seminary Settings', 'allow_audit')
            .then(value => {
                if (value === 1) {
                    frm.toggle_display('audit', true);
                } else {
                    frm.toggle_display('audit', false);
                }
            })
            .catch(error => {
                console.log('Error occurred while fetching Seminary Settings:', error);
            });
        frappe.db.get_list('Program Enrollment', {
            fields: ['name'],
            filters: {
                docstatus: 1
            }
        }).then(result => {
            const programEnrollments = result.map(item => item.name);
            frm.set_query('program_ce', () => {
                return {
                    filters: {
                        name: ['in', programEnrollments]
                    }
                };
            });
        }).catch(error => {
            console.log('Error occurred while fetching Program Enrollment:', error);
        });

    },
    refresh(frm) {
        frm.set_query("coursesc_ce", () => {
            const NO_MATCH = { filters: { course: ["in", ["__none__"]], open_enroll: 1 } };
            let q;
            if (!frm.doc.program_ce) {
                q = NO_MATCH;
            } else if (frm.doc.no_prereq === 1 || frm.doc.audit === 1) {
                q = { filters: { open_enroll: 1 } };
            } else if (frm.courses && frm.courses.length) {
                q = { filters: { course: ["in", frm.courses], open_enroll: 1 } };
            } else {
                q = NO_MATCH;
            }
            console.log("coursesc_ce set_query →", q.filters);
            return q;
        });

        // Existing record: program is already set but field event never fired.
        if (frm.doc.program_ce && !frm.courses) {
            load_courses_for_program(frm);
        }
        if (!frm.doc.cei_si) {

            frm.add_custom_button("Create Sales Invoice(s)", function() {
                frm.call('get_inv_data_ce')
                    .then(r => {
                        frm.set_value("cei_si", 1);
                        frm.save();
                        frm.refresh();
                    })
                    .catch(e => {
                        frappe.msgprint("Error creating Sales Invoice(s)!");
                    });
            }).css({"color":"white", "background": "#0d3049", "font-weight": "700", "border-radius": "5px", "padding": "5px 10px", "margin-right": "10px"});};

        if (frm.doc.docstatus === 1 && !frm.doc.withdrawn && !frm.doc.withdrawal_request) {
            frm.add_custom_button(__("Request Withdrawal"), function() {
                frappe.model.with_doctype("Course Withdrawal Request", function() {
                    const wr = frappe.model.get_new_doc("Course Withdrawal Request");
                    wr.program_enrollment = frm.doc.program_ce;
                    wr.student = frm.doc.student_ce;
                    wr.course_enrollment_individual = frm.doc.name;
                    wr.withdrawal_scope = "Single Course";
                    frappe.set_route("Form", "Course Withdrawal Request", wr.name);
                });
            }).css({"color":"white", "background": "#0d3049", "font-weight": "700", "border-radius": "5px", "padding": "5px 10px", "margin-right": "10px"});
        }

    },
    program_ce(frm) {
        // Clear stale course selection when program changes
        frm.set_value("coursesc_ce", "");
        frm.courses = null;

        if (frm.doc.program_ce) {
            load_courses_for_program(frm);
        }
    },




    student_ce(frm) {
        frm.set_query("program_ce", function() {
            return {
                filters: {
                    student: frm.doc.student_ce
                }
            };
        });
    },
    coursesc_ce(frm) {

        frm.call('get_credits')
                .then(r => {
                        r.message = Number(r.message);
                        frm.set_value('credits', r.message);


                    });

    },


    on_submit(frm) {
        frm.call('get_credits2')
        .then(r => {
            if (r.message) {
                frm.credits = r.message;
                console.log("Credits: ", r.message);
            }
        }
    );

    }
});
