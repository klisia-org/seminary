frappe.listview_settings['Course Schedule'] = {
	onload: function(listview) {
		listview.page.add_inner_button(__("Classes & Assessments Calendar"), function() {
			frappe.set_route("classes-and-assessments-calendar");
		});

		const can_import = frappe.user.has_role('Program Chair')
			|| frappe.user.has_role('Seminary Manager')
			|| frappe.user.has_role('Registrar');
		if (can_import) {
			listview.page.add_inner_button(__("Import Course Pack"), function() {
				frappe.prompt(
					[
						{
							fieldname: 'pack', fieldtype: 'Attach', reqd: 1,
							label: __('Course Pack (.zip)')
						},
						{
							fieldname: 'target_mode', fieldtype: 'Select', reqd: 1,
							label: __('Import into'), default: 'new',
							options: [
								{ value: 'new', label: __('A new Course') },
								{ value: 'existing', label: __('An existing Course') }
							]
						},
						{
							fieldname: 'course_name', fieldtype: 'Data',
							label: __('New Course name (optional)'),
							depends_on: "eval:doc.target_mode=='new'"
						},
						{
							fieldname: 'course', fieldtype: 'Link', options: 'Course',
							label: __('Existing Course'),
							mandatory_depends_on: "eval:doc.target_mode=='existing'",
							depends_on: "eval:doc.target_mode=='existing'"
						},
						{
							fieldname: 'academic_term', fieldtype: 'Link', options: 'Academic Term',
							label: __('Target Academic Term'), reqd: 1
						},
						{
							fieldname: 'section', fieldtype: 'Data',
							label: __('Section'), reqd: 1, default: 'A'
						},
						{
							fieldname: 'note_html', fieldtype: 'HTML',
							options: `<div class="text-muted small" style="margin-top:8px;">
								${__('Creates a new Draft Course Schedule with the pack content (chapters, lessons, quizzes, exams, questions, grading scale and media) as fresh, editable records. Set the schedule dates, room and instructors afterwards.')}
							</div>`
						}
					],
					(values) => {
						frappe.dom.freeze(__('Importing course pack…'));
						frappe.call({
							method: 'seminary.seminary.course_pack.import_.import_course_pack',
							args: {
								file_url: values.pack,
								target_mode: values.target_mode,
								course: values.course,
								course_name: values.course_name,
								academic_term: values.academic_term,
								section: values.section
							}
						}).then(r => {
							frappe.dom.unfreeze();
							const m = r && r.message;
							if (!m) return;
							let msg = __('Imported {0} chapters, {1} lessons, {2} activities, {3} questions.',
								[m.chapters, m.lessons, m.activities, m.questions]);
							frappe.msgprint({
								title: __('Course Pack imported'),
								indicator: 'green',
								message: msg
									+ (m.warnings && m.warnings.length ? '<hr>' + m.warnings.join('<br>') : '')
									+ `<hr><a href="/app/course-schedule/${encodeURIComponent(m.course_schedule)}">${__('Open the imported schedule')}</a>`
							});
							listview.refresh();
						}).catch(() => frappe.dom.unfreeze());
					},
					__('Import Course Pack'),
					__('Import')
				);
			});
		}

		listview.page.add_actions_menu_item(__("Close Enrollment"), function() {
			const docs = listview.get_checked_items();
			if (!docs.length) {
				frappe.msgprint(__("Please select at least one Course Schedule."));
				return;
			}
			const names = docs.map(d => d.name);
			frappe.confirm(
				__("Close enrollment on {0} Course Schedule(s)?", [names.length]),
				() => {
					frappe.call({
						method: "seminary.seminary.doctype.course_schedule.course_schedule.bulk_close_enrollment",
						args: { names: names },
						freeze: true,
						freeze_message: __("Closing enrollment..."),
						callback: (r) => {
							const res = r.message || {};
							frappe.show_alert({
								message: __("Closed {0}, skipped {1}.", [
									(res.closed || []).length,
									(res.skipped || []).length,
								]),
								indicator: "green",
							});
							listview.refresh();
						},
					});
				}
			);
		});
	}
};
