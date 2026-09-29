frappe.query_reports["Time-based Enrollment Gaps"] = {
	filters: [
		{
			fieldname: "academic_term",
			label: __("Academic Term"),
			fieldtype: "Link",
			options: "Academic Term",
			reqd: 1,
		},
		{
			fieldname: "program",
			label: __("Program"),
			fieldtype: "Link",
			options: "Program",
			get_query: () => ({ filters: { program_type: "Time-based" } }),
		},
		{
			fieldname: "gaps_only",
			label: __("Gaps only"),
			fieldtype: "Check",
			default: 1,
		},
	],

	get_datatable_options(options) {
		return Object.assign(options, { checkboxColumn: true });
	},

	onload(report) {
		report.page.add_inner_button(__("Enroll missing"), () => {
			const data = frappe.query_report.data || [];
			const checked = frappe.query_report.datatable.rowmanager
				.getCheckedRows()
				.map((i) => data[i])
				.filter((row) => row && row.gap);
			if (!checked.length) {
				frappe.msgprint(__("Tick the missing courses to enroll first."));
				return;
			}
			frappe
				.call({
					method: "seminary.seminary.doctype.bulk_course_enrollment.bulk_course_enrollment.new_run",
					args: {
						academic_term: frappe.query_report.get_filter_value("academic_term"),
						programs: [...new Set(checked.map((r) => r.program))],
						enrollments: [...new Set(checked.map((r) => r.program_enrollment))],
						courses: [...new Set(checked.map((r) => r.course))],
					},
					freeze: true,
				})
				.then((r) => frappe.set_route("Form", "Bulk Course Enrollment", r.message));
		});
	},
};
