// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

const REX = "seminary.seminary.exceptions";

frappe.ui.form.on("Requirement Exception", {
	setup(frm) {
		frm.set_query("program_enrollment", () => ({ filters: { docstatus: 1 } }));
	},

	refresh(frm) {
		if (frm.is_new()) {
			frm.set_intro(
				__("Saving records this exception as approved by you."),
				"blue"
			);
			return;
		}
		const call = (method, args) =>
			frappe
				.call({ method: `${REX}.${method}`, args: Object.assign({ name: frm.doc.name }, args) })
				.then(() => frm.reload_doc());

		if (frm.doc.status === "Requested") {
			frm.add_custom_button(__("Approve"), () =>
				decisionDialog(__("Approve"), (note) => call("decide", { approve: 1, note }))
			);
			frm.add_custom_button(__("Deny"), () =>
				decisionDialog(__("Deny"), (note) => call("decide", { approve: 0, note }), true)
			);
			if (frm.doc.requested_by === frappe.session.user) {
				frm.add_custom_button(__("Withdraw"), () => call("withdraw"));
			}
		}
		if (frm.doc.status === "Approved") {
			frm.add_custom_button(__("Revoke"), () =>
				decisionDialog(__("Revoke"), (note) => call("revoke", { note }), true)
			);
		}
	},
});

function decisionDialog(title, action, noteRequired) {
	frappe.prompt(
		{
			fieldname: "note",
			fieldtype: "Small Text",
			label: __("Decision note"),
			reqd: noteRequired ? 1 : 0,
		},
		(values) => action(values.note),
		title,
		title
	);
}
