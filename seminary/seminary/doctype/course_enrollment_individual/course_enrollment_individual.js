// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Course Enrollment Individual", {
// 	refresh(frm) {

// 	},
// });
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
            if (!frm.doc.program_ce) {
                // No program selected — show nothing
                return { filters: { name: "" } };
            }
            if (frm.doc.no_prereq === 1 || frm.doc.audit === 1) {
                return { filters: { open_enroll: 1 } };
            }
            if (frm.courses && frm.courses.length) {
                return { filters: { course: ["in", frm.courses], open_enroll: 1 } };
            }
            // Courses not loaded yet — show nothing until get_courses resolves
            return { filters: { name: "" } };
        });
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



      /* This needs to be fixed for webform only
       frm.call('get_user')
        .then(r => {
            if (r.message) {
                frm.set_value('user', r.message);
            }
        }); */

    },
    program_ce(frm) {
        // Clear stale course selection when program changes
        frm.set_value("coursesc_ce", "");
        frm.courses = null;

        if (frm.doc.program_ce) {
            frm.trigger("get_courses");
        }
    },

    get_courses(frm) {
        if (!frm.doc.program_ce) return;
        frappe.call({
            method: "seminary.seminary.api.courses_for_student",
            args: { program_ce: frm.doc.program_ce },
            callback: function (response) {
                frm.courses = response.message;
                // Refresh the query now that courses are loaded
                frm.refresh_field("coursesc_ce");
            },
        });
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
