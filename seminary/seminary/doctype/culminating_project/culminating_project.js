// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Culminating Project", {
	refresh(frm) {
		// Only offer active project types in the picker.
		frm.set_query("project_type", () => ({
			filters: { is_active: 1 },
		}));

		if (frm.is_new()) return;

		if (frm.doc.course_enrollment) {
			frm.add_custom_button(__("Open Course Enrollment"), () => {
				frappe.set_route(
					"Form",
					"Course Enrollment Individual",
					frm.doc.course_enrollment
				);
			});
		} else if (frm.doc.program_enrollment) {
			frm.add_custom_button(__("Enroll in Project Course"), () =>
				prompt_enroll_in_project_course(frm)
			);
		}
	},
});

function prompt_enroll_in_project_course(frm) {
	// Resolve the project type's backing course so we can scope the Course
	// Schedule picker to schedules that actually teach it.
	const get_backing_course = frm.doc.project_type
		? frappe.db.get_value("Culminating Project Type", frm.doc.project_type, "course")
		: Promise.resolve({ message: {} });

	Promise.resolve(get_backing_course).then((res) => {
		const backing_course = res && res.message && res.message.course;
		const cs_filters = backing_course ? { course: backing_course } : {};

		const d = new frappe.ui.Dialog({
			title: __("Enroll in Project Course"),
			fields: [
				{
					fieldname: "course_schedule",
					fieldtype: "Link",
					label: __("Course Schedule"),
					options: "Course Schedule",
					reqd: 1,
					get_query: () => ({ filters: cs_filters }),
				},
			],
			primary_action_label: __("Enroll"),
			primary_action(values) {
				d.hide();
				frappe.call({
					method: "seminary.seminary.doctype.culminating_project.culminating_project.enroll_in_project_course",
					args: { name: frm.doc.name, course_schedule: values.course_schedule },
					freeze: true,
					freeze_message: __("Creating course enrollment..."),
					callback: (r) => {
						if (r.message && r.message.course_enrollment) {
							frappe.show_alert({
								message: __("Course enrollment {0} created.", [
									r.message.course_enrollment,
								]),
								indicator: "green",
							});
							frm.reload_doc();
						}
					},
				});
			},
		});
		d.show();
	});
}
