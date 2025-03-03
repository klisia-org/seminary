cur_frm.add_fetch("employee", "department", "department");
cur_frm.add_fetch("employee", "image", "image");

frappe.ui.form.on("Instructor", {
	employee: function(frm) {
		if (!frm.doc.employee) return;
		frappe.db.get_value("Employee", {name: frm.doc.employee}, "company", (d) => {
			frm.set_query("department", function() {
				return {
					"filters": {
						"company": d.company,
					}
				};
			});
			frm.set_query("department", "instructor_log", function() {
				return {
					"filters": {
						"company": d.company,
					}
				};
			});
		});
	},
	refresh: function(frm) {

	
	
		frm.set_query("employee", function(doc) {
			return {
				"filters": {
					"department": doc.department,
				}
			};
		});

		frm.set_query("academic_term", "instructor_log", function(_doc, cdt, cdn) {
			let d = locals[cdt][cdn];
			return {
				filters: {
					"academic_year": d.academic_year
				}
			};
		});

		// Example frontend code to debug heatmap data
	
		// console.log("Heatmap Data:", timeline_data);  // Add this line to verify the data being passed to the heatmap component


		frm.set_query("course", "instructor_log", function(_doc, cdt, cdn) {
			let d = locals[cdt][cdn];
			return {
				query: "seminary.seminary.doctype.program_enrollment.program_enrollment.get_program_courses",
				filters: {
					"program": d.program
				}
			};
		});
	},
	onload: function(frm) {
		let name = frm.doc.name;
		console.log(name);
		frm.call({method: "seminary.seminary.doctype.instructor.instructor.update_instructorlog", args: {doc: name}});
		console.log("Instructor Log updated");
		frm.refresh();
			}
		
	}	
);
