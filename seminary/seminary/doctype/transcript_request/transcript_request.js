// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt
// decisions/119 §5-6: holds and the fee are checked on submit; the registrar issues a printed copy.

frappe.ui.form.on("Transcript Request", {
	refresh(frm) {
		if (frm.is_new()) return;
		const issuer = ["Registrar", "Seminary Manager", "System Manager"].some((r) =>
			frappe.user_roles.includes(r)
		);
		const call = (method, args) =>
			frappe
				.call(`seminary.seminary.transcripts.${method}`, { name: frm.doc.name, ...args })
				.then(() => frm.reload_doc());
		if (frm.doc.status === "Ready" && issuer) {
			frm.add_custom_button(__("Issue"), () => call("issue")).addClass("btn-primary");
		}
		if (["On Hold", "Awaiting Payment", "Draft"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Check Again"), () => call("recheck"));
		}
		if (
			issuer &&
			frm.doc.charges &&
			!frm.doc.fee_waived &&
			!["Issued", "Cancelled"].includes(frm.doc.status)
		) {
			frm.add_custom_button(__("Waive Fee"), () =>
				frappe.prompt(
					{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
					(v) => call("waive_fee", { reason: v.reason }),
					__("Waive Transcript Fee")
				)
			);
		}
		if (!["Issued", "Cancelled"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Cancel Request"), () =>
				frappe.prompt(
					{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason") },
					(v) => call("cancel_request", { reason: v.reason }),
					__("Cancel Transcript Request")
				)
			);
		}
		if (frm.doc.verification_code) {
			frm.set_intro(
				__("Verification code {0}. Anyone can confirm it at {1}.", [
					frm.doc.verification_code,
					`${window.location.origin}/transcript-verify?code=${frm.doc.verification_code}`,
				]),
				"blue"
			);
		}
	},
});
