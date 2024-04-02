frappe.ui.form.on("Course Schedule", {
	refresh: function(frm) {
		frm.trigger("render_days");
		frm.add_custom_button(__('Add Meeting Dates'), function()  {
			const selectedDays = [];
  			if (frm.doc.monday) {
    			selectedDays.push("Monday")};
			if (frm.doc.tuesday) {
				selectedDays.push("Tuesday")};
			if (frm.doc.wednesday) {
				selectedDays.push("Wednesday")};
			if (frm.doc.thursday) {
				selectedDays.push("Thursday")};
			if (frm.doc.friday) {
				selectedDays.push("Friday")};
			if (frm.doc.saturday) {
				selectedDays.push("Saturday")};
			if (frm.doc.sunday) {
				selectedDays.push("Sunday")};

			frappe.dom.freeze(__("Scheduling..."));
			frm.call('schedule_dates', { days: selectedDays })
				.fail(() => {
					frappe.dom.unfreeze();
					frappe.msgprint(__("Course Scheduling Failed"));
				})
				.then(r => {
					frappe.dom.unfreeze();
					if (!r.message) {
						frappe.throw(__('There were errors creating Course Schedule'));
					}
					const { meeting_dates} = r.message;
					if (meeting_dates) {
						const meeting_dates_html = meeting_dates.map(c => `
							<tr>
								<td>${c.cs_meetdate}</td>
							</tr>
						`).join('');
						
						const html = `
							<table class="table table-bordered">
								<caption>${__('Following meeting dates were created')}</caption>
								<thead><tr><th>${__("Date")}</th></tr></thead>
								<tbody>
									${meeting_dates_html}
								</tbody>
							</table>
						`;

						frappe.msgprint(html);
				
						
					}
				});
			




		});
		if (!frm.doc.__islocal) {
				frm.add_custom_button(__("Mark Attendance"), function() {
					frappe.route_options = {
						based_on: "Course Schedule",
						course_schedule: frm.doc.name
					}
					frappe.set_route("Form", "Student Attendance Tool");
				});
				
			};
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