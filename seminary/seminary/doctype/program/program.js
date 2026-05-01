// Copyright (c) 2015, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Program', {
	setup: function(frm) {
		frm.set_query('program_level', function() {
			return { filters: { 'docstatus': 1 } };
		});
	},
	refresh: function(frm) {
		frm.set_query('program_track', 'pgm_courses_track', function() {
			return {
				query: 'seminary.seminary.doctype.program.program.get_program_tracks',
				filters: { 'program': frm.doc.name }
			};
		});
		frm.set_query('fallback_emphasis', function() {
			return {
				query: 'seminary.seminary.doctype.program.program.get_program_tracks',
				filters: { 'program': frm.doc.name }
			};
		});

		if (frm.doc.pgm_pgmtracks && frm.doc.pgm_pgmtracks.length) {
			frm.add_custom_button(__('Check Track Credits'), function() {
				check_track_credits(frm);
			});
		}
	}
});

frappe.ui.form.on('Program Course', {
	courses_add: function(frm){
		frm.fields_dict['courses'].grid.get_field('course').get_query = function(doc){
			var courses_list = [];
			$.each(doc.courses, function(idx, val){
				if (val.course) courses_list.push(val.course);
			});
			return { filters: [['Course', 'name', 'not in', courses_list]] };
		};
	},
	course: function(frm, cdt, cdn) {
		// Auto-populate credits from Course default when course is selected and credits is empty
		let row = locals[cdt][cdn];
		if (row.course && !row.pgmcourse_credits) {
			frappe.db.get_value('Course', row.course, 'course_credits', function(r) {
				if (r && r.course_credits) {
					frappe.model.set_value(cdt, cdn, 'pgmcourse_credits', r.course_credits);
				}
			});
		}
	}
});

frappe.ui.form.on('Program Track Courses', {
	pgm_courses_track_add: function(frm) {
		frm.fields_dict['pgm_courses_track'].grid.get_field('program_track_course').get_query = function() {
			let program_courses = (frm.doc.courses || []).map(pc => pc.course).filter(Boolean);
			return { filters: [['Course', 'name', 'in', program_courses]] };
		};
	}
});

// Update form based on program_type: if program_type = 'Time-based' show terms_complete and hide credits_complete; if program_type = 'Credit-based' show credits_complete and hide terms_complete
//frappe.ui.form.on('Program', 'program_type', function(frm) {
//	if (frm.doc.program_type == 'Time-based') {
//		frm.toggle_display('terms_complete', true);
//		frm.toggle_display('credits_complete', false);
//	} else if (frm.doc.program_type == 'Credit-based') {
//		frm.toggle_display('credits_complete', true);
//		frm.toggle_display('terms_complete', true);
//	}
// });

// Update label of terms_complete based on program_type; if program_type = 'Time-based' label = 'Terms to Complete (Will be used to auto-enroll passing students)'; if program_type = 'Credit-based' label terms_complete as 'Suggested # terms to complete (will only be used for statistical purposes)' and label credits_complete = 'Minimum # of Credits to Graduate'
frappe.ui.form.on('Program', 'program_type', function(frm) {
	if (frm.doc.is_ongoing) return;
	if (frm.doc.program_type == 'Time-based') {
		frm.set_df_property('terms_complete', 'label', 'Terms to Complete (Will be used to auto-enroll passing students)');
		} else if (frm.doc.program_type == 'Credit-based') {
		frm.set_df_property('terms_complete', 'label', 'Suggested # terms to complete (will only be used for statistical purposes)');
		frm.set_df_property('credits_complete', 'label', 'Minimum # of Credits to Graduate');
		frm.reload();
	}
});

function check_track_credits(frm) {
	// Build a map of course -> credits from Program Course child table (pgmcourse_credits)
	let course_credits = {};
	(frm.doc.courses || []).forEach(function(pc) {
		if (pc.course) {
			course_credits[pc.course] = cint(pc.pgmcourse_credits);
		}
	});

	// Build a map of track -> total available credits from Program Track Courses
	let track_totals = {};
	(frm.doc.pgm_courses_track || []).forEach(function(ptc) {
		if (!ptc.program_track || !ptc.program_track_course) return;
		if (!track_totals[ptc.program_track]) {
			track_totals[ptc.program_track] = 0;
		}
		let credits = course_credits[ptc.program_track_course];
		if (credits === undefined) {
			// Course is in track but not in Program Courses table — skip
			return;
		}
		track_totals[ptc.program_track] += credits;
	});

	// Compare against each track's requirements
	let rows = '';
	let all_ok = true;
	(frm.doc.pgm_pgmtracks || []).forEach(function(track) {
		let required = track.addcredits || 0;
		let ceiling = track.max_credits || 0;
		let available = track_totals[track.name] || 0;
		let status, color;

		if (available >= required) {
			status = 'OK';
			color = 'green';
		} else {
			status = 'Short by ' + (required - available);
			color = 'red';
			all_ok = false;
		}

		let ceiling_note = '';
		if (ceiling > 0 && available > ceiling) {
			ceiling_note = ' (capped at ' + ceiling + ')';
		}

		rows += '<tr>'
			+ '<td>' + track.track_name + '</td>'
			+ '<td style="text-align:right">' + required + '</td>'
			+ '<td style="text-align:right">' + available + ceiling_note + '</td>'
			+ '<td style="text-align:right;color:' + color + ';font-weight:bold">' + status + '</td>'
			+ '</tr>';
	});

	let html = '<table class="table table-bordered table-condensed">'
		+ '<thead><tr>'
		+ '<th>' + __('Track') + '</th>'
		+ '<th style="text-align:right">' + __('Required') + '</th>'
		+ '<th style="text-align:right">' + __('Available') + '</th>'
		+ '<th style="text-align:right">' + __('Status') + '</th>'
		+ '</tr></thead>'
		+ '<tbody>' + rows + '</tbody>'
		+ '</table>';

	if (all_ok) {
		html += '<p style="color:green;font-weight:bold">' + __('All tracks have sufficient courses.') + '</p>';
	}

	frappe.msgprint({
		title: __('Track Credit Sufficiency'),
		message: html,
		indicator: all_ok ? 'green' : 'orange',
		wide: true
	});
}