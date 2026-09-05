frappe.query_reports["Term Enrollment Status"] = {
	"filters": [
		{
			"fieldname": "academic_term",
			"label": __("Academic Term"),
			"fieldtype": "Link",
			"options": "Academic Term",
			// Filled in onload, not here: `frappe.defaults.get_default(...)`
			// used to be read for this and nothing has ever published that key,
			// so the filter simply opened blank. The term is a document flag,
			// not a site default.
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

	// `Academic Term.iscurrent_acterm` is the app-wide answer to "what term is
	// it" and `tasks._update_term_flags` is its only writer, so the report asks
	// the document rather than a site default nobody maintains. Async, hence
	// onload: a query-report filter `default` is evaluated when the file loads.
	"onload": function (report) {
		if (report.get_filter_value("academic_term")) return;
		frappe.db.get_value("Academic Term", { iscurrent_acterm: 1 }, "name").then((r) => {
			const term = r && r.message && r.message.name;
			// Re-check: the user may have typed one while this was in flight.
			if (term && !report.get_filter_value("academic_term")) {
				report.set_filter_value("academic_term", term);
			}
		});
	},

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
