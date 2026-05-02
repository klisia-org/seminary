// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Program Graduation Requirement", {
	refresh(frm) {
		// Restrict the Library Link picker to submitted rows. Library is
		// submittable; drafts and cancelled rows must not be selectable.
		frm.set_query("grad_requirement_item", "pgr_items", () => ({
			filters: { docstatus: 1 },
		}));

		// Safety net: bind a row-click handler that opens the row's full form
		// view. Useful in case Frappe's built-in pencil binding misfires due
		// to the heavy depends_on / fetch_from chain on this child doctype.
		const grid_field = frm.fields_dict.pgr_items;
		if (!grid_field || !grid_field.grid) return;
		const grid = grid_field.grid;

		grid.wrapper.off("click.pgrOpenForm");
		grid.wrapper.on("click.pgrOpenForm", ".grid-row .data-row .col", function (e) {
			if ($(e.target).closest("input, select, textarea, button, a, .grid-row-check").length) {
				return;
			}
			const $row = $(this).closest(".grid-row");
			const docname = $row.attr("data-name") || $row.data("name");
			if (!docname) return;
			const row = grid.grid_rows_by_docname[docname];
			if (row) {
				row.toggle_view(true);
				e.stopPropagation();
				e.preventDefault();
			}
		});
	},
	pgr_items_add(frm, cdt, cdn) {
		// Auto-open the form view for newly added rows so the registrar sees
		// the conditional sections immediately.
		const grid_row = frm.fields_dict.pgr_items.grid.grid_rows_by_docname[cdn];
		if (grid_row) {
			setTimeout(() => grid_row.toggle_view(true), 50);
		}
	},
});

frappe.ui.form.on("Program Grad Req Items", {
	grad_requirement_item(frm, cdt, cdn) {
		// Mirror requirement_type client-side so depends_on works before the
		// parent is saved (fetch_from only runs server-side on save).
		const row = locals[cdt][cdn];
		if (!row || !row.grad_requirement_item) return;
		frappe.db
			.get_value("Graduation Requirement Item", row.grad_requirement_item, "requirement_type")
			.then((res) => {
				const value = res && res.message && res.message.requirement_type;
				if (value) {
					frappe.model.set_value(cdt, cdn, "requirement_type", value);
				}
			});
	},
});
