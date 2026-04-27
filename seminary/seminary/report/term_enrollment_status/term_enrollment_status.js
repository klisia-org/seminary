frappe.query_reports["Term Enrollment Status"] = {
	"filters": [
		{
			"fieldname": "academic_term",
			"label": __("Academic Term"),
			"fieldtype": "Link",
			"options": "Academic Term",
			"default": frappe.defaults.get_default("iscurrent_acterm"),
			"reqd": 0
		},
		{
			"fieldname": "workflow_state",
			"label": __("Workflow State"),
			"fieldtype": "Select",
			"options": "\nDraft\nOpen for Enrollment\nEnrollment Closed\nGrading\nClosed\nCancelled"
		},
		{
			"fieldname": "below_minimum_only",
			"label": __("Below Minimum Only"),
			"fieldtype": "Check"
		}
	],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "delta" && data && data.minimum_enrollment) {
			if (data.delta < 0) {
				value = `<span style="color:var(--text-danger,#c0392b);font-weight:600">${value}</span>`;
			} else if (data.delta === 0) {
				value = `<span style="color:var(--text-warning,#b7791f);font-weight:600">${value}</span>`;
			} else {
				value = `<span style="color:var(--text-success,#15803d)">${value}</span>`;
			}
		}
		return value;
	}
};
