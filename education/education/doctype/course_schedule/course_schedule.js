frappe.ui.form.on("Course Schedule", {
	refresh: function(frm) {
		frm.add_custom_button(__('Add Meeting Dates'), function()  {
			if(!frm.cs_meetinfo) {
				frm.call('save_dates');
		
				} else { 
					frappe.msgprint('No meeting dates found')}})},
	
			

	onload: (frm) => {
		frm.set_query('instructor', () => {
			if (frm.instructors.length) {
				return {
					'filters':{
						'instructor_name': ["in", frm.instructors]
			},
				};
			}
			else
				return;

		})

	}
			});