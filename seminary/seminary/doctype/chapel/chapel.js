// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Chapel", {
	setup(frm) {
		// A chaplain has no read on Contact; the team picker searches through
		// a gated endpoint instead (decisions/116 §5).
		frm.set_query("team_member_contact", "chapel_team", () => ({
			query: "seminary.seminary.chapel.search_contacts",
		}));
	},

	onload(frm) {
		// Seed the per-chapel sync default from the Seminary Settings master
		// toggle (the chaplain can still override it per service).
		if (frm.is_new() && !frm.doc.sync_with_google_calendar) {
			frappe.db
				.get_single_value("Seminary Settings", "sync_chapels_with_google_calendar")
				.then((v) => {
					if (v) frm.set_value("sync_with_google_calendar", 1);
				})
				.catch(() => {});
		}
	},

	refresh(frm) {
		if (!frm.is_new() && frm.doc.confirmed) {
			frm.add_custom_button(__("Take Roll"), () => take_roll(frm));
		}
	},
});

function take_roll(frm) {
	frappe
		.call("seminary.seminary.chapel.get_roll", { chapel: frm.doc.name })
		.then(({ message: rows }) => {
			const d = new frappe.ui.Dialog({
				title: __("Roll for {0}", [frm.doc.chapel_topic || frm.doc.name]),
				size: "large",
				fields: [
					{
						fieldtype: "HTML",
						options: `<p class="text-muted small">${__(
							"Excused can be marked ahead. Present is marked once the chapel has started. Clear a status to remove the record."
						)}</p>`,
					},
					{
						fieldname: "rows",
						fieldtype: "Table",
						// The roll lists the students it is taken for (decisions/116 §5).
						cannot_add_rows: true,
						cannot_delete_rows: true,
						in_place_edit: true,
						data: rows,
						fields: [
							{
								fieldname: "student",
								fieldtype: "Data",
								label: __("Student"),
								read_only: 1,
								in_list_view: 1,
								columns: 3,
							},
							{
								fieldname: "student_name",
								fieldtype: "Data",
								label: __("Name"),
								read_only: 1,
								in_list_view: 1,
								columns: 4,
							},
							{
								fieldname: "status",
								fieldtype: "Select",
								options: "\nPresent\nExcused",
								label: __("Status"),
								in_list_view: 1,
								columns: 2,
							},
							{
								fieldname: "method",
								fieldtype: "Data",
								label: __("Method"),
								read_only: 1,
								in_list_view: 1,
								columns: 1,
							},
						],
					},
				],
				primary_action_label: __("Save Roll"),
				primary_action(values) {
					frappe
						.call({
							method: "seminary.seminary.chapel.save_roll",
							args: {
								chapel: frm.doc.name,
								rows: (values.rows || []).map((r) => ({
									student: r.student,
									status: r.status || "",
								})),
							},
							freeze: true,
						})
						.then(() => {
							d.hide();
							frappe.show_alert({ message: __("Roll saved"), indicator: "green" });
						});
				},
			});
			d.show();
		});
}
