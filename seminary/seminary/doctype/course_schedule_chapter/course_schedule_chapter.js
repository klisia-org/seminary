// Copyright (c) 2025, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Course Schedule Chapter", {
	onload: function (frm) {
		frm.set_query("lesson", "lessons", function () {
			return {
				filters: {
					chapter: frm.doc.name,
				},
			};
		});
		// Competencies belong to a course, so the eligible set depends on this
		// chapter's course. link_filters cannot express that; the server-side
		// guard in validate() is what actually enforces it.
		frm.set_query("course_competency", function () {
			return {
				filters: {
					course: frm.doc.course_title,
					is_active: 1,
				},
			};
		});
	},
});
