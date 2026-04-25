// Copyright (c) 2016, Frappe and contributors
// For license information, please see license.txt


frappe.ui.form.on('Program Enrollment', {

	onload: function(frm) {
		frm.set_query('program', function() {
			frm.set_query('course', 'courses', function() {
				return {
					query: 'seminary.seminary.doctype.program_enrollment.program_enrollment.get_program_courses',
					filters: {
						'program': frm.doc.program
					}
				}
			});
		});
		frm.set_query('emphasis_track', 'emphases', function() {
			return {
				query: 'seminary.seminary.doctype.program_enrollment.program_enrollment.get_emphasis',
				filters: {
					'program': frm.doc.program
				}
			}
		});
	},
	on_save: function(frm) {
		frm.call('get_payers')
			.fail(() => {
				frappe.msgprint("Error adding payers");
			})
			.then(() => {
				frm.reload_doc();
			});
},
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('Payers for this Program'), function() {
				frappe.set_route("Form", "Payers Fee Category PE", frm.doc.name);
			}).css({"color":"white", "background": "#0d3049", "font-weight": "700", "border-radius": "5px", "padding": "5px 10px", "margin-right": "10px"});

			frm.add_custom_button(__('View Full Audit'), function() {
				show_full_audit(frm);
			});
		}

		// Populate inline audit summary
		if (frm.doc.program && frm.doc.docstatus === 1) {
			frappe.call({
				method: 'seminary.seminary.api.get_program_audit',
				args: { program_enrollment: frm.doc.name },
				callback: function(r) {
					if (r.message) {
						render_audit_summary(frm, r.message);
						maybe_add_alumni_button(frm, r.message);
					}
				}
			});
		}
	}

});

function maybe_add_alumni_button(frm, audit) {
	if (!audit.graduation_eligible) return;

	frm.add_custom_button(__('Mark as Alumni'), function() {
		frappe.confirm(
			__('Create an Alumni Profile for {0} and grant them the Alumni role?',
				[frm.doc.student_name]),
			function() {
				frappe.call({
					method: 'seminary.alumni.api.mark_as_alumni',
					args: { program_enrollment: frm.doc.name },
					freeze: true,
					freeze_message: __('Creating alumni profile...'),
					callback: function(r) {
						if (!r.message) return;
						if (r.message.already_existed) {
							frappe.msgprint({
								title: __('Already an Alumnus'),
								message: __('This student already has an alumni profile.'),
								indicator: 'orange',
							});
						} else {
							frappe.show_alert({
								message: __('Alumni profile created.'),
								indicator: 'green',
							});
						}
						frappe.set_route('Form', 'Alumni Profile', r.message.name);
					},
				});
			}
		);
	}, __('Graduation'));
}

function render_audit_summary(frm, audit) {
	let pct = audit.effective_credits_required
		? Math.round((audit.credits_earned / audit.effective_credits_required) * 100)
		: 0;
	pct = Math.min(pct, 100);

	// Card style shared across all summary cards
	let card = 'style="border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px;background:#fff;min-width:180px"';
	let bar_bg = 'style="background:#e5e7eb;border-radius:4px;height:8px;margin-top:6px"';

	function progress_bar(percent, color) {
		return '<div ' + bar_bg + '>'
			+ '<div style="background:' + (color || '#4b5563') + ';border-radius:4px;height:8px;width:' + percent + '%"></div>'
			+ '</div>';
	}

	// Graduation eligibility banner
	let grad_bg = audit.graduation_eligible ? '#f0fdf4' : '#fff7ed';
	let grad_color = audit.graduation_eligible ? '#16a34a' : '#ea580c';
	let grad_text = audit.graduation_eligible ? __('Eligible for Graduation') : __('Not Yet Eligible for Graduation');

	let html = '<div style="padding:8px 0">';
	html += '<div style="padding:8px 12px;border-radius:6px;margin-bottom:12px;font-weight:600;color:'
		+ grad_color + ';background:' + grad_bg + '">' + grad_text + '</div>';

	// Cards row
	html += '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:12px">';

	// Program Credits card
	if (audit.program_type === 'Credits-based') {
		html += '<div ' + card + '>'
			+ '<div style="font-size:12px;color:#6b7280;margin-bottom:2px">' + __('Program Credits') + '</div>'
			+ '<div style="font-size:18px;font-weight:700;color:#1f2937">'
			+ audit.credits_earned + ' / ' + audit.effective_credits_required + '</div>'
			+ progress_bar(pct)
			+ '</div>';
	}

	// Terms card
	if (audit.program_type === 'Time-based') {
		let termPct = audit.terms_required
			? Math.min(Math.round((audit.current_term / audit.terms_required) * 100), 100)
			: 0;
		html += '<div ' + card + '>'
			+ '<div style="font-size:12px;color:#6b7280;margin-bottom:2px">' + __('Term Progress') + '</div>'
			+ '<div style="font-size:18px;font-weight:700;color:#1f2937">'
			+ __('Term') + ' ' + audit.current_term + ' ' + __('of') + ' ' + audit.terms_required + '</div>'
			+ progress_bar(termPct)
			+ '</div>';
	}

	// Emphasis cards
	(audit.emphases || []).forEach(function(emph) {
		let ePct = emph.credits_required
			? Math.min(Math.round((emph.credits_capped / emph.credits_required) * 100), 100)
			: 0;
		html += '<div ' + card + '>'
			+ '<div style="font-size:12px;color:#6b7280;margin-bottom:2px">' + emph.track_name + '</div>'
			+ '<div style="font-size:18px;font-weight:700;color:#1f2937">'
			+ emph.credits_capped + ' / ' + emph.credits_required;
		if (emph.max_credits > 0) {
			html += ' <span style="font-size:11px;color:#9ca3af;font-weight:400">(' + __('cap') + ': ' + emph.max_credits + ')</span>';
		}
		html += '</div>' + progress_bar(ePct);
		if (emph.mandatory_remaining.length) {
			html += '<div style="margin-top:4px;font-size:11px;color:#ea580c">'
				+ __('Remaining') + ': ' + emph.mandatory_remaining.join(', ') + '</div>';
		}
		html += '</div>';
	});

	// Elective Credits card
	let elec_earned = audit.elective_credits_earned != null ? audit.elective_credits_earned : 0;
	let elec_needed = audit.elective_credits_needed != null ? audit.elective_credits_needed : '—';
	html += '<div ' + card + '>'
		+ '<div style="font-size:12px;color:#6b7280;margin-bottom:2px">' + __('Elective Credits') + '</div>'
		+ '<div style="font-size:18px;font-weight:700;color:#1f2937">'
		+ elec_earned + ' / ' + elec_needed
		+ '</div></div>';

	html += '</div>'; // close cards row
	html += '</div>';
	frm.fields_dict.audit_summary.$wrapper.html(html);
}

function show_full_audit(frm) {
	frappe.call({
		method: 'seminary.seminary.api.get_program_audit',
		args: { program_enrollment: frm.doc.name },
		callback: function(r) {
			if (!r.message) return;
			let audit = r.message;

			let today = frappe.datetime.nowdate();
			let html = '<div id="audit-print-content">';

			// Header with student info
			html += '<div style="margin-bottom:12px">'
				+ '<h3 style="margin:0">' + __('Program Audit') + ': ' + (audit.student_name || '') + '</h3>'
				+ '<p style="margin:2px 0;color:#666">' + __('Program') + ': ' + audit.program
				+ ' | ' + __('Generated on') + ': ' + today + '</p>'
				+ '</div>';

			// Graduation status
			let grad_color = audit.graduation_eligible ? '#16a34a' : '#ea580c';
			let grad_text = audit.graduation_eligible ? __('Eligible for Graduation') : __('Not Yet Eligible for Graduation');
			html += '<div style="margin-bottom:12px;padding:8px 12px;border-radius:4px;font-weight:bold;color:' + grad_color
				+ ';background:' + (audit.graduation_eligible ? '#f0fdf4' : '#fff7ed') + '">' + grad_text + '</div>';

			// Credits summary
			if (audit.program_type === 'Credits-based') {
				html += '<p><strong>' + __('Credits') + ':</strong> ' + audit.credits_earned + ' / ' + audit.effective_credits_required + '</p>';
			}
			if (audit.program_type === 'Time-based') {
				html += '<p><strong>' + __('Term') + ':</strong> ' + audit.current_term + ' / ' + audit.terms_required + '</p>';
			}

			// Program mandatory courses table
			if (audit.mandatory_courses && audit.mandatory_courses.length) {
				html += '<h4>' + __('Program Requirements') + '</h4>';
				html += '<table class="table table-bordered table-condensed">'
					+ '<thead><tr><th>' + __('Course') + '</th><th>' + __('Credits') + '</th>'
					+ '<th>' + __('Status') + '</th><th>' + __('Grade') + '</th></tr></thead><tbody>';

				audit.mandatory_courses.forEach(function(mc) {
					let color = mc.status === 'Completed' ? 'green' : mc.status === 'In Progress' ? 'orange' : 'gray';
					html += '<tr><td>' + (mc.course_name || mc.course) + '</td>'
						+ '<td>' + (mc.credits || '') + '</td>'
						+ '<td style="color:' + color + ';font-weight:bold">' + mc.status + '</td>'
						+ '<td>' + (mc.grade_code || '') + '</td></tr>';
				});
				html += '</tbody></table>';
			}

			// Emphasis details with track mandatory courses
			(audit.emphases || []).forEach(function(emph) {
				html += '<h4>' + __('Track Requirements') + ': ' + emph.track_name + '</h4>';
				html += '<p style="font-size:11px;color:#999;font-style:italic">'
					+ __('Courses mandatory for both the program and this emphasis are shown here only.') + '</p>';
				html += '<p>' + __('Credits') + ': ' + emph.credits_capped + ' / ' + emph.credits_required;
				if (emph.max_credits > 0) html += ' (' + __('cap') + ': ' + emph.max_credits + ')';
				html += '</p>';

				if (emph.mandatory_courses && emph.mandatory_courses.length) {
					html += '<table class="table table-bordered table-condensed">'
						+ '<thead><tr><th>' + __('Course') + '</th><th>' + __('Credits') + '</th>'
						+ '<th>' + __('Status') + '</th><th>' + __('Grade') + '</th></tr></thead><tbody>';
					emph.mandatory_courses.forEach(function(mc) {
						let color = mc.status === 'Completed' ? 'green' : mc.status === 'In Progress' ? 'orange' : 'gray';
						html += '<tr><td>' + (mc.course_name || mc.course) + '</td>'
							+ '<td>' + (mc.credits || '') + '</td>'
							+ '<td style="color:' + color + ';font-weight:bold">' + mc.status + '</td>'
							+ '<td>' + (mc.grade_code || '') + '</td></tr>';
					});
					html += '</tbody></table>';
				}
			});

			// Elective Credits
			let elec_earned = audit.elective_credits_earned != null ? audit.elective_credits_earned : 0;
			let elec_needed = audit.elective_credits_needed != null ? audit.elective_credits_needed : '—';
			html += '<h4>' + __('Elective Credits') + '</h4>';
			html += '<p>' + elec_earned + ' / ' + elec_needed + '</p>';

			// Disclaimer
			html += '<p style="margin-top:16px;font-size:11px;color:#999;font-style:italic">'
				+ (audit.disclaimer || '') + '</p>';

			html += '</div>';

			let d = new frappe.ui.Dialog({
				title: __('Full Program Audit'),
				size: 'large',
				primary_action_label: __('Print'),
				primary_action: function() {
					let w = window.open('', '_blank');
					w.document.write('<html><head><title>' + __('Program Audit') + ' - ' + (audit.student_name || '') + '</title>'
						+ '<style>body{font-family:sans-serif;padding:20px;font-size:13px}'
						+ 'table{border-collapse:collapse;width:100%;margin-bottom:12px}'
						+ 'th,td{border:1px solid #ddd;padding:6px 8px;text-align:left}'
						+ 'th{background:#f5f5f5;font-weight:600}'
						+ 'h3,h4{margin:8px 0}</style></head><body>'
						+ document.getElementById('audit-print-content').innerHTML
						+ '</body></html>');
					w.document.close();
					w.print();
				}
			});
			d.$body.html(html);
			d.show();
		}
	});
}

frappe.ui.form.on('Program Enrollment Course', {
	courses_add: function(frm){
		frm.fields_dict['courses'].grid.get_field('course').get_query = function(doc) {
			var course_list = [];
			if(!doc.__islocal) course_list.push(doc.name);
			$.each(doc.courses, function(_idx, val) {
				if (val.course) course_list.push(val.course);
			});
			return { filters: [['Course', 'name', 'not in', course_list],
				['Course', 'name', 'in', frm.program_courses.map((e) => e.course)]] };
		};
},
});
