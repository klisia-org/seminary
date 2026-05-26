// Classes and Assessments Calendar — Frappe Page that renders FullCalendar
// against seminary.seminary.api.get_course_schedule_events (meetings +
// assessment due dates UNIONed across all Course Schedules).
//
// The default Course Schedule → Calendar view now shows native term spans
// (c_datestart / c_dateend) via course_schedule_calendar.js. This page is
// the home for the per-meeting / per-assessment-due-date overview.

frappe.pages['classes-and-assessments-calendar'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Classes and Assessments Calendar'),
		single_column: true,
	});

	let calendar;

	const $calWrap = $(
		'<div class="cac-calendar" style="padding:1rem;"></div>'
	).appendTo(page.body);

	frappe.require('calendar.bundle.js', () => {
		calendar = new frappe.FullCalendar($calWrap[0], {
			plugins: frappe.FullCalendar.Plugins,
			initialView: 'dayGridMonth',
			locale: frappe.boot.lang,
			firstDay: frappe.datetime.get_first_day_of_the_week_index(),
			headerToolbar: {
				left: 'prev,title,next',
				right: 'today,dayGridMonth,timeGridWeek,timeGridDay',
			},
			buttonText: {
				today: __('Today'),
				month: __('Month'),
				week: __('Week'),
				day: __('Day'),
			},
			eventTimeFormat: { hour: 'numeric', minute: '2-digit', hour12: true },
			displayEventTime: true,
			displayEventEnd: true,
			nowIndicator: true,
			events: (info, success, failure) => {
				frappe
					.call({
						method: 'seminary.seminary.api.get_course_schedule_events',
						type: 'GET',
						args: {
							start: frappe.datetime.convert_to_system_tz(info.start, true),
							end: frappe.datetime.convert_to_system_tz(info.end, true),
							filters: JSON.stringify([]),
						},
					})
					.then((r) => {
						const events = (r.message || []).map((e) => ({
							id: e.name,
							title: e.title,
							start: e.dtstart,
							end: e.dtend,
							allDay: !!e.allDay,
							color: e.color,
						}));
						success(events);
					})
					.catch(failure);
			},
			eventClick: (info) => {
				if (info.event.id) {
					frappe.set_route('Form', 'Course Schedule', info.event.id);
				}
			},
		});
		calendar.render();
	});
};
