// Copyright (c) 2016, Frappe and contributors
// For license information, please see license.txt


frappe.ui.form.on('Program Enrollment', {

	onload: function(frm) {
		frm.set_query('program', function() {
			frm.set_query('course', 'courses', function() {
				return {
					query: 'education.education.doctype.program_enrollment.program_enrollment.get_program_courses',
					filters: {
						'program': frm.doc.program
					}
				}
			});
		});
	},
	on_save: function(frm) {
		frm.call('get_payers')
			.fail(() => {
				frappe.msgprint("Error adding payers");
			})
			.then(() => {
				frm.reload_doc();
			});
},});

frappe.ui.form.on('Program Enrollment Course', {
	courses_add: function(frm){
		frm.fields_dict['courses'].grid.get_field('course').get_query = function(doc) {
			var course_list = [];
			if(!doc.__islocal) course_list.push(doc.name);
			$.each(doc.courses, function(_idx, val) {
				if (val.course) course_list.push(val.course);
			});
			return { filters: [['Course', 'name', 'not in', course_list],
				['Course', 'name', 'in', frm.program_courses.map((e) => e.course)]] };
		};
},
});
