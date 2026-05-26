// Copyright (c) 2026, Klisia, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["CEI Marked Paid Without Payment"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("Marked Paid From"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("Marked Paid To"),
			fieldtype: "Date",
		},
		{
			fieldname: "marked_paid_by",
			label: __("Marked Paid By"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "program",
			label: __("Program"),
			fieldtype: "Link",
			options: "Program",
		},
	],
};
