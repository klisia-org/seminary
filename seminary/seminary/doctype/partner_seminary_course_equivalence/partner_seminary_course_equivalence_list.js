frappe.listview_settings["Partner Seminary Course Equivalence"] = {
	onload(listview) {
		if (!frappe.user.has_role("System Manager")) return;

		const btn = listview.page.add_inner_button(
			__("Create Legacy Integration"),
			() => promptCreateLegacyIntegration(listview)
		);
		btn.attr(
			"title",
			__(
				"Use this if course names were not changed during the migration. Otherwise, it requires course-by-course input."
			)
		);
	},
};

function promptCreateLegacyIntegration(listview) {
	const d = new frappe.ui.Dialog({
		title: __("Create Legacy Integration"),
		fields: [
			{
				label: __("Legacy Partner Seminary"),
				fieldname: "partner_seminary",
				fieldtype: "Link",
				options: "Partner Seminary",
				reqd: 1,
				get_query: () => ({ filters: { is_internal_legacy: 1 } }),
			},
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			d.hide();
			frappe.call({
				method:
					"seminary.seminary.doctype.partner_seminary_course_equivalence.partner_seminary_course_equivalence.create_legacy_integration",
				args: { partner_seminary: values.partner_seminary },
				freeze: true,
				freeze_message: __("Creating legacy equivalences..."),
				callback: (r) => {
					const res = r.message || {};
					frappe.msgprint({
						title: __("Legacy Integration"),
						message: __(
							"Created {0} equivalence(s); skipped {1} already in place.",
							[res.created || 0, res.skipped || 0]
						),
					});
					listview.refresh();
				},
			});
		},
	});
	d.show();
}
