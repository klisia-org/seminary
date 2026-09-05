// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.query_reports['Course Competency Coverage'] = {
	filters: [
		{
			fieldname: 'course',
			label: __('Course'),
			fieldtype: 'Link',
			options: 'Course',
		},
		{
			fieldname: 'academic_unit',
			label: __('Academic Unit'),
			fieldtype: 'Link',
			options: 'Academic Unit',
		},
		{
			fieldname: 'grading_scale',
			label: __('Grading Scale'),
			fieldtype: 'Link',
			options: 'Grading Scale',
		},
		{
			fieldname: 'only_issues',
			label: __('Only Courses Needing Attention'),
			fieldtype: 'Check',
			default: 0,
		},
		{
			fieldname: 'include_retired',
			label: __('Include Retired Courses'),
			fieldtype: 'Check',
			default: 0,
		},
		{
			fieldname: 'include_all_courses',
			label: __('Include Courses Without Competencies'),
			fieldtype: 'Check',
			default: 0,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === 'issue' && data && data.issue) {
			value = `<span style="color: var(--text-danger)">${value}</span>`;
		}
		if (
			column.fieldname === 'active_competencies' &&
			data &&
			data.scale_type === 'Competency-based education'
		) {
			const colour = data.active_competencies
				? 'var(--text-success)'
				: 'var(--text-danger)';
			value = `<span style="color: ${colour}; font-weight: 600">${value}</span>`;
		}
		return value;
	},
};
