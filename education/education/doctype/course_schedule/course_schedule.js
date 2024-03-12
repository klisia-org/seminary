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
});
frappe.ui.form.on("Course Schedule Meeting Dates", {
	meeting_date: (frm, cdt, cdn) => {
		let row = course_schedule.get_meeting_dates(cdt, cdn);
}});