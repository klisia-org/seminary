// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt
// decisions/119 §1: the registrar decides; the instructor gives an opinion.

frappe.ui.form.on("Incomplete Extension Request", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status !== "Open") return;
		const registrar = ["Registrar", "Seminary Manager", "System Manager"].some((r) =>
			frappe.user_roles.includes(r)
		);
		if (!registrar) return;
		frm.add_custom_button(__("Approve"), () => {
			frappe.prompt(
				{ fieldname: "note", fieldtype: "Small Text", label: __("Note") },
				(v) =>
					frappe
						.call("seminary.seminary.incompletes.approve_extension", {
							name: frm.doc.name,
							note: v.note,
						})
						.then(() => frm.reload_doc()),
				__("Approve Extension")
			);
		});
		frm.add_custom_button(__("Decline"), () => {
			frappe.prompt(
				{ fieldname: "note", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
				(v) =>
					frappe
						.call("seminary.seminary.incompletes.decline_extension", {
							name: frm.doc.name,
							note: v.note,
						})
						.then(() => frm.reload_doc()),
				__("Decline Extension")
			);
		});
	},
});
