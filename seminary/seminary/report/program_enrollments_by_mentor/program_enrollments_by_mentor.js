// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.query_reports['Program Enrollments by Mentor'] = {
	filters: [
		{
			fieldname: 'instructor',
			label: __('Mentor'),
			fieldtype: 'Link',
			options: 'Instructor',
		},
		{
			fieldname: 'instructor_category',
			label: __('Mentor Type'),
			fieldtype: 'Link',
			options: 'Instructor Category',
			get_query: function () {
				return { filters: { is_competency_evaluator: 1 } };
			},
		},
		{
			fieldname: 'program',
			label: __('Program'),
			fieldtype: 'Link',
			options: 'Program',
		},
		{
			fieldname: 'academic_term',
			label: __('Academic Term'),
			fieldtype: 'Link',
			options: 'Academic Term',
		},
		{
			fieldname: 'include_inactive',
			label: __('Include Inactive Enrollments'),
			fieldtype: 'Check',
			default: 0,
		},
		{
			fieldname: 'include_closed',
			label: __('Include Closed Mentor Assignments'),
			fieldtype: 'Check',
			default: 0,
		},
		{
			fieldname: 'unmentored',
			label: __('Show Students Missing a Mentor'),
			fieldtype: 'Check',
			default: 0,
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
