// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt
// decisions/119 §3: the registrar approves, and a second approver after the set number of days.

frappe.ui.form.on("Grade Change Request", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status !== "Open") return;
		const roles = frappe.user_roles;
		const registrar = ["Registrar", "Seminary Manager", "System Manager"].some((r) =>
			roles.includes(r)
		);
		const second =
			frm.doc.needs_second_approval &&
			frm.doc.registrar_approved_by &&
			!frm.doc.second_approved_by &&
			roles.includes(frm.doc.second_approver_role) &&
			frm.doc.registrar_approved_by !== frappe.session.user;
		if ((registrar && !frm.doc.registrar_approved_by) || second) {
			frm.add_custom_button(__("Approve"), () => {
				frappe.prompt(
					{ fieldname: "note", fieldtype: "Small Text", label: __("Note") },
					(v) =>
						frappe
							.call("seminary.seminary.grade_changes.approve", {
								name: frm.doc.name,
								note: v.note,
							})
							.then(() => frm.reload_doc()),
					__("Approve Grade Change")
				);
			});
		}
		if (registrar || second) {
			frm.add_custom_button(__("Reject"), () => {
				frappe.prompt(
					{ fieldname: "note", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
					(v) =>
						frappe
							.call("seminary.seminary.grade_changes.reject", {
								name: frm.doc.name,
								note: v.note,
							})
							.then(() => frm.reload_doc()),
					__("Reject Grade Change")
				);
			});
		}
		if (registrar || frm.doc.owner === frappe.session.user) {
			frm.add_custom_button(__("Withdraw"), () =>
				frappe
					.call("seminary.seminary.grade_changes.withdraw", { name: frm.doc.name })
					.then(() => frm.reload_doc())
			);
		}
	},
	roster(frm) {
		frm.set_query("assessment", "changes", () => ({
			filters: { parent: frm.doc.course_schedule },
		}));
	},
	onload(frm) {
		frm.set_query("assessment", "changes", () => ({
			filters: { parent: frm.doc.course_schedule },
		}));
		frm.set_query("roster", () => ({ filters: { active: 0, audit_bool: 0 } }));
	},
});
