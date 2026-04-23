// Copyright (c) 2026, Klisia, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Unpaid Instructor Log"] = {
	filters: [
		{
			fieldname: "as_of",
			label: __("As of"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "instructor",
			label: __("Instructor"),
			fieldtype: "Link",
			options: "Instructor",
		},
		{
			fieldname: "academic_term",
			label: __("Academic Term"),
			fieldtype: "Link",
			options: "Academic Term",
		},
		{
			fieldname: "instructor_category",
			label: __("Instructor Category"),
			fieldtype: "Link",
			options: "Instructor Category",
		},
	],
};
