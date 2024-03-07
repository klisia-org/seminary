// Copyright (c) 2016, Frappe and contributors
// For license information, please see license.txt


frappe.ui.form.on('Program Enrollment', {

	onload: function(frm) {
		frm.fields_dict['fees'].grid.get_field('fee_schedule').get_query = function(doc, cdt, cdn) {
			var d = locals[cdt][cdn];
			return {
				filters: {'academic_term': d.academic_term}
			}
		};

		if (frm.doc.program) {
			frm.set_query('course', 'courses', function() {
				return {
					query: 'education.education.doctype.program_enrollment.program_enrollment.get_program_courses',
					filters: {
						'program': frm.doc.program
					}
				}
			});
		}
	},

	program: function(frm) {
		frm.events.get_courses(frm);
		if (frm.doc.program) {
			frappe.call({
				method: 'education.education.api.get_fee_schedule',
				args: {
					'program': frm.doc.program,
					'student_category': frm.doc.student_category
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('fees' ,r.message);
						frm.events.get_courses(frm);
					}
				}
			});
		}
	},

	student_category: function() {
		frappe.ui.form.trigger('Program Enrollment', 'program');
	},

	
});

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
	}
});
