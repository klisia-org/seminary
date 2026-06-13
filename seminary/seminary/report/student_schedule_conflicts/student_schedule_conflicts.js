// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

// ADR 050: registrar worksheet for student schedule double-bookings. Conflicts
// are never blocked at enrollment — this is where the registrar resolves them.
const RESOLVE_ROLES = ["Registrar", "Program Chair", "Seminary Manager", "System Manager"];

// Script-report rows are keyed by fieldname; fall back defensively.
function ceiOf(row) {
	return (row && (row.enrollment || row.Enrollment || row.name)) || null;
}

frappe.query_reports["Student Schedule Conflicts"] = {
	filters: [
		{
			fieldname: "academic_term",
			label: __("Academic Term"),
			fieldtype: "Link",
			options: "Academic Term",
		},
		{
			fieldname: "submitted_only",
			label: __("Submitted involved only"),
			fieldtype: "Check",
		},
	],

	// Highlight the rows that involve a rostered (Submitted) enrollment.
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (data && data.alert) {
			return `<span style="color: var(--red-600); font-weight: 600;">${formatted}</span>`;
		}
		return formatted;
	},

	get_datatable_options(options) {
		return Object.assign(options, { checkboxColumn: true });
	},

	onload(report) {
		const canResolve = RESOLVE_ROLES.some((r) => (frappe.user_roles || []).includes(r));
		if (!canResolve) return;

		report.page.add_inner_button(__("Resolve Selected"), () => {
			const rows = frappe.query_report.get_checked_items();
			if (!rows.length) {
				frappe.msgprint(__("Select the enrollment(s) to drop (checkbox)."));
				return;
			}
			const ceis = rows.map(ceiOf).filter(Boolean);
			if (!ceis.length) {
				frappe.msgprint(__("Could not resolve the selected enrollment(s)."));
				return;
			}
			frappe.confirm(
				__("Resolve {0} selected enrollment(s)? Drafts are deleted and unpaid seats released; rostered or paid enrollments are routed to a Withdrawal Request.", [ceis.length]),
				() => {
					frappe.dom.freeze(__("Resolving..."));
					Promise.all(
						ceis.map((cei) =>
							frappe
								.call("seminary.seminary.api.resolve_schedule_conflict", { cei_name: cei })
								.then((r) => ({ cei, res: (r && r.message) || {} }))
								.catch(() => ({ cei, res: { success: false } }))
						)
					).then((results) => {
						frappe.dom.unfreeze();
						const needWithdrawal = results.filter((x) => x.res && x.res.action === "withdrawal");
						if (needWithdrawal.length === 1) {
							frappe.show_alert({ message: __("Routing to Withdrawal Request"), indicator: "blue" });
							routeToWithdrawal(needWithdrawal[0].cei);
							return;
						}
						if (needWithdrawal.length > 1) {
							frappe.msgprint(
								__("{0} rostered/paid enrollment(s) need a Withdrawal Request — open each and file one.", [needWithdrawal.length])
							);
						}
						frappe.show_alert({ message: __("Done"), indicator: "green" });
						report.refresh();
					});
				}
			);
		});
	},
};

// Open a Withdrawal Request prefilled for a rostered/paid enrollment, keeping
// the financial and grade audit trail (mirrors the CEI form's withdrawal button).
function routeToWithdrawal(cei) {
	frappe.db
		.get_value("Course Enrollment Individual", cei, ["student_ce", "program_ce"])
		.then((r) => {
			const v = (r && r.message) || {};
			frappe.model.with_doctype("Withdrawal Request", () => {
				const wr = frappe.model.get_new_doc("Withdrawal Request");
				wr.program_enrollment = v.program_ce;
				wr.student = v.student_ce;
				wr.course_enrollment_individual = cei;
				wr.withdrawal_scope = "Single Course";
				frappe.set_route("Form", "Withdrawal Request", wr.name);
			});
		});
}
