frappe.ui.form.on('Student Group', {
	onload: function(frm) {
		frm.set_query('academic_term', function() {
			return {
				filters: {
					'academic_year': (frm.doc.academic_year)
				}
			};
		});
		if (!frm.__islocal) {
			frm.set_query('student', 'students', function() {
				return{
					query: 'education.education.doctype.student_group.student_group.get_students',
					filters: {
						'academic_year': frm.doc.academic_year,				
						'academic_term': frm.doc.academic_term,
						'program': frm.doc.program
					}
				}
			});
		}
	},

	refresh: function(frm) {
		if (!frm.doc.__islocal) {

			frm.add_custom_button(__('Student Attendance Tool'), function() {
				frappe.route_options = {
					based_on: 'Student Group',
					student_group: frm.doc.name
				}
				frappe.set_route('Form', 'Student Attendance Tool', 'Student Attendance Tool');
			}, __('Tools'));

			frm.add_custom_button(__('Course Scheduling Tool'), function() {
				frappe.route_options = {
					student_group: frm.doc.name
				}
				frappe.set_route('Form', 'Course Scheduling Tool', 'Course Scheduling Tool');
			}, __('Tools'));

			frm.add_custom_button(__('Newsletter'), function() {
				frappe.route_options = {
					'Newsletter Email Group.email_group': frm.doc.name
				}
				frappe.set_route('List', 'Newsletter');
			}, __('View'));

		}
	},
	
	get_students: function(frm) {
		frm.students = [],
					frm.set_value('students', []);
				frappe.call({
					method: 'get_students',
					doc: frm.doc,
					
					
					args: {
						'academic_year': frm.doc.academic_year,
						'academic_term': frm.doc.academic_term,
						'program': frm.doc.program
						},
					callback: function(r) {
						if (r.message) {
							frm.students = r.message;
							frm.set_value('students', r.message);
							frm.refresh_field('students'); 					
								}
							}});
						} 
					});

frappe.ui.form.on('Student Group Instructor', {
	instructors_add: function(frm){
		frm.fields_dict['instructors'].grid.get_field('instructor').get_query = function(doc){
			let instructor_list = [];
			$.each(doc.instructors, function(idx, val){
				instructor_list.push(val.instructor);
			});
			return { filters: [['Instructor', 'name', 'not in', instructor_list]] };
		};
	}
});
