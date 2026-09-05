// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.query_reports['Cohorts Needing Attention'] = {
	filters: [
		{
			fieldname: 'cohort_type',
			label: __('Cohort Type'),
			fieldtype: 'Link',
			options: 'Cohort Type',
		},
		{
			fieldname: 'issue',
			label: __('Issue'),
			fieldtype: 'Select',
			options: [
				{ value: '', label: __('All') },
				{ value: 'no_leader', label: __('No active leader') },
				{ value: 'inactive_leader', label: __('Leader no longer an active instructor') },
				{ value: 'member_on_leave', label: __('Member on leave of absence') },
				{ value: 'unplaced', label: __('Students waiting for a cohort') },
			],
			default: '',
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === 'issue' && data && data.issue) {
			value = `<span style="color: var(--text-danger)">${value}</span>`;
		}
		return value;
	},
};
