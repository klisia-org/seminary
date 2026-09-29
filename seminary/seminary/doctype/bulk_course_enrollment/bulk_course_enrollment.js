// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bulk Course Enrollment", {
	setup(frm) {
		// A Table MultiSelect has no grid: its link filter is set on the field
		// itself, not as a child-table query.
		frm.set_query("programs", () => ({
			filters: { program_type: "Time-based", staff_enroll_only: 1 },
		}));
		frm.set_query("course_schedule", "courses", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				filters: {
					course: row.course,
					academic_term: doc.academic_term,
					workflow_state: "Open for Enrollment",
				},
			};
		});
		frappe.realtime.on("bulk_course_enrollment_done", (data) => {
			if (data && data.name === frm.doc.name) {
				frm.reload_doc();
				frappe.show_alert({ message: data.summary, indicator: "green" });
			}
		});
	},

	refresh(frm) {
		const billing = frm.doc.__onload && frm.doc.__onload.has_financials;
		frm.fields_dict.courses.grid.update_docfield_property("charges", "hidden", !billing);
		frm.fields_dict.courses.grid.update_docfield_property(
			"charges",
			"in_list_view",
			billing ? 1 : 0
		);
		frm.fields_dict.courses.grid.refresh();

		const busy = ["Queued", "Running"].includes(frm.doc.run_status);
		const colors = {
			Draft: "gray",
			Queued: "blue",
			Running: "blue",
			Completed: "green",
			"Completed with Errors": "orange",
		};
		frm.page.set_indicator(__(frm.doc.run_status), colors[frm.doc.run_status] || "gray");
		if (busy) {
			frm.set_intro(
				__("Enrolling in the background. The results appear here when it finishes."),
				"blue"
			);
		}
		if (frm.is_new() || busy) return;

		frm.add_custom_button(__("Get Students"), () => run(frm, "get_students"));
		frm.add_custom_button(__("Get Courses"), () => run(frm, "get_courses"));
		frm.add_custom_button(__("Enroll"), () => confirm_enroll(frm)).addClass("btn-primary");
	},
});

const METHODS = "seminary.seminary.doctype.bulk_course_enrollment.bulk_course_enrollment.";

function run(frm, method) {
	const call = () =>
		frappe
			.call({ method: METHODS + method, args: { name: frm.doc.name }, freeze: true })
			.then(() => frm.reload_doc());
	return frm.is_dirty() ? frm.save().then(call) : call();
}

function confirm_enroll(frm) {
	const students = (frm.doc.students || []).filter((r) => r.include).length;
	const courses = (frm.doc.courses || []).filter((r) => r.include && r.course_schedule);
	const no_section = (frm.doc.courses || []).filter((r) => r.include && !r.course_schedule);
	let message = __("Enroll {0} students in {1} course sections?", [students, courses.length]);
	if (no_section.length) {
		message +=
			"<br><br>" +
			__("{0} courses have no section and will be skipped: {1}", [
				no_section.length,
				no_section.map((r) => frappe.utils.escape_html(r.course)).join(", "),
			]);
	}
	message +=
		"<br><br>" +
		__(
			"Payment rules, prerequisites and seat limits apply as for a single enrollment. A full section puts students on its waitlist."
		);
	frappe.confirm(message, () => {
		const go = () =>
			frappe
				.call({ method: METHODS + "enroll", args: { name: frm.doc.name }, freeze: true })
				.then((r) => {
					frappe.show_alert({
						message: __("{0} enrollments queued.", [r.message]),
						indicator: "blue",
					});
					frm.reload_doc();
				});
		frm.is_dirty() ? frm.save().then(go) : go();
	});
}
