// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Partner Job Opening", {
	setup(frm) {
		// Only offer locations that belong to the selected partner organization.
		frm.set_query("location", () => {
			return { filters: { partner_org: frm.doc.partner_org } };
		});
	},
	partner_org(frm) {
		// The chosen location must match the (possibly new) organization.
		if (frm.doc.location) {
			frm.set_value("location", null);
		}
	},
	refresh(frm) {
		// Surface the approval state (publish gate) as a coloured indicator so
		// staff can spot partner postings awaiting review.
		if (frm.is_new()) return;
		if (frm.doc.status === "Closed") {
			frm.page.set_indicator(__("Closed"), "gray");
		} else if (!frm.doc.publish) {
			frm.page.set_indicator(__("Awaiting Approval"), "orange");
		} else {
			frm.page.set_indicator(__("Published"), "green");
		}
	},
});
