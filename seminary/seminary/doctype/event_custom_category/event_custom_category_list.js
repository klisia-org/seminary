// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.listview_settings["Event Custom Category"] = {
	// Per-row "Create Event" button on cohort categories (per_student = 0):
	// opens a modal to pick the enrolled students and create one shared Event.
	button: {
		show: (doc) => !doc.per_student,
		get_label: () => __("Create Event"),
		get_description: (doc) => __("Create a cohort attendance event for {0}", [doc.name]),
		action: (doc) => open_cohort_dialog(doc.name),
	},
};

function open_cohort_dialog(category) {
	const d = new frappe.ui.Dialog({
		title: __("Create Cohort Event") + ": " + category,
		size: "large",
		fields: [
			{ fieldname: "program", fieldtype: "Link", options: "Program", label: __("Program (optional)") },
			{ fieldname: "col", fieldtype: "Column Break" },
			{ fieldname: "only_candidates", fieldtype: "Check", label: __("Graduation candidates only") },
			{ fieldname: "within_days", fieldtype: "Int", label: __("Within N days of max graduation") },
			{ fieldname: "load", fieldtype: "Button", label: __("Load Students") },
			{ fieldname: "candidates", fieldtype: "HTML" },
			{ fieldname: "sb", fieldtype: "Section Break" },
			{ fieldname: "starts_on", fieldtype: "Datetime", label: __("Event Date / Time"), reqd: 1 },
			{ fieldname: "location", fieldtype: "Data", label: __("Location") },
		],
		primary_action_label: __("Create Event"),
		primary_action(values) {
			const checked = d.$wrapper
				.find(".cohort-cand:checked")
				.map((_, el) => el.value)
				.get();
			if (!checked.length) {
				frappe.msgprint(__("Select at least one student."));
				return;
			}
			frappe.call({
				method: "seminary.seminary.events.create_cohort_event",
				args: {
					event_custom_category: category,
					sgr_names: checked,
					starts_on: values.starts_on,
					location: values.location || null,
				},
				freeze: true,
				freeze_message: __("Creating event..."),
				callback(res) {
					if (res.message && res.message.event) {
						d.hide();
						frappe.show_alert({
							message: __("Event created for {0} student(s).", [res.message.count]),
							indicator: "green",
						});
						frappe.set_route("Form", "Event", res.message.event);
					}
				},
			});
		},
	});

	const render = (rows) => {
		const $w = d.fields_dict.candidates.$wrapper;
		if (!rows.length) {
			$w.html('<p class="text-muted">' + __("No matching students.") + "</p>");
			return;
		}
		let html =
			'<div style="max-height:240px;overflow:auto;border:1px solid #e5e7eb;border-radius:6px;padding:8px">';
		html +=
			'<label style="font-weight:600;display:block;margin-bottom:6px"><input type="checkbox" class="cohort-all"> ' +
			__("Select all") +
			" (" + rows.length + ")</label>";
		rows.forEach((row) => {
			html +=
				'<label style="display:block"><input type="checkbox" class="cohort-cand" value="' +
				row.sgr_name +
				'"> ' +
				frappe.utils.escape_html(row.student_name || row.program_enrollment) +
				' <span class="text-muted">(' +
				frappe.utils.escape_html(row.program || "") +
				")</span></label>";
		});
		html += "</div>";
		$w.html(html);
		$w.find(".cohort-all").on("change", function () {
			$w.find(".cohort-cand").prop("checked", this.checked);
		});
	};

	const load = () => {
		frappe.call({
			method: "seminary.seminary.events.get_cohort_candidates",
			args: {
				event_custom_category: category,
				program: d.get_value("program") || null,
				only_candidates: d.get_value("only_candidates") ? 1 : 0,
				within_days: d.get_value("within_days") || null,
			},
			callback: (r) => render(r.message || []),
		});
	};

	d.fields_dict.load.$input.on("click", load);
	d.show();
	load();
}
