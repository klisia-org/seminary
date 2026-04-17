// Copyright (c) 2026, Klisia, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Student Balance", {
	refresh: function (frm) {
		if (!frm.doc.is_open || frm.doc.net_outstanding <= 0) {
			return;
		}

		frm.add_custom_button(
			__("Record Full Payment"),
			() => show_payment_dialog(frm, frm.doc.net_outstanding, true),
			__("Payment")
		);

		frm.add_custom_button(
			__("Record Partial Payment"),
			() => show_payment_dialog(frm, null, false),
			__("Payment")
		);
	},
});

function show_payment_dialog(frm, prefill_amount, is_full) {
	const dialog = new frappe.ui.Dialog({
		title: is_full ? __("Record Full Payment") : __("Record Partial Payment"),
		fields: [
			{
				fieldname: "amount",
				fieldtype: "Currency",
				label: __("Amount"),
				reqd: 1,
				default: prefill_amount || undefined,
				read_only: is_full ? 1 : 0,
				description: __("Outstanding: {0}", [
					format_currency(frm.doc.net_outstanding, frm.doc.currency),
				]),
			},
			{
				fieldname: "mode_of_payment",
				fieldtype: "Link",
				label: __("Mode of Payment"),
				options: "Mode of Payment",
			},
		],
		primary_action_label: __("Record Payment"),
		primary_action: (values) => {
			if (values.amount <= 0 || values.amount > frm.doc.net_outstanding) {
				frappe.msgprint(
					__("Amount must be between 0 and {0}.", [frm.doc.net_outstanding])
				);
				return;
			}
			dialog.hide();
			record_payment(frm, values.amount, values.mode_of_payment);
		},
	});
	dialog.show();
}

function record_payment(frm, amount, mode_of_payment) {
	frappe.call({
		method:
			"seminary.seminary.doctype.student_balance.student_balance.record_payment",
		args: {
			student_balance: frm.doc.name,
			amount: amount,
			mode_of_payment: mode_of_payment || null,
		},
		freeze: true,
		freeze_message: __("Recording payment..."),
		callback: (r) => {
			if (r.message && r.message.payment_entry) {
				frappe.show_alert({
					message: __("Payment Entry {0} created", [
						`<a href="/app/payment-entry/${r.message.payment_entry}">${r.message.payment_entry}</a>`,
					]),
					indicator: "green",
				});
				frm.reload_doc();
			}
		},
	});
}
