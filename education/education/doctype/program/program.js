// Copyright (c) 2015, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Program Course', {
	courses_add: function(frm){
		frm.fields_dict['courses'].grid.get_field('course').get_query = function(doc){
			var courses_list = [];
			$.each(doc.courses, function(idx, val){
				if (val.course) courses_list.push(val.course);
			});
			return { filters: [['Course', 'name', 'not in', courses_list]] };
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
	if (frm.doc.program_type == 'Time-based') {
		frm.set_df_property('terms_complete', 'label', 'Terms to Complete (Will be used to auto-enroll passing students)');
		} else if (frm.doc.program_type == 'Credit-based') {
		frm.set_df_property('terms_complete', 'label', 'Suggested # terms to complete (will only be used for statistical purposes)');
		frm.set_df_property('credits_complete', 'label', 'Minimum # of Credits to Graduate');
		frm.reload();
	}
});