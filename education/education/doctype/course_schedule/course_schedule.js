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
	frm.get_meeting_dates();
		
};