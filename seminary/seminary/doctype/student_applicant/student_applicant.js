// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Student Applicant", {

	refresh: function(frm) {
		frm.set_query('academic_term', function(doc, cdt, cdn) {
			return{
				filters: {
					'academic_year': frm.doc.academic_year
				}
			};
		});

		if (!frm.is_new() && frm.doc.application_status==="Applied") {
			frm.add_custom_button(__("Approve"), function() {
				frm.set_value("application_status", "Approved");
				frm.save_or_update();

			}, 'Actions');

			frm.add_custom_button(__("Reject"), function() {
				frm.set_value("application_status", "Rejected");
				frm.save_or_update();
			}, 'Actions');
		}

		if (!frm.is_new() && frm.doc.application_status === "Approved") {
			frm.add_custom_button(__("Enroll"), function() {
				frm.events.enroll(frm)
			});

			frm.add_custom_button(__("Reject"), function() {
				frm.set_value("application_status", "Rejected");
				frm.save_or_update();
			}, 'Actions');
		}

		if (!frm.is_new() && frm.doc.application_status === "Rejected") {
			frm.add_custom_button(__("Approve"), function() {
				frm.set_value("application_status", "Approved");
				frm.save_or_update();
			}, 'Actions');
		}

		frappe.realtime.on("enroll_student_progress", function(data) {
			if(data.progress) {
				frappe.hide_msgprint(true);
				frappe.show_progress(__("Enrolling student"), data.progress[0],data.progress[1]);
			}
		});

		bind_tax_id(frm);

	},

	// Nationality decides which document is wanted, falling back to the single
	// country column — an applicant has no Person yet, so no mailing country
	// (ADR 071).
	nationality: function(frm) {
		bind_tax_id(frm);
	},

	country: function(frm) {
		bind_tax_id(frm);
	},

	enroll: function(frm) {
		frappe.model.open_mapped_doc({
			method: "seminary.seminary.api.enroll_student",
			frm: frm
		})
	}
});

// Shared with the Person and Partner Organization forms, and with the public
// application form: public/js/tax_id.bundle.js.
function bind_tax_id(frm) {
	window.seminary?.bindTaxIdField(frm, {
		country_fields: ["nationality", "country"],
		subject: "person",
	});
}
