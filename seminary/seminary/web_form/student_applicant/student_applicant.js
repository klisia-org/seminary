frappe.ready(function () {
    console.log("frappe.ready function executed");

    frappe.call("seminary.seminary.api.active_term")
        .then(r => {
            if (r.message) {
                let at = r.message.academic_term;
                let ay = r.message.academic_year;
                // Set the active term and academic year in the web form
                console.log("Academic Term: " + at);
                console.log("Academic Year: " + ay);
                frappe.web_form.set_value("academic_term", at);
                frappe.web_form.set_value("academic_year", ay);
            }
        });

    frappe.call("seminary.seminary.api.get_doctrinal_statement")
        .then(r => {
            if (r.message) {
                let dstatement = r.message;
                // Set the doctrinal statement in the web form
                setTimeout(() => {
                    const doctrinalst = frappe.web_form.get_value("doctrinalst");
                    console.log(dstatement);
                    var doctrinalStatementDiv = $('<div>').html(dstatement);
                    $("doctrinalst").append(doctrinalStatementDiv);
                    frappe.web_form.set_value("ds2", dstatement);
                }, 2000);
                setTimeout(() => {
                    let ds2 = frappe.web_form.get_value("ds2");
                    console.log(ds2);
                }, 3000);
            }
        });
});




