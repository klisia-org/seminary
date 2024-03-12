frappe.views.calendar["Course Schedule"] = {
	field_map: {
		"date": "cs_meetdate",
		"start": "cs_fromtime",
		"end": "cs_totime",
		"id": "name",
		"title": "course",
	},
	gantt: false,
	order_by: "c.datestart",
	filters: [
		{
			"fieldtype": "Link",
			"fieldname": "course",
			"options": "Course",
			"label": __("Course")
		},
		{
			"fieldtype": "Link",
			"fieldname": "instructor1",
			"options": "Instructor",
			"label": __("Instructor")
		},
		{
			"fieldtype": "Link",
			"fieldname": "room",
			"options": "Room",
			"label": __("Room")
		}
	],
	get_events_method: "education.education.api.get_course_schedule_events"
}
