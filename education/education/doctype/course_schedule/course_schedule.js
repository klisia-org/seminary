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
	cs_meetinfo_add: (frm, cdt, cdn) => {
		frm.call('get_meeting_dates') 
}});