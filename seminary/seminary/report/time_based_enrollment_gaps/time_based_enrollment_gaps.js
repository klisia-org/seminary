frappe.query_reports["Time-based Enrollment Gaps"] = {
	"filters": [
		{
			"fieldname": "program",
			"label": __("Program"),
			"fieldtype": "Link",
			"options": "Program"
		},
		{
			"fieldname": "academic_term",
			"label": __("Offering Term"),
			"fieldtype": "Link",
			"options": "Academic Term"
		}
	]
};
