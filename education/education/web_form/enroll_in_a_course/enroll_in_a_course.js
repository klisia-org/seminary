frappe.ready(() => {
    // bind events here
    frappe.web_form.after_load = setTimeout(function() {
        frappe.call('get_context', self).then(r => {
            student = r.message;
            frappe.web_form.set_value('student_ce', student);

            
        });
    }, 2000); // 2 seconds delay
});
