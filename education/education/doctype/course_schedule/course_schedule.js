frappe.ui.form.on("Course Schedule", {


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
})};