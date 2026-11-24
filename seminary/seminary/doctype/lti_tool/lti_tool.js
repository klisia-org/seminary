// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

// What the tool's administrator needs from this site (decisions/110 §1).
frappe.ui.form.on("LTI Tool", {
	refresh(frm) {
		const p = frm.doc.__onload && frm.doc.__onload.platform;
		if (!p) return;
		const row = (label, value) =>
			`<tr><th style="padding:4px 12px 4px 0;white-space:nowrap">${frappe.utils.escape_html(
				label
			)}</th><td><code>${frappe.utils.escape_html(value || "")}</code></td></tr>`;
		frm.get_field("platform_details").$wrapper.html(
			`<p class="text-muted small">${__(
				"Give these to the tool's administrator, with the client ID and deployment ID."
			)}</p><table class="small">${[
				row(__("Issuer"), p.issuer),
				row(__("Authorization URL"), p.auth_url),
				row(__("Token URL"), p.token_url),
				row(__("Key-set URL"), p.jwks_url),
				row(__("Content selection return URL"), p.deep_link_return_url),
				row(__("OpenID configuration"), p.openid_configuration),
			].join("")}</table>`
		);
	},
});
