// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.query_reports['Sources of Funding'] = {
	filters: [
		{
			fieldname: 'view',
			label: __('View'),
			fieldtype: 'Select',
			options: [
				{ value: 'Period', label: __('A period beside a year earlier') },
				{ value: 'Every year', label: __('Every year') },
			],
			default: 'Period',
		},
		{
			fieldname: 'from_date',
			label: __('From'),
			fieldtype: 'Date',
			depends_on: "eval:doc.view !== 'Every year'",
		},
		{
			fieldname: 'to_date',
			label: __('To'),
			fieldtype: 'Date',
			depends_on: "eval:doc.view !== 'Every year'",
		},
	],

	onload: function (report) {
		frappe.call('seminary.seminary.financial.funding.current_fiscal_year').then((r) => {
			if (!r.message || report.get_filter_value('from_date')) return;
			report.set_filter_value({ from_date: r.message[0], to_date: r.message[1] });
		});
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		return data && data.bold ? `<b>${value}</b>` : value;
	},
};
