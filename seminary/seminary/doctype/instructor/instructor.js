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

		render_open_commitments(frm);

		if (!frm.is_new() && frm.doc.instructor_type === "Volunteer" && !frm.doc.supplier) {
			frm.add_custom_button(__("Create Supplier"), function() {
				frm.call({
					method: "create_supplier",
					doc: frm.doc,
				}).then(() => frm.reload_doc());
			}, __("Actions"));
		}

		if (!frm.is_new() && frm.doc.employee) {
			frappe.db.get_single_value("Seminary Settings", "hrms_enable").then((enabled) => {
				if (!enabled) return;

				frm.add_custom_button(__("Pull from Employee"), function() {
					frappe.confirm(
						__("Replace the current Education table with Employee's education? Seminary-only fields on existing rows will be lost."),
						() => frm.call({
							method: "pull_education_from_employee",
							doc: frm.doc,
						}).then(() => frm.reload_doc())
					);
				}, __("Education"));

				frm.add_custom_button(__("Push to Employee"), function() {
					frappe.confirm(
						__("Overwrite Employee's education with this table? Accreditation-only fields are not copied."),
						() => frm.call({
							method: "push_education_to_employee",
							doc: frm.doc,
						}).then(() => frm.reload_doc())
					);
				}, __("Education"));
			});
		}

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
		if (!frm.is_new()) {
			frm.call({method: "seminary.seminary.doctype.instructor.instructor.update_instructorlog", args: {doc: name}});
		}
		console.log("Instructor Log updated");
		frm.refresh();
			}

	}
);

// What this instructor is still carrying — open sections, cohorts they lead,
// culminating projects they advise (ADR 066 §7.1). The registrar's answer to
// "what happens if they go on sabbatical", visible before the question is
// urgent. Nothing here is closed automatically; who takes a group over is a
// decision, not a consequence.
function render_open_commitments(frm) {
	const wrapper = frm.fields_dict.open_commitments_html;
	if (!wrapper) return;
	if (frm.is_new()) {
		wrapper.$wrapper.empty();
		return;
	}
	frappe.call({
		method: 'seminary.seminary.instructor_load.instructor_commitments',
		args: { instructor: frm.doc.name },
		callback: function(r) {
			const res = r.message || {};
			wrapper.$wrapper.html(
				res.html || `<p class="text-muted">${__('Nothing currently assigned.')}</p>`
			);
		},
	});
}
