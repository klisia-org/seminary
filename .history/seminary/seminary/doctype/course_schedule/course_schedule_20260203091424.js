frappe.ui.form.on("Course Schedule", {

	refresh: function(frm) {
		frm.add_web_link(`/seminary/courses/${frm.doc.name}`, "See on Website");
		frm.trigger("render_days");
		if (frm.doc.hasmtgdate === 0) {
			frm.add_custom_button(__('Add Meeting Dates'), function() {
				// Button functionality here

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
				frappe.call({
					method: "seminary.seminary.api.course_event",
					args: {
						name: frm.doc.name
					},
					callback: function(r) {
						if (r.message) {
							frm.msgprint("Calendar created successfully");
						}}
			});
			frm.set_value('hasmtgdate',  1);
			frm.save();
		});
	};

	if (frm.doc.calendar_token) {
			frm.add_custom_button(__('Regenerate Calendar Token (This will invalidate existing calendar subscriptions)'), function() {
				frm.call('regenerate_token')
				.then(r => {
					if (r.message) {
						frappe.msgprint(__('New Calendar Token: {0}', [r.message]));
					}
				});
			});
		}






		// if (!frm.doc.__islocal) {
		// 		frm.add_custom_button(__("Mark Attendance"), function() {
		// 			frappe.route_options = {

		// 				course_schedule: frm.doc.name
		// 			}
		// 			frappe.set_route("Form", "Student Attendance Tool");
		// 		});

		// 	};
/* 		if (!frm.doc.__islocal) {
				frm.add_custom_button(__("Add Calendar"), function() {
					frappe.call({
						method: "seminary.seminary.api.course_event",
						args: {
							name: frm.doc.name
						},
						callback: function(r) {
							if (r.message) {
								frm.msgprint("Calendar created successfully");
							}}
				});
			});

		}; */

	},
			validate: function(frm) {
				if (frm.doc.modality !== "Virtual" && frm.doc.c_datestart !== frm.doc.c_dateend) {
					if (!frm.doc.monday && !frm.doc.tuesday && !frm.doc.wednesday && !frm.doc.thursday && !frm.doc.friday && !frm.doc.saturday && !frm.doc.sunday) {
						frappe.msgprint('Please select at least one day of the week');
						validated = false;
					}
				} else {
					frm.call('validate')
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

	},
	onload: function(frm) {
		if (!frm.doc.__islocal) {
			frappe.call({
				method: "seminary.seminary.api.get_course_rosters",
				args: {
					name: frm.doc.name
				},
				callback: function(r) {

					if (r.message) {
						var enrollments = r.message;
						var table = "<style>table { width: 100%; border-collapse: collapse; } th, td { border: 1px solid #0d3049; padding: 8px; text-align: left; } </style>";
						table += "<table><thead><tr><th>Photo</th><th>Student ID</th><th>Student Name</th><th>Student Email</th><th>Audit</th><th>Active</th><th>Program</th><th>Grade</th></tr></thead><tbody>";
						for (var i = 0; i < enrollments.length; i++) {
							var activeStatus = enrollments[i].active ? "Yes" : "No";
							var auditStatus = enrollments[i].audit_bool ? "Yes" : "No";
							var image = enrollments[i].stuimage ? "<img src='" + enrollments[i].stuimage + "' width='100' height='100'>" : "";
							// Handle null values in table cells
							var grade = "<a href='/app/scheduled-course-roster/" + enrollments[i].course_sc + "-" + enrollments[i].student + "' style='color: #44b2f7;'>" + "Grades"  + "</a>";
							var student = "<a href='/app/student/" + enrollments[i].student + "'>" + enrollments[i].student + "</a>";
							var stuname_roster = enrollments[i].stuname_roster || "";
							var stuemail_rc = enrollments[i].stuemail_rc || "";
							var program_std_scr = enrollments[i].program_std_scr || "";

							table += "<tr><td>" + image + "</td><td>" + student + "</td><td>" + stuname_roster + "</td><td>" + stuemail_rc + "</td><td>" + auditStatus + "</td><td>" + activeStatus + "</td><td>" + program_std_scr + "</td><td>" + grade + "</td></tr>";
						}
						table += "</tbody></table>";
						frm.set_df_property('csroster_html', 'options', table);
						frm.refresh_field('csroster_html');
					} else {
						frm.set_df_property('csroster_html', 'options', __('No student enrolled so far'));
						frm.refresh_field('csroster_html');
					}
				}
			});
		} else {
					frm.set_df_property('csroster_html', 'options', __('No student enrolled so far'));
					frm.refresh_field('csroster_html');
				};


			},

	})
