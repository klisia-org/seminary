frappe.ui.form.on('Course Withdrawal Request', {

	refresh: function(frm) {
		// Filter CEI by selected Program Enrollment and current academic term
		frappe.db.get_value('Academic Term', { iscurrent_acterm: 1 }, 'name', function(r) {
			let current_term = r ? r.name : null;

			frm.set_query('course_enrollment_individual', function() {
				let filters = {
					docstatus: 1,
					withdrawn: 0
				};
				if (frm.doc.program_enrollment) {
					filters.program_ce = frm.doc.program_enrollment;
				}
				if (current_term) {
					filters.academic_term = current_term;
				}
				return { filters: filters };
			});
		});

		// Show parent and sibling requests for child requests
		if (frm.doc.has_parent && frm.doc.parent_withdrawal) {
			frm.add_custom_button(__('View Parent Request'), function() {
				frappe.set_route('Form', 'Course Withdrawal Request', frm.doc.parent_withdrawal);
			});

			// Fetch and show sibling requests
			frappe.call({
				method: 'frappe.client.get_list',
				args: {
					doctype: 'Course Withdrawal Request',
					filters: {
						parent_withdrawal: frm.doc.parent_withdrawal,
						name: ['!=', frm.doc.name]
					},
					fields: ['name', 'course_name', 'workflow_state', 'resulting_grade']
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						let html = '<div class="related-withdrawals"><strong>Related Withdrawal Requests:</strong><ul>';
						r.message.forEach(function(req) {
							html += `<li><a href="/app/course-withdrawal-request/${req.name}">${req.name}</a> - ${req.course_name || ''} (${req.workflow_state || 'Draft'})</li>`;
						});
						html += '</ul></div>';
						frm.set_df_property('parent_withdrawal', 'description', html);
					}
				}
			});
		}

		// Show documentation label from withdrawal reason
		if (frm.doc.withdrawal_reason) {
			frappe.db.get_value('Withdrawal Reasons', frm.doc.withdrawal_reason,
				['requires_documentation', 'documentation_label'], function(r) {
					if (r && r.requires_documentation) {
						frm.set_df_property('student_documentation',
							'description', r.documentation_label || 'Documentation required');
					}
				}
			);
		}
	},

	withdrawal_reason: function(frm) {
		if (frm.doc.withdrawal_reason) {
			frappe.db.get_value('Withdrawal Reasons', frm.doc.withdrawal_reason,
				['requires_documentation', 'documentation_label'], function(r) {
					if (r && r.requires_documentation) {
						frm.toggle_reqd('student_documentation', true);
						frm.set_df_property('student_documentation',
							'description', r.documentation_label || 'Documentation required');
					} else {
						frm.toggle_reqd('student_documentation', false);
						frm.set_df_property('student_documentation', 'description', '');
					}
				}
			);
		}
	},



	withdrawal_scope: function(frm) {
		if (frm.doc.withdrawal_scope !== 'Single Course') {
			frm.set_value('is_parent', 1);
		} else {
			frm.set_value('is_parent', 0);
		}
	}

});
