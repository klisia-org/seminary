// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Academic Unit", {
	refresh(frm) {
		if (frm.is_new()) return;
		// Read-only view of who is wired to this unit (transitive for an
		// interdepartment). Displays the roster; it never adds or copies rows.
		frm.add_custom_button(__("See Member Roster"), () => show_member_roster(frm));
	},
});

function show_member_roster(frm) {
	frappe.call({
		method: "seminary.seminary.faculty.get_unit_roster",
		args: { unit: frm.doc.name },
		freeze: true,
		callback: (r) => {
			const roster = r.message || [];
			if (!roster.length) {
				frappe.msgprint({
					title: __("Member Roster"),
					message: __("No active members wired to this unit yet."),
				});
				return;
			}
			const rows = roster
				.map((m) => {
					const caps = (m.capabilities || [])
						.map((c) => {
							const cap = m.unit !== frm.doc.name ? `${c.capability} (${m.unit})` : c.capability;
							const load =
								c.max_students > 0
									? ` <span style="color:${c.current_students >= c.max_students ? "var(--red-500)" : "var(--ink-gray-5)"}">${c.current_students || 0}/${c.max_students}</span>`
									: "";
							return `${frappe.utils.escape_html(cap)}${load}`;
						})
						.join(", ");
					const who = frappe.utils.escape_html(m.person_name || m.person);
					const role = m.instructor ? "" : ` <i style="color:var(--ink-gray-5)">(${__("non-instructor")})</i>`;
					return `<tr><td>${who}${role}</td><td>${caps || "—"}</td></tr>`;
				})
				.join("");
			frappe.msgprint({
				title: __("Member Roster — {0}", [frm.doc.unit_name]),
				wide: true,
				message: `<table class="table table-bordered" style="margin:0">
					<thead><tr><th>${__("Member")}</th><th>${__("Capabilities")}</th></tr></thead>
					<tbody>${rows}</tbody></table>`,
			});
		},
	});
}
