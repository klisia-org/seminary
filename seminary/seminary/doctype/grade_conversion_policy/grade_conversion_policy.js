frappe.ui.form.on("Grade Conversion Policy", {
	refresh(frm) {
		refresh_all_options(frm);
	},
	source_grading_scale(frm) {
		refresh_symbol_options(frm, "source_grading_scale", "source_symbol");
	},
	target_grading_scale(frm) {
		refresh_symbol_options(frm, "target_grading_scale", "target_symbol");
	},
});

frappe.ui.form.on("Grade Conversion Map", {
	conversion_map_add(frm) {
		refresh_all_options(frm);
	},
});

function refresh_all_options(frm) {
	refresh_symbol_options(frm, "source_grading_scale", "source_symbol");
	refresh_symbol_options(frm, "target_grading_scale", "target_symbol");
}

function refresh_symbol_options(frm, scale_fieldname, row_fieldname) {
	const scale = frm.doc[scale_fieldname];
	const grid = frm.fields_dict.conversion_map && frm.fields_dict.conversion_map.grid;
	if (!grid) return;

	if (!scale) {
		set_grid_field_options(grid, row_fieldname, "");
		return;
	}

	frappe.db.get_doc("Grading Scale", scale).then((doc) => {
		const intervals = (doc.intervals || [])
			.slice()
			.sort((a, b) => (b.threshold || 0) - (a.threshold || 0));
		const options = intervals.map((r) => r.grade_code).filter(Boolean).join("\n");
		set_grid_field_options(grid, row_fieldname, options);
	});
}

function set_grid_field_options(grid, fieldname, options) {
	grid.update_docfield_property(fieldname, "options", options);
	(grid.grid_rows || []).forEach((row) => {
		if (!row) return;
		const docfield = row.docfields && row.docfields.find((df) => df.fieldname === fieldname);
		if (docfield) docfield.options = options;
		if (row.refresh_field) row.refresh_field(fieldname);
	});
	grid.refresh();
}
