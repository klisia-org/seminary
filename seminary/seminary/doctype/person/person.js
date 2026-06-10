// Copyright (c) 2026, Murilo Melo and contributors
// For license information, please see license.txt

// CRM-style conversation surface (ADR 044): the Conversation tab renders the
// Person's Communication Log timeline, and Compose buttons start an email /
// SMS / in-app message through the consent-aware ledger.

frappe.ui.form.on("Person", {
	refresh(frm) {
		if (frm.is_new()) return;
		render_conversation(frm);
		["Email", "SMS", "In-App"].forEach((channel) => {
			frm.add_custom_button(__(channel), () => compose(frm, channel), __("Compose"));
		});
	},
});

const STATUS_COLORS = {
	Queued: "orange",
	Sending: "orange",
	Sent: "blue",
	Delivered: "green",
	Read: "green",
	Failed: "red",
	Bounced: "red",
	Cancelled: "gray",
};

function render_conversation(frm) {
	const wrapper = frm.get_field("conversation_html").$wrapper;
	wrapper.html(`<div class="text-muted">${__("Loading conversation...")}</div>`);
	frappe
		.call("seminary.seminary.comms.get_person_timeline", { person: frm.doc.name })
		.then((r) => {
			const rows = r.message || [];
			if (!rows.length) {
				wrapper.html(`<div class="text-muted">${__("No communications yet.")}</div>`);
				return;
			}
			const items = rows.map((row) => {
				const arrow = row.direction === "Inbound" ? "←" : "→";
				const color = STATUS_COLORS[row.status] || "gray";
				const when = frappe.datetime.prettyDate(row.sent_at || row.creation);
				const ref = row.reference_name
					? `· <a href="/app/${frappe.router.slug(row.reference_doctype)}/${encodeURIComponent(
							row.reference_name
					  )}">${frappe.utils.escape_html(row.reference_name)}</a>`
					: "";
				const subject = frappe.utils.escape_html(
					row.subject || frappe.utils.strip_html(row.message || "").slice(0, 80)
				);
				return `
					<div class="comm-row" style="display:flex;gap:8px;align-items:baseline;padding:8px 4px;border-bottom:1px solid var(--border-color);">
						<span class="text-muted" style="min-width:14px">${arrow}</span>
						<span class="indicator-pill ${color}" style="white-space:nowrap">${__(row.status)}</span>
						<span style="min-width:64px" class="text-muted small">${frappe.utils.escape_html(row.channel)}</span>
						<a href="/app/communication-log/${encodeURIComponent(row.name)}" style="flex:1">${subject}</a>
						<span class="text-muted small" style="white-space:nowrap">${when} ${ref}</span>
					</div>`;
			});
			wrapper.html(`<div class="comm-timeline">${items.join("")}</div>`);
		});
}

function compose(frm, channel) {
	const fields = [
		{
			fieldname: "template",
			fieldtype: "Link",
			label: __("Template"),
			options: "Communication Template",
			description: __("Pick a template, or leave blank and write below."),
		},
		{ fieldname: "subject", fieldtype: "Data", label: __("Subject"), depends_on: "eval:!doc.template" },
		{
			fieldname: "message",
			fieldtype: "Text Editor",
			label: __("Message"),
			depends_on: "eval:!doc.template",
		},
		{ fieldname: "send_now", fieldtype: "Check", label: __("Send now"), default: 1 },
	];
	const d = new frappe.ui.Dialog({
		title: __("Compose {0} to {1}", [__(channel), frm.doc.full_name]),
		fields,
		primary_action_label: __("Send"),
		primary_action(values) {
			frappe
				.call("seminary.seminary.comms.compose_communication", {
					person: frm.doc.name,
					channel,
					subject: values.subject,
					message: values.message,
					template: values.template,
					send_now: values.send_now,
				})
				.then((r) => {
					d.hide();
					if (r.message) {
						frappe.show_alert({ message: __("Queued: {0}", [r.message]), indicator: "green" });
					} else {
						frappe.show_alert({
							message: __("Not sent (deduplicated or blocked by consent)."),
							indicator: "orange",
						});
					}
					render_conversation(frm);
				});
		},
	});
	d.show();
}
