// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Student', {
	refresh: function(frm) {
		frm.set_query("user", function (doc) {
			return {
				filters: {
					ignore_user_type: 1,
				},
			};  
		});

		if(!frm.is_new()) {
			frm.add_custom_button(__('Accounting Ledger'), function() {
				frappe.set_route('query-report', 'General Ledger',
					{party_type:'Customer', party:frm.doc.customer});
			});
		};
	},
		

		
	
/* 	frm.add_custom_button('Get Program Enrollments', function() {
			
		frappe.call({
			method:"education.education.doctype.student.get_pgmenrollments", 
			args: {
				doc: frm.doc}
		.then(r => {
				
				if (r.message) {
					var enrollments = r.message;
					var table = "<table><thead><tr><th>Program</th><th>Active</th><th>Enrollment Date</th><th>Conclusion Date</th></tr></thead><tbody>";
					if (enrollments.length > 0) {
						for (var i = 0; i < enrollments.length; i++) {
							table += "<tr><td>" + enrollments[i].program + "</td><td>" + enrollments[i].pgmenrol_active + "</td></tr>" + enrollments[i].enrollment_date + "</td></tr>" + enrollments[i].date_of_conclusion + "</td></tr>";
						}
					} else {
						table += "<tr><td colspan='4'>No enrollments found</td></tr>";
					}
					table += "</tbody></table>";
						// Set the 'options' property of the 'pe_html' field to the HTML string
					frm.set_df_property('pe_html', 'options', table);
					frm.refresh_field('pe_html');
				}
			})
		});
		}); */

		onload: function(frm) {
			if (frm.doc.enabled) {
				frappe.call({
					method: "education.education.api.get_pgmenrollments",
					args: {
						name: frm.doc.name
					},
					callback: function(r) {
						if (r.message) {
							var enrollments = r.message;
							var table = "<style>table { width: 100%; border-collapse: collapse; } th, td { border: 1px solid #0d3049; padding: 8px; text-align: left; } </style>";
							table += "<table><thead><tr><th>Program</th><th>Active</th><th>Enrollment Date</th><th>Conclusion Date</th></tr></thead><tbody>";
							for (var i = 0; i < enrollments.length; i++) {
								var activeStatus = enrollments[i].pgmenrol_active ? "Yes" : "No";
								var conclusionDate = enrollments[i].date_of_conclusion ? enrollments[i].date_of_conclusion : " ";
								table += "<tr><td>" + enrollments[i].program + "</td><td>" + activeStatus + "</td><td>" + enrollments[i].enrollment_date + "</td><td>" + conclusionDate + "</td></tr>";
							}
							table += "</tbody></table>";
							frm.set_df_property('pe_html', 'options', table);
							frm.refresh_field('pe_html');
						} else {
							frm.set_df_property('pe_html', 'options', "No enrollments found");
							frm.refresh_field('pe_html');
						}
					}
				});
			} else {
				frm.set_df_property('pe_html', 'options', "No enrollments found");
				frm.refresh_field('pe_html');
			};
		}},
				
	

/* 
frappe.ui.form.on('Student Guardian', {
	guardians_add: function(frm){
		frm.fields_dict['guardians'].grid.get_field('guardian').get_query = function(doc){
			let guardian_list = [];
			if(!doc.__islocal) guardian_list.push(doc.guardian);
			$.each(doc.guardians, function(idx, val){
				if (val.guardian) guardian_list.push(val.guardian);
			});
			return { filters: [['Guardian', 'name', 'not in', guardian_list]] };
		};
	}*/
);