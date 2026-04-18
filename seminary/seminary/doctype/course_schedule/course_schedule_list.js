frappe.listview_settings['Course Schedule'] = {
	onload: function(listview) {
		listview.page.add_actions_menu_item(__("Close Enrollment"), function() {
			const docs = listview.get_checked_items();
			if (!docs.length) {
				frappe.msgprint(__("Please select at least one Course Schedule."));
				return;
			}
			const names = docs.map(d => d.name);
			frappe.confirm(
				__("Close enrollment on {0} Course Schedule(s)?", [names.length]),
				() => {
					frappe.call({
						method: "seminary.seminary.doctype.course_schedule.course_schedule.bulk_close_enrollment",
						args: { names: names },
						freeze: true,
						freeze_message: __("Closing enrollment..."),
						callback: (r) => {
							const res = r.message || {};
							frappe.show_alert({
								message: __("Closed {0}, skipped {1}.", [
									(res.closed || []).length,
									(res.skipped || []).length,
								]),
								indicator: "green",
							});
							listview.refresh();
						},
					});
				}
			);
		});
	}
};
