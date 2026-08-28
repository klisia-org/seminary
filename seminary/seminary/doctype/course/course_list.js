frappe.listview_settings['Course'] = {
	onload: function(listview) {
		// Competency counts are not Course fields — they live one query away, in
		// Course Competency — so they cannot be a list column. The report shows
		// them for every course at once, which is what the list view is being
		// asked for here.
		listview.page.add_menu_item(__("Competency Coverage"), function() {
			// Carry the list's own academic unit across so the report opens on
			// the same slice of courses the user was already looking at.
			const options = {};
			const unit = listview.get_filter_value("academic_unit");
			if (unit) options.academic_unit = unit;
			frappe.set_route("query-report", "Course Competency Coverage", options);
		});

		listview.page.add_actions_menu_item(__("Add to Program"), function() {
			const docs = listview.get_checked_items();
			if (!docs.length) {
				frappe.msgprint(__("Please select at least one Course."));
				return;
			}
			const names = docs.map(d => d.name);
			frappe.prompt(
				[
					{
						fieldname: "program",
						label: __("Program"),
						fieldtype: "Link",
						options: "Program",
						reqd: 1,
					},
					{
						fieldname: "mandatory",
						label: __("Is Mandatory"),
						fieldtype: "Check",
					},
				],
				(data) => {
					frappe.call({
						method: "seminary.seminary.doctype.course.course.bulk_add_courses_to_program",
						args: {
							courses: names,
							program: data.program,
							mandatory: data.mandatory,
						},
						freeze: true,
						freeze_message: __("Adding courses to program..."),
						callback: (r) => {
							const res = r.message || {};
							frappe.show_alert({
								message: __("Added {0}, skipped {1}.", [
									(res.added || []).length,
									(res.skipped || []).length,
								]),
								indicator: "green",
							});
							listview.refresh();
						},
					});
				},
				__("Add {0} Course(s) to Program", [names.length]),
				__("Add")
			);
		});
	},
};
