frappe.ui.form.on("Course Schedule", {
	refresh: function(frm) {
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__("Mark Attendance"), function() {
				frappe.route_options = {
					based_on: "Course Schedule",
					course_schedule: frm.doc.name
				}
				frappe.set_route("Form", "Student Attendance Tool");
			});
		}
	},

	onload: (frm) => {
		frm.set_query('instructor', () => {
			if (frm.instructors.length) {
				return {
					'filters':{
						'instructor_name': ["in", frm.instructors]
					}
				};
			}
			else
				return;

		})

	}
}),

	after_save; (frm) => {
	frappe.call({
		method: 'education.education.course_schedule.get_meeting_dates',
		args: {
			'docname': frm.doc.name
},
	callback: function(r) {
		if (r.message) {
			frm.set_value('meeting_dates', r.message);
		}
		else
			return;
}
})}