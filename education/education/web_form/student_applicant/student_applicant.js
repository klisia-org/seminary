
frappe.ready(function () {
	console.log("frappe.ready function executed");
	
	frappe.call("education.education.api.get_doctrinal_statement")
		.then(r => {
			if (r.message) {
				let dstatement = r.message;
				// Set the doctrinal statement in the web form
				setTimeout(() => {const doctrinalst = frappe.web_form.get_value("doctrinalst");
				console.log(dstatement);
				var doctrinalStatementDiv = $('<div>').html(dstatement);
				$("doctrinalst").append(doctrinalStatementDiv);
				
				
				frappe.web_form.set_value("ds2", dstatement);
				
				}, 2000);
				setTimeout(() => {ds2 = frappe.web_form.get_value("ds2");
				console.log(ds2);},3000);
				
				
			}
		});
	
				
			});



	
