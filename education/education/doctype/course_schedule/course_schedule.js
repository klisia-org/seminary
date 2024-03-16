frappe.ui.form.on("Course Schedule", {
	refresh: function(frm) {
		frm.add_custom_button(__('Add Meeting Dates'), function()  {
			if(!frm.cs_meetinfo) {
				frm.call('save_dates').then(function() {
					frm.reload_doc();
				});
		
				} else { 
					frappe.msgprint('No meeting dates found')}})
				
				},
	
			validate: function(frm) {
				if (frm.doc.modality !== "Virtual") {
					if (!frm.doc.monday && !frm.doc.tuesday && !frm.doc.wednesday && !frm.doc.thursday && !frm.doc.friday && !frm.doc.saturday && !frm.doc.sunday) {
						frappe.msgprint('Please select at least one day of the week');
						validated = false;
					}
				}
			},

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