// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
frappe.provide("education");

frappe.ui.form.on('Student Attendance Tool', {
	setup: (frm) => {
		frm.students_area = $('<div>')
			.appendTo(frm.fields_dict.students_html.wrapper);
	},


	refresh: function(frm) {
		if (frappe.route_options) {
			
			frm.set_value("course_schedule", frappe.route_options.course_schedule);
			frappe.route_options = null;
		}
		frm.disable_save();
	},

	student_roster: function(frm) {
		if ( frm.doc.course_schedule) {
			frm.students_area.find('.student-attendance-checks').html(`<div style='padding: 2rem 0'>Fetching...</div>`);
			var method = "education.education.doctype.student_attendance_tool.student_attendance_tool.get_student_attendance_records";

			frappe.call({
				method: method,
				args: {
					
					date: frm.doc.date,
					course_schedule: frm.doc.course_schedule
				},
				callback: function(r) {
					frm.events.get_students(frm, r.message);
				}
			})
		}
	},


	date: function(frm) {
		if (frm.doc.date > frappe.datetime.get_today())
			frappe.throw(__("Cannot mark attendance for future dates."));
		frm.trigger("student_roster");
		
			
	},

	course_schedule: function(frm) {
		frm.trigger("student_roster");
	},

	get_students: function(frm, students) {
		students = students || [];
		frm.students_editor = new education.StudentsEditor(frm, frm.students_area, students);
	}
});


education.StudentsEditor = class StudentsEditor {
	constructor(frm, wrapper, students) {
		this.wrapper = wrapper;
		this.frm = frm;
		if(students.length > 0) {
			this.make(frm, students);
		} else {
			this.show_empty_state();
		}
	}
	make(frm, students) {
		var me = this;

		$(this.wrapper).empty();
		var student_toolbar = $('<p>\
			<button class="btn btn-default btn-add btn-xs" style="margin-right: 5px;"></button>\
			<button class="btn btn-xs btn-default btn-remove" style="margin-right: 5px;"></button>\
			<button class="btn btn-default btn-primary btn-mark-att btn-xs"></button></p>').appendTo($(this.wrapper));

		student_toolbar.find(".btn-add")
			.html(__('Check all'))
			.on("click", function() {
				$(me.wrapper).find('input[type="checkbox"]').each(function(i, check) {
					if (!$(check).prop("disabled")) {
						check.checked = true;
					}
				});
			});

		student_toolbar.find(".btn-remove")
			.html(__('Uncheck all'))
			.on("click", function() {
				$(me.wrapper).find('input[type="checkbox"]').each(function(i, check) {
					if (!$(check).prop("disabled")) {
						check.checked = false;
					}
				});
			});

		student_toolbar.find(".btn-mark-att")
			.html(__('Mark Attendance'))
			.removeClass("btn-default")
			.on("click", function() {
				$(me.wrapper.find(".btn-mark-att")).attr("disabled", true);
				var studs = [];
				$(me.wrapper.find('input[type="checkbox"]')).each(function(i, check) {
					var $check = $(check);
					studs.push({
						student: $check.data().student,
						student_name: $check.data().stuname_roster,
						
						disabled: $check.prop("disabled"),
						checked: $check.is(":checked")
					});
				});

				var students_present = studs.filter(function(stud) {
					return !stud.disabled && stud.checked;
				});

				var students_absent = studs.filter(function(stud) {
					return !stud.disabled && !stud.checked;
				});

				frappe.confirm(__("Do you want to update attendance? <br> Present: {0} <br> Absent: {1}",
					[students_present.length, students_absent.length]),
					function() {	//ifyes
						if(!frappe.request.ajax_count) {
							frappe.call({
								method: "education.education.api.mark_attendance",
								freeze: true,
								freeze_message: __("Marking attendance"),
								args: {
									"students_present": students_present,
									"students_absent": students_absent,
									"course_schedule": frm.doc.course_schedule,
									"date": frm.doc.date
								},
								callback: function(r) {
									$(me.wrapper.find(".btn-mark-att")).attr("disabled", false);
									if (!r.exc) {
										frappe.show_alert({message:__("Attendance Marked"), indicator:'green'});
									}
								}
							});
						}
					},
					function() {	//ifno
						$(me.wrapper.find(".btn-mark-att")).attr("disabled", false);
					}
				);
			});

		// make html grid of students
		let student_html = '';
		for (let student of students) {
			student_html += `<div class="col-sm-3">
					<div class="checkbox">
						<label>
							<input
								type="checkbox"
								data-student="${student.student}"
								data-student-name="${student.stuname_roster}"
								class="students-check"
								${student.status==='Present' ? 'checked' : ''}>
							 ${student.stuname_roster}
						</label>
					</div>
				</div>`;
		}

		$(`<div class='student-attendance-checks'>${student_html}</div>`).appendTo(me.wrapper);
	}

	show_empty_state() {
		$(this.wrapper).html(
			`<div class="text-center text-muted" style="line-height: 100px;">
				${__("No Students in")} ${this.frm.doc.course_schedule}
			</div>`
		);
	}
};
