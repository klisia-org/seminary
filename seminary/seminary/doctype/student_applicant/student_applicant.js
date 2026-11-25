// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Student Applicant", {
	refresh: function (frm) {
		frm.set_query("academic_term", function (doc, cdt, cdn) {
			return {
				filters: {
					academic_year: frm.doc.academic_year,
				},
			};
		});

		if (!frm.is_new()) add_admission_actions(frm);

		frappe.realtime.on("enroll_student_progress", function (data) {
			if (data.progress) {
				frappe.hide_msgprint(true);
				frappe.show_progress(__("Enrolling student"), data.progress[0], data.progress[1]);
			}
		});

		bind_tax_id(frm);
	},

	// Nationality decides which document is wanted, falling back to the single
	// country column — an applicant has no Person yet, so no mailing country
	// (ADR 071).
	nationality: function (frm) {
		bind_tax_id(frm);
	},

	country: function (frm) {
		bind_tax_id(frm);
	},

	enroll: function (frm) {
		frappe.model.open_mapped_doc({
			method: "seminary.seminary.api.enroll_student",
			frm: frm,
		});
	},
});

// Shared with the Person and Partner Organization forms, and with the public
// application form: public/js/tax_id.bundle.js.
function bind_tax_id(frm) {
	window.seminary?.bindTaxIdField(frm, {
		country_fields: ["nationality", "country"],
		subject: "person",
	});
}

// Admission (decisions/112): status follows the decision, so the form offers
// the next step instead of status buttons.
function add_admission_actions(frm) {
	frappe
		.call("seminary.seminary.admissions.form_state", { applicant: frm.doc.name })
		.then((r) => {
			const state = r.message || {};
			const status = frm.doc.application_status;
			if (status === "Applied") {
				if ((state.missing || []).length) {
					frm.dashboard.set_headline(
						__("Review starts when these are in: {0}", [
							state.missing.map(frappe.utils.escape_html).join(", "),
						])
					);
				}
				frm.add_custom_button(__("Check and Start Review"), () =>
					frappe
						.call("seminary.seminary.admissions.check_now", {
							applicant: frm.doc.name,
						})
						.then(() => frm.reload_doc())
				);
			}
			if (state.claimed && ["In Review", "Waitlisted"].includes(status)) {
				frm.dashboard.set_headline(
					__("This application is decided by {0}.", [
						frappe.utils.escape_html(state.claimed),
					])
				);
			}
			if (
				state.may_decide &&
				!state.claimed &&
				["In Review", "Waitlisted"].includes(status)
			) {
				frm.add_custom_button(__("Decide"), () =>
					frappe.new_doc("Admission Decision", { student_applicant: frm.doc.name })
				).addClass("btn-primary");
			}
			if (status === "Approved" && state.is_staff) {
				frm.add_custom_button(__("Enroll"), () => frm.events.enroll(frm)).addClass(
					"btn-primary"
				);
			}
			if (state.is_staff && !["Admitted", "Withdrawn"].includes(status)) {
				frm.add_custom_button(
					__("Withdraw"),
					() =>
						frappe.confirm(__("Withdraw this application?"), () =>
							frappe
								.call("seminary.seminary.admissions.withdraw", {
									applicant: frm.doc.name,
								})
								.then(() => frm.reload_doc())
						),
					__("Actions")
				);
			}
		});
}
