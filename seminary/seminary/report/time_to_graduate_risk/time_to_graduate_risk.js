frappe.query_reports["Time-to-Graduate Risk"] = {
	"filters": [
		{
			"fieldname": "program",
			"label": __("Program"),
			"fieldtype": "Link",
			"options": "Program"
		},
		{
			"fieldname": "active_only",
			"label": __("Active Only"),
			"fieldtype": "Check",
			"default": 1
		}
	]
};
