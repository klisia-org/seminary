// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Course Enrollment Individual", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Course Enrollment Individual", {
    onload(frm) {
              

        frappe.db.get_single_value('Education Settings', 'allow_audit')
            .then(value => {
                if (value === 1) {
                    frm.toggle_display('audit', true);
                } else {
                    frm.toggle_display('audit', false);
                }
            })
            .catch(error => {
                console.log('Error occurred while fetching Education Settings:', error);
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
            if (frm.doc.no_prereq === 1 || frm.doc.audit === 1) {
                // Return unfiltered results
                return {
                    filters: {
                        open_enroll: 1
                    }
                };
            } 
            else {
              //if frm.courses is empty, trigger get_courses
            if (!frm.courses) {
                frm.trigger('get_courses')
                console.log("Triggered get_courses");
            } return {
                
                filters: {
                    course: ["in", frm.courses]
                }             
            }}
           
            
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

        
                
            
       
      /* This needs to be fixed for webform only  
       frm.call('get_user')
        .then(r => {    
            if (r.message) {
                frm.set_value('user', r.message);
            }
        }); */
        
    },
    program_ce(frm) {
        frm.set_query("student_ce", function() {
            return {
                filters: {
                program: frm.doc.program_ce
            }
            };
        });
        frm.trigger('get_courses');
    },
    
    get_courses(frm) {
        frappe.call({
        method: "education.education.api.courses_for_student",
        args: {
            
            program_ce: frm.doc.program_ce
            },
            callback: function(response) {
                // Store the list of courses in a variable
                frm.courses = response.message;
            }})},
    
        
        
    
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
