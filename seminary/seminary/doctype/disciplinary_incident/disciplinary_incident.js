// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Disciplinary Incident', {
	setup: function (frm) {
		// Submitted enrollments that haven't terminally ended. Leave of Absence
		// is intentionally included — a student on leave can still warrant a
		// disciplinary action (e.g. social-media conduct during the leave).
		frm.set_query('pe', function () {
			return {
				filters: {
					docstatus: 1,
					status: ['not in', ['Withdrawn', 'Dismissed', 'Graduated', 'Transferred']],
				},
			};
		});

		// Scope the course-enrollment picker to the selected PE's student.
		// Registered synchronously so the filter is always in place.
		frm.set_query('cei', function () {
			const filters = { withdrawn: 0 };
			if (frm.doc.pe) {
				filters.program_ce = frm.doc.pe;
			}
			return { filters: filters };
		});
	},

	pe: function (frm) {
		// Clear a now-mismatched CEI and refresh the occurrence count.
		frm.set_value('cei', null);
		maybe_set_occurrence(frm);
	},

	student: function (frm) {
		// `student` is fetched from `pe`; once it lands, (re)compute the
		// occurrence so the reason's advisory matrix can suggest actions.
		maybe_set_occurrence(frm);
	},

	reason: function (frm) {
		maybe_set_occurrence(frm);
	},

	occurrence_number: function (frm) {
		suggest_actions(frm);
	},
});

function maybe_set_occurrence(frm) {
	if (!frm.doc.student || !frm.doc.reason) {
		return;
	}
	frappe.call({
		method: 'seminary.seminary.disciplinary.compute_occurrence_number',
		args: {
			student: frm.doc.student,
			reason: frm.doc.reason,
			exclude_name: frm.doc.name,
		},
		callback: function (r) {
			if (r.message) {
				frm.set_value('occurrence_number', r.message);
			}
		},
	});
}

function suggest_actions(frm) {
	if (!frm.doc.reason || !frm.doc.occurrence_number) {
		return;
	}
	frappe.call({
		method: 'seminary.seminary.disciplinary.suggest_actions',
		args: { reason: frm.doc.reason, occurrence_number: frm.doc.occurrence_number },
		callback: function (r) {
			const suggestions = r.message || [];
			if (!suggestions.length) {
				return;
			}
			// Drop previously-suggested (unconfirmed) rows, keep manual ones.
			frm.doc.applied_actions = (frm.doc.applied_actions || []).filter(
				(row) => !row.was_suggested
			);
			suggestions.forEach(function (s) {
				const row = frm.add_child('applied_actions');
				row.action = s.recommended_action;
				row.applied_on = frappe.datetime.get_today();
				row.was_suggested = 1;
				row.outcome_note = s.note || '';
			});
			frm.refresh_field('applied_actions');
			frappe.show_alert({
				message: __('Suggested action(s) pre-filled from the reason matrix. Confirm or override.'),
				indicator: 'blue',
			});
		},
	});
}
