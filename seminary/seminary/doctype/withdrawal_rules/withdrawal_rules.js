frappe.ui.form.on('Withdrawal Rules', {

	refresh: function(frm) {
		if (!frm.is_new() && frm.doc.term_based_date) {
			frm.add_custom_button(__('View Term Rules'), function() {
				frappe.set_route('List', 'Term Withdrawal Rules', {
					withdrawal_rule: frm.doc.name
				});
			});
		}
	},

	exclude_from_grade_calculation: function(frm) {
		if (frm.doc.exclude_from_grade_calculation) {
			frm.set_value('consider_grade_as', '');
		} else {
			frm.set_value('grading_symbol', '');
		}
	}

});
