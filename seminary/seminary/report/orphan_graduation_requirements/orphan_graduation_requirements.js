// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

const ACTION_ROLES = ["Registrar", "Program Chair", "Seminary Manager", "System Manager"];

// Query-report rows may be keyed by fieldname or by column label depending on
// the datatable build — read defensively.
function valOf(row, fieldname, label) {
	if (!row) return null;
	if (row[fieldname] != null) return row[fieldname];
	if (label && row[label] != null) return row[label];
	return null;
}

function selectedPairs() {
	return (frappe.query_report.get_checked_items() || [])
		.map((r) => ({
			pe: valOf(r, "program_enrollment", "Program Enrollment"),
			sgr: valOf(r, "sgr", "SGR"),
			linked_doc: valOf(r, "linked_doc", "Linked Document"),
		}))
		.filter((p) => p.pe && p.sgr);
}

function runBatch(report, method, pairs, extraArgs) {
	frappe.dom.freeze(__("Working..."));
	Promise.all(
		pairs.map((p) =>
			frappe.call({
				method,
				args: Object.assign(
					{ program_enrollment: p.pe, sgr_name: p.sgr },
					extraArgs || {}
				),
			})
		)
	)
		.then(() => {
			frappe.dom.unfreeze();
			frappe.show_alert({ message: __("Done"), indicator: "green" });
			report.refresh();
		})
		.catch(() => frappe.dom.unfreeze());
}

frappe.query_reports["Orphan Graduation Requirements"] = {
	get_datatable_options(options) {
		return Object.assign(options, { checkboxColumn: true });
	},

	onload(report) {
		const canAct = ACTION_ROLES.some((r) => (frappe.user_roles || []).includes(r));
		if (!canAct) return;

		report.page.add_inner_button(__("Cancel Requirement"), () => {
			const pairs = selectedPairs();
			if (!pairs.length) {
				frappe.msgprint(__("Select at least one row (checkbox)."));
				return;
			}
			frappe.confirm(
				__("Remove {0} selected orphan requirement(s) from the student snapshot?", [
					pairs.length,
				]),
				() =>
					runBatch(
						report,
						"seminary.seminary.graduation.cancel_orphan_requirement",
						pairs
					)
			);
		});

		report.page.add_inner_button(__("Waive"), () => {
			const pairs = selectedPairs();
			if (!pairs.length) {
				frappe.msgprint(__("Select at least one row (checkbox)."));
				return;
			}
			frappe.prompt(
				{
					fieldname: "reason",
					fieldtype: "Small Text",
					label: __("Waiver reason"),
					reqd: 1,
				},
				(values) =>
					runBatch(report, "seminary.seminary.graduation.waive_sgr", pairs, {
						reason: values.reason,
					}),
				__("Waive {0} requirement(s)", [pairs.length])
			);
		});

		report.page.add_inner_button(__("Withdraw Linked Document"), () => {
			const pairs = selectedPairs().filter((p) => p.linked_doc);
			if (!pairs.length) {
				frappe.msgprint(
					__("Select at least one row whose requirement has a linked document.")
				);
				return;
			}
			frappe.confirm(
				__("Withdraw the linked document for {0} selected row(s) and drop the requirement?", [
					pairs.length,
				]),
				() =>
					runBatch(
						report,
						"seminary.seminary.graduation.withdraw_orphan_requirement",
						pairs
					)
			);
		});
	},
};
