// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

const FA_ROLES = ["Registrar", "Program Chair", "Seminary Manager", "System Manager"];

// Query-report rows are keyed by column.id (= the column label), so the
// "Roster" column's value lives under row.Roster. Fall back defensively.
function rosterOf(row) {
	return (row && (row.Roster || row.roster || row.name)) || null;
}

frappe.query_reports["Students At Attendance Risk"] = {
	// Row checkboxes so the registrar can act on selected students.
	get_datatable_options(options) {
		return Object.assign(options, { checkboxColumn: true });
	},

	onload(report) {
		const canFail = FA_ROLES.some((r) => (frappe.user_roles || []).includes(r));
		if (!canFail) return;

		report.page.add_inner_button(__("Fail for Absence"), () => {
			const rows = frappe.query_report.get_checked_items();
			if (!rows.length) {
				frappe.msgprint(__("Select at least one student (checkbox)."));
				return;
			}
			const names = rows.map(rosterOf).filter(Boolean);
			if (!names.length) {
				frappe.msgprint(__("Could not resolve the selected roster(s)."));
				return;
			}
			frappe.confirm(
				__("Fail {0} selected student(s) for unexcused absences? Their final grade becomes the FA code (Fail).", [names.length]),
				() => {
					frappe.dom.freeze(__("Failing..."));
					Promise.all(
						names.map((rosterName) =>
							frappe.call("seminary.seminary.api.fail_for_absence", { name: rosterName })
						)
					)
						.then(() => {
							frappe.dom.unfreeze();
							frappe.show_alert({ message: __("Done"), indicator: "orange" });
							report.refresh();
						})
						.catch(() => frappe.dom.unfreeze());
				}
			);
		});

		// Disciplinary action — only when enabled and an Attendance reason exists.
		Promise.all([
			frappe.db.get_single_value("Seminary Settings", "portal_disciplinary"),
			frappe.db.get_value("Disciplinary Reason", { category: "Attendance" }, "name"),
		]).then(([portalDisc, reasonRes]) => {
			const reason = reasonRes && reasonRes.message && reasonRes.message.name;
			if (!portalDisc || !reason) return;
			report.page.add_inner_button(__("Report Disciplinary Incident"), () => {
				const rows = frappe.query_report.get_checked_items();
				if (rows.length !== 1) {
					frappe.msgprint(__("Select exactly one student for a disciplinary incident."));
					return;
				}
				const rosterName = rosterOf(rows[0]);
				if (!rosterName) {
					frappe.msgprint(__("Could not resolve the selected roster."));
					return;
				}
				frappe.db
					.get_value("Scheduled Course Roster", rosterName, ["student", "program_std_scr"])
					.then((r) => {
						const v = (r && r.message) || {};
						frappe.db
							.get_value("Program Enrollment", { student: v.student, program: v.program_std_scr }, "name")
							.then((peRes) => {
								const pe = peRes && peRes.message && peRes.message.name;
								if (!pe) {
									frappe.msgprint(__("No Program Enrollment found for this student."));
									return;
								}
								frappe.route_options = { pe: pe, reason: reason };
								frappe.new_doc("Disciplinary Incident");
							});
					});
			});
		});
	},
};
