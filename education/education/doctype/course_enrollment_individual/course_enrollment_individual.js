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
        frm.set_query("coursesc_ce", () => {
            return {
                query: "education.education.education.course_enrollment_individual.courses_for_student",
                filters: {
                    coursesc_ce: "courses"
                }
            };
            
        });
    },
    
    submit() {
        frappe.call('make_copies')
            .then(r => {
            frappe.msgprint('Course Enrollment has been submitted');
               })
            .catch(error => {
                console.log('Error occurred with make_copies:', error);
                });
            },});
