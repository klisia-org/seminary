// Copyright (c) 2026, Murilo Melo and contributors
// For license information, please see license.txt

// CRM-style conversation surface (ADR 044): the Conversation tab renders the
// Person's Communication Log timeline, and Compose buttons start an email /
// SMS / in-app message through the consent-aware ledger.

frappe.ui.form.on("Person", {
	refresh(frm) {
		if (frm.is_new()) return;
		render_conversation(frm);
		render_org_footprint(frm);
		render_location(frm);
		bind_address_autocomplete(frm);
		["Email", "SMS", "In-App"].forEach((channel) => {
			frm.add_custom_button(__(channel), () => compose(frm, channel), __("Compose"));
		});
	},
});

// Org Footprint tab (ADR 062): the Person's Academic Unit memberships + capabilities, plus
// Department / Reports To when HRMS is enabled — so a manager can confirm someone is wired into
// everything that drives their access and training.
function render_org_footprint(frm) {
	const wrapper = frm.get_field("org_footprint_html").$wrapper;
	wrapper.html(`<div class="text-muted">${__("Loading footprint...")}</div>`);
	frappe
		.call("seminary.seminary.faculty.person_org_footprint", { person: frm.doc.name })
		.then((r) => {
			const fp = r.message || {};
			const units = fp.units || [];
			const esc = frappe.utils.escape_html;
			const blocks = [];

			if (fp.department || fp.reports_to) {
				blocks.push(`<div style="margin-bottom:12px">
					${fp.department ? `<div><b>${__("Department")}:</b> ${esc(fp.department)}</div>` : ""}
					${fp.reports_to ? `<div><b>${__("Reports To")}:</b> ${esc(fp.reports_to)}</div>` : ""}
				</div>`);
			}

			if (!units.length) {
				blocks.push(`<div class="text-muted">${__("No Academic Unit memberships.")}</div>`);
			} else {
				const rows = units.map((u) => {
					const caps = (u.capabilities || [])
						.map((c) => {
							const cap = esc(c.capability);
							const slots =
								c.max_students > 0 ? ` (${c.current_students || 0}/${c.max_students})` : "";
							return `<span class="indicator-pill blue" style="margin:1px">${cap}${slots}</span>`;
						})
						.join(" ");
					const dim = u.is_active ? "" : 'style="opacity:0.5"';
					const parent = u.parent_unit
						? ` <span class="text-muted small">↑ ${esc(u.parent_unit)}</span>`
						: "";
					return `<tr ${dim}>
						<td style="padding:6px 8px;border-bottom:1px solid var(--border-color)">
							<a href="/app/academic-unit/${encodeURIComponent(u.unit)}">${esc(u.unit)}</a>${parent}
							${u.is_active ? "" : ` <span class="text-muted small">(${__("inactive")})</span>`}
						</td>
						<td class="text-muted small" style="padding:6px 8px;border-bottom:1px solid var(--border-color)">${esc(u.unit_type || "")}</td>
						<td style="padding:6px 8px;border-bottom:1px solid var(--border-color)">${caps || '<span class="text-muted small">—</span>'}</td>
					</tr>`;
				});
				blocks.push(`<table style="width:100%;border-collapse:collapse">
					<thead><tr class="text-muted small">
						<th style="text-align:left;padding:6px 8px">${__("Unit")}</th>
						<th style="text-align:left;padding:6px 8px">${__("Type")}</th>
						<th style="text-align:left;padding:6px 8px">${__("Capabilities")}</th>
					</tr></thead>
					<tbody>${rows.join("")}</tbody>
				</table>`);
			}
			wrapper.html(blocks.join(""));
		});
}

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


// Location (ADR 068 §7). The coordinates are resolved from the mailing address
// and never typed, so the form shows what the last lookup concluded rather than
// four read-only numbers with no explanation. A failed lookup is deliberately
// silent at save time — this is where it becomes visible.
function render_location(frm) {
	const field = frm.get_field("geo_html");
	if (!field) return; // permlevel 1: not everyone can see this section
	const wrapper = field.$wrapper;
	const esc = frappe.utils.escape_html;
	const d = frm.doc;

	const STATE = {
		Resolved: ["green", __("Located")],
		Unresolvable: ["orange", __("No such place")],
		Failed: ["red", __("Lookup failed")],
	};
	const [colour, label] = STATE[d.geo_status] || ["gray", __("Not looked up")];

	const when = d.geocoded_on ? frappe.datetime.str_to_user(d.geocoded_on) : null;
	const parts = [
		`<span class="indicator-pill ${colour}">${label}</span>`,
	];

	if (d.geo_status === "Resolved") {
		const map = `https://www.openstreetmap.org/?mlat=${d.latitude}&mlon=${d.longitude}#map=16/${d.latitude}/${d.longitude}`;
		parts.push(
			`<a href="${map}" target="_blank" rel="noopener" style="margin-left:8px">
				${d.latitude}, ${d.longitude}</a>`,
			// A rooftop and a city centroid are not the same answer, and a
			// distance ranking built on the latter is noise.
			d.geocode_precision
				? `<span class="text-muted small" style="margin-left:8px">${esc(d.geocode_precision)}</span>`
				: ""
		);
	} else if (d.geo_status === "Unresolvable") {
		parts.push(
			`<span class="text-muted small" style="margin-left:8px">${__(
				"The provider knows of no such address. Correct the address above; it is not retried on its own."
			)}</span>`
		);
	} else if (d.geo_status === "Failed") {
		parts.push(
			`<span class="text-muted small" style="margin-left:8px">${__(
				"The provider could not be reached. The daily sweeper will try again."
			)}</span>`
		);
	}

	if (when) {
		parts.push(
			`<div class="text-muted small" style="margin-top:6px">${__("Last checked")}: ${esc(when)}</div>`
		);
	}

	wrapper.html(`<div style="padding:4px 0">${parts.join("")}</div>`);

	if (!frm.is_new()) {
		frm.add_custom_button(__("Geocode Now"), () => geocode_now(frm), __("Location"));
	}
}

function geocode_now(frm) {
	frappe.dom.freeze(__("Looking up the address..."));
	frappe
		.call("seminary.seminary.integrations.geocoding.geocode_now", { person: frm.doc.name })
		.then((r) => {
			frappe.dom.unfreeze();
			const res = r.message || {};
			if (!res.ok) {
				frappe.msgprint({
					title: __("Not located"),
					indicator: "orange",
					message: frappe.utils.escape_html(res.message || ""),
				});
			}
			frm.reload_doc();
		})
		.catch(() => frappe.dom.unfreeze());
}


// Address autocomplete (ADR 068 §7), proxied through this server so no API key
// reaches the browser. A typed address is what the geocoder has to work with,
// so normalising it at entry is cheaper than chasing Unresolvable statuses
// afterwards — and a picked address arrives already located, so it needs no
// separate geocode at all.
function bind_address_autocomplete(frm) {
	const field = frm.get_field("address_line_1");
	if (!field || !field.$input || !window.seminary?.attachAddressAutocomplete) return;

	window.seminary.attachAddressAutocomplete(field.$input.get(0), (address) => {
		const map = {
			address_line_1: address.address_line_1,
			address_line_2: address.address_line_2,
			city: address.city,
			state: address.state,
			pincode: address.pincode,
		};
		Object.entries(map).forEach(([fieldname, value]) => {
			if (value) frm.set_value(fieldname, value);
		});
		// Place Details returns the point, so the address is located the moment
		// it is chosen rather than on the next queued lookup.
		if (address.latitude) {
			frm.set_value("latitude", address.latitude);
			frm.set_value("longitude", address.longitude);
		}
		// Country is a Link, so only set it when Google's name is one we hold —
		// otherwise the field silently rejects it on save.
		if (address.country) {
			frappe.db.exists("Country", address.country).then((exists) => {
				if (exists) frm.set_value("mailing_country", address.country);
			});
		}
	});
}
