// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Course Competency', {
	course: function (frm) {
		load_dimension_options(frm);
	},
	onload: function (frm) {
		load_dimension_options(frm);
	},
	refresh: function (frm) {
		if (!frm.is_new() && frm.doc.course) {
			frm.add_custom_button(__('Add Missing Dimensions'), function () {
				add_missing_dimensions(frm);
			});
		}
	},
});

// Dimensions come from the course's grading scale (ADR 065). Offering them as
// options keeps the author from copying codes across forms and getting them
// subtly wrong; the server validates the same list on save.
let dimension_cache = {};

function load_dimension_options(frm) {
	if (!frm.doc.course) return;
	frappe.call({
		method: 'seminary.seminary.doctype.course_competency.course_competency.get_course_dimensions',
		args: { course: frm.doc.course },
		callback: function (r) {
			let rows = r.message || [];
			dimension_cache[frm.doc.course] = rows;
			let field = frappe.meta.get_docfield(
				'Course Competency Dimension', 'dimension_code', frm.doc.name
			);
			if (field) {
				field.fieldtype = 'Select';
				field.options = [''].concat(rows.map(d => d.dimension_code)).join('\n');
			}
			frm.refresh_field('dimensions');
		},
	});
}

function add_missing_dimensions(frm) {
	let rows = dimension_cache[frm.doc.course] || [];
	if (!rows.length) {
		frappe.msgprint(__('The grading scale for this course defines no dimensions.'));
		return;
	}
	let present = (frm.doc.dimensions || []).map(d => d.dimension_code);
	let added = 0;
	rows.forEach(function (d) {
		if (present.includes(d.dimension_code)) return;
		let row = frm.add_child('dimensions');
		row.dimension_code = d.dimension_code;
		row.dimension = d.dimension;
		added += 1;
	});
	frm.refresh_field('dimensions');
	frappe.show_alert(
		added
			? __('Added {0} dimension(s). Describe how each is demonstrated.', [added])
			: __('Every dimension is already listed.')
	);
}
