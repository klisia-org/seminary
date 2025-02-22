// Copyright (c) 2025, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.query_reports["Scholarship Sales Invoices"] = {
	"filters": [
		{
			"fieldname":"start_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"reqd": 0
		},	
		{
			"fieldname":"end_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"reqd": 0
		},
		{
			"fieldname":"Customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
			"reqd": 0
		}
	

	]
};
