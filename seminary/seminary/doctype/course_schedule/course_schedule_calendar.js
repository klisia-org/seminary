// Native Frappe calendar — no get_events_method so Frappe falls back to
// frappe.desk.calendar.get_events, which runs frappe.get_list with the
// user's permissions and the native filter chips below.
//
// The companion meetings + assessment-due-date view lives at
// /app/classes-and-assessments-calendar (Frappe Page); that one still uses
// the custom UNION query in seminary.seminary.api.get_course_schedule_events.

frappe.views.calendar['Course Schedule'] = {
	field_map: {
		id: 'name',
		start: 'c_datestart',
		end: 'c_dateend',
		title: 'title',
		allDay: 1,
		color: 'color',
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
			fieldname: 'academic_term',
			options: 'Academic Term',
			label: __('Academic Term'),
		},
		{
			fieldtype: 'Link',
			fieldname: 'workflow_state',
			options: 'Workflow State',
			label: __('Status'),
		},
	],
}
