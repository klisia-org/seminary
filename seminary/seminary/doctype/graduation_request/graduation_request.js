// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Graduation Request", {
	refresh(frm) {
		// Filter PE picker to active, submitted enrollments only.
		frm.set_query("program_enrollment", () => ({
			filters: {
				docstatus: 1,
				pgmenrol_active: 1,
			},
		}));

		// Filter Student picker to the PE's student when one is set.
		if (frm.doc.program_enrollment) {
			frm.set_query("student", () => ({
				filters: { name: frm.doc.student || "" },
			}));
		}

		render_snapshot(frm);
	},

	program_enrollment(frm) {
		// Cleared by the user — drop dependent fields so fetch_from re-runs.
		if (!frm.doc.program_enrollment) {
			frm.set_value("student", null);
			frm.set_value("program", null);
			frm.set_value("expected_graduation_date", null);
			frm.set_value("is_free", 0);
			clear_snapshot(frm);
			return;
		}
		render_snapshot(frm);
	},
});

function clear_snapshot(frm) {
	if (frm.fields_dict.graduation_requirements_html) {
		frm.fields_dict.graduation_requirements_html.$wrapper.empty();
	}
	if (frm.fields_dict.pending_payments_html) {
		frm.fields_dict.pending_payments_html.$wrapper.empty();
	}
}

function render_snapshot(frm) {
	if (!frm.doc.program_enrollment) {
		clear_snapshot(frm);
		return;
	}

	frappe.call({
		method: "seminary.seminary.api.get_program_audit",
		args: { program_enrollment: frm.doc.program_enrollment },
		callback: function (r) {
			if (!r.message) return;
			render_grad_reqs(frm, r.message);
		},
	});

	frappe.call({
		method: "seminary.seminary.api.get_pe_unpaid_invoices",
		args: { program_enrollment: frm.doc.program_enrollment },
		callback: function (r) {
			render_pending_payments(frm, r.message || []);
		},
	});
}

function render_grad_reqs(frm, audit) {
	const wrapper = frm.fields_dict.graduation_requirements_html.$wrapper;
	const reqs = audit.graduation_requirements || [];
	if (!reqs.length) {
		wrapper.html(`<p class="text-muted">${__("No graduation requirements snapshotted on this enrollment.")}</p>`);
		return;
	}

	const status_color = (s) => {
		if (s === "Fulfilled") return "green";
		if (s === "Waived") return "#2563eb";
		if (s === "Submitted") return "#d97706";
		if (s === "In Progress") return "orange";
		if (s === "Failed") return "#dc2626";
		return "gray";
	};

	const desk_link = (req) => {
		if (!req.linked_doc || !req.link_doctype) return "—";
		const dt = req.link_doctype.toLowerCase().replace(/ /g, "-");
		const url = `/app/${dt}/${encodeURIComponent(req.linked_doc)}`;
		return `<a href="${url}" target="_blank">${frappe.utils.escape_html(req.linked_doc)}</a>`;
	};

	let html = '<table class="table table-bordered table-condensed">'
		+ "<thead><tr>"
		+ `<th>${__("Requirement")}</th>`
		+ `<th>${__("Type")}</th>`
		+ `<th>${__("Status")}</th>`
		+ `<th>${__("Mandatory")}</th>`
		+ `<th>${__("Blocks Request")}</th>`
		+ `<th>${__("Due")}</th>`
		+ `<th>${__("Linked Document")}</th>`
		+ "</tr></thead><tbody>";

	for (const req of reqs) {
		html += "<tr>"
			+ `<td>${frappe.utils.escape_html(req.requirement_name || "")}${req.waived ? ` <em>(${__("waived")})</em>` : ""}</td>`
			+ `<td>${frappe.utils.escape_html(req.requirement_type || "—")}</td>`
			+ `<td style="color:${status_color(req.status)};font-weight:bold">${frappe.utils.escape_html(req.status || "—")}</td>`
			+ `<td>${req.mandatory ? __("Yes") : __("No")}</td>`
			+ `<td>${req.blocks_graduation_request ? __("Yes") : __("No")}</td>`
			+ `<td>${req.due_date || "—"}</td>`
			+ `<td>${desk_link(req)}</td>`
			+ "</tr>";
	}
	html += "</tbody></table>";
	wrapper.html(html);
}

function render_pending_payments(frm, rows) {
	const wrapper = frm.fields_dict.pending_payments_html.$wrapper;
	if (!rows.length) {
		wrapper.html(`<p class="text-muted">${__("No unpaid invoices on this enrollment.")}</p>`);
		return;
	}

	let total = 0;
	let html = '<table class="table table-bordered table-condensed">'
		+ "<thead><tr>"
		+ `<th>${__("Payer")}</th>`
		+ `<th>${__("Unpaid Invoices")}</th>`
		+ `<th class="text-right">${__("Total Unpaid")}</th>`
		+ "</tr></thead><tbody>";

	for (const row of rows) {
		total += row.total_unpaid || 0;
		const inv_links = (row.invoices || [])
			.map((inv) => {
				const url = `/app/sales-invoice/${encodeURIComponent(inv.name)}`;
				return `<a href="${url}" target="_blank">${frappe.utils.escape_html(inv.name)}</a> <span class="text-muted">(${frappe.utils.escape_html(inv.source)})</span>`;
			})
			.join(", ");
		html += "<tr>"
			+ `<td>${frappe.utils.escape_html(row.customer || "")}</td>`
			+ `<td>${inv_links}</td>`
			+ `<td class="text-right" style="color:#d97706;font-weight:bold">${format_currency(row.total_unpaid)}</td>`
			+ "</tr>";
	}
	html += "</tbody>"
		+ "<tfoot><tr>"
		+ `<th colspan="2" class="text-right">${__("Total")}</th>`
		+ `<th class="text-right" style="color:#d97706">${format_currency(total)}</th>`
		+ "</tr></tfoot></table>";
	wrapper.html(html);
}

function format_currency(value) {
	const n = Number(value || 0);
	return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
