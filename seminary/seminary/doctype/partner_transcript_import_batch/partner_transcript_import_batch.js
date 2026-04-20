frappe.ui.form.on("Partner Transcript Import Batch", {
	refresh(frm) {
		add_workflow_buttons(frm);
		refresh_row_autocompletes(frm);
	},
	partner_seminary(frm) {
		refresh_row_autocompletes(frm);
	},
});

frappe.ui.form.on("Partner Transcript Import Row", {
	rows_add(frm) {
		refresh_row_autocompletes(frm);
	},
	source_course_code(frm, cdt, cdn) {
		autofill_from_equivalence(frm, cdt, cdn);
	},
});

function add_workflow_buttons(frm) {
	if (frm.is_new() || frm.doc.docstatus !== 0) return;

	frm.add_custom_button(__("Run Dry-Run"), () => {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save your changes first, then click Run Dry-Run."));
			return;
		}
		frm.call("dry_run", {}, null, {
			freeze: true,
			freeze_message: __("Validating rows..."),
		}).then((r) => {
			const clean = r && r.message && r.message.clean;
			frappe.show_alert({
				message: clean
					? __("Dry-run clean. You may submit the batch.")
					: __(
							"Dry-run found warnings; review the Warning column and add Override Notes as needed."
					  ),
				indicator: clean ? "green" : "orange",
			});
			frm.reload_doc();
		});
	}).addClass(
		frm.doc.batch_status === "Dry-Run Clean" ? "btn-default" : "btn-primary"
	);
}

async function refresh_row_autocompletes(frm) {
	const grid = frm.fields_dict.rows && frm.fields_dict.rows.grid;
	if (!grid) return;

	if (!frm.doc.partner_seminary) {
		set_grid_options(grid, "source_course_code", "");
		set_grid_options(grid, "source_grade", "");
		return;
	}
	if (frm.is_new()) return;

	const r = await frm.call("get_import_options");
	const opts = (r && r.message) || { course_codes: [], grade_codes: [] };
	set_grid_options(grid, "source_course_code", (opts.course_codes || []).join("\n"));
	set_grid_options(grid, "source_grade", (opts.grade_codes || []).join("\n"));
}

function set_grid_options(grid, fieldname, options) {
	grid.update_docfield_property(fieldname, "options", options);
	(grid.grid_rows || []).forEach((row) => {
		if (!row) return;
		const df =
			row.docfields && row.docfields.find((d) => d.fieldname === fieldname);
		if (df) df.options = options;
		if (row.refresh_field) row.refresh_field(fieldname);
	});
	grid.refresh();
}

async function autofill_from_equivalence(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.source_course_code || !frm.doc.partner_seminary) return;

	const match = await frappe.db.get_value(
		"Partner Seminary Course Equivalence",
		{
			partner_seminary: frm.doc.partner_seminary,
			source_course_code: row.source_course_code,
			docstatus: 1,
		},
		["source_course_name", "source_credit_value"]
	);
	const values = (match && match.message) || {};
	if (values.source_course_name) {
		frappe.model.set_value(cdt, cdn, "source_course_name", values.source_course_name);
	}
	if (values.source_credit_value) {
		frappe.model.set_value(cdt, cdn, "source_credit_value", values.source_credit_value);
	}
}
