frappe.listview_settings['Course'] = {
	onload: function(listview) {
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
