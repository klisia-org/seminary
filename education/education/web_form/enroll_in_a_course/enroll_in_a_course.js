frappe.ready(() => {
    // bind events here
    frappe.web_form.after_load = setTimeout(function() {
        frappe.call('get_student_name', self).then(r => {
            const student = r.message;
            console.log("Student: ", student);
            frappe.web_form.set_value('student_ce', student);       
        });
    }, 2000); // 2 seconds delay
});
