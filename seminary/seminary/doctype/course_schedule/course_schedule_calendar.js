frappe.views.calendar['Course Schedule'] = {
	field_map: {
		'start': 'dtstart',
		'end': 'dtend',
		'id': 'name',
		'title': 'title',
		'allDay': 'allDay',
		'color': 'color'
	},
	gantt: false,
	filters: [
		{
			fieldtype: 'Link',
			fieldname: 'course',
			options: 'Course',
			label: __('Course'),
		},
		{
			fieldtype: 'Link',
			fieldname: 'instructor1',
			options: 'Instructor',
			label: __('Instructor'),
		},
	],

	get_events_method: "seminary.seminary.api.get_course_schedule_events"
}
