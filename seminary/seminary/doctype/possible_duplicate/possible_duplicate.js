// Copyright (c) 2026, Seminary and contributors
// For license information, please see license.txt

// Merge two records, or set the pair aside (privatedocs/p022).
frappe.ui.form.on("Possible Duplicate", {
	refresh(frm) {
		frm.disable_save();
		if (frm.doc.status !== "Open") return;
		frm.add_custom_button(__("Compare and Merge"), () => compare(frm)).addClass("btn-primary");
		frm.add_custom_button(__("Not the Same"), () =>
			frappe.confirm(__("These are two different records. They will not be proposed again."), () =>
				frappe
					.call("seminary.seminary.duplicates.not_the_same", { pair: frm.doc.name })
					.then(() => frm.reload_doc())
			)
		);
	},
});

function compare(frm) {
	frappe.call("seminary.seminary.duplicates.merge_preview", { pair: frm.doc.name }).then(({ message: p }) => {
		const label = (r) => `${r.title || r.name} (${r.name})`;
		const fields = [
			{
				fieldname: "keep",
				fieldtype: "Select",
				label: __("Keep"),
				reqd: 1,
				options: [
					{ value: p.first.name, label: label(p.first) },
					{ value: p.second.name, label: label(p.second) },
				],
				default: p.first.name,
				description: __("The other record is removed and everything linked to it moves to this one."),
			},
		];
		if (p.conflicts.length || !p.can_merge) {
			fields.push({
				fieldtype: "HTML",
				options: `<div class="alert alert-warning">${[...p.conflicts, p.why_not]
					.filter(Boolean)
					.map(frappe.utils.escape_html)
					.join("<br>")}</div>`,
			});
		}
		if (p.differences.length) {
			fields.push({
				fieldtype: "Section Break",
				label: __("Where they differ"),
				description: __("Fields only one record fills are kept without asking."),
			});
			for (const d of p.differences) {
				fields.push({
					fieldname: d.key,
					fieldtype: "Select",
					label: d.label,
					options: [
						{ value: "first", label: d.first },
						{ value: "second", label: d.second },
					],
					default: "first",
				});
			}
		}
		const blocked = p.conflicts.length || !p.can_merge;
		const dialog = new frappe.ui.Dialog({
			title: __("Merge {0}", [__(p.doctype)]),
			fields,
			primary_action_label: __("Merge"),
			primary_action(values) {
				const choices = {};
				for (const d of p.differences) choices[d.key] = values[d.key];
				frappe.confirm(__("A merge cannot be undone. Merge now?"), () =>
					frappe
						.call({
							method: "seminary.seminary.duplicates.merge",
							args: { pair: frm.doc.name, keep: values.keep, choices },
							freeze: true,
						})
						.then(({ message }) => {
							dialog.hide();
							frappe.set_route("Form", p.doctype, message);
						})
				);
			},
		});
		if (blocked) dialog.get_primary_btn().prop("disabled", true);
		dialog.show();
	});
}
