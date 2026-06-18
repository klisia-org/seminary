// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.query_reports["Academic Unit Faculty Audit"] = {
	filters: [
		{
			fieldname: "academic_unit",
			label: __("Academic Unit"),
			fieldtype: "Link",
			options: "Academic Unit",
		},
		{
			fieldname: "only_issues",
			label: __("Only Issues"),
			fieldtype: "Check",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "issue" && data && data.issue) {
			value = `<span style="color:var(--red-600);font-weight:600">${value}</span>`;
		}
		return value;
	},
};
