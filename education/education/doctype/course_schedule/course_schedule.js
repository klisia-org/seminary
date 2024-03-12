frappe.ui.form.on("Course Schedule", {
	refresh: function(frm) {
		frm.add_custom_button(__('Add Meeting Dates'), function()  {
			frm.call('save_dates', function(save_dates) {
				if (save_dates.cs_meetdate && save_dates.cs_fromtime && save_dates.cs_totime) {
				frm.add_child('cs_meetinfo', {
					'cs_meetdate' : save_dates.cs_meetdate,
					'cs_fromtime' : save_dates.cs_fromtime,
						'cs_totime' : save_dates.cs_totime});
				refresh_field('cs_meetinfo');
				} else { 
					frappe.msgprint('No meeting dates found')}})})},
	
			

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