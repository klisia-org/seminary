// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Culminating Project", {
	refresh(frm) {
		// Only offer active project types in the picker.
		frm.set_query("project_type", () => ({
			filters: { is_active: 1 },
		}));

		// The project belongs to an Academic Department (or Interdepartment).
		frm.set_query("academic_unit", () => ({
			filters: {
				is_active: 1,
				unit_type: ["in", ["Academic Department", "Academic Interdepartment"]],
			},
		}));

		// Reader pickers: External Examiner picker offers active examiners; an
		// instructor reader is scoped to the project's unit unless the type's
		// policy allows other units. The reader policy lives on the project type.
		apply_reader_policy_ui(frm);

		if (frm.is_new()) return;

		// Department assigns the advisor from the unit's Thesis/CP Advisor pool.
		if (!frm.doc.advisor && frm.doc.academic_unit) {
			frm.add_custom_button(__("Assign Advisor"), () => prompt_assign_advisor(frm));
		}

		if (frm.doc.course_enrollment) {
			frm.add_custom_button(__("Open Course Enrollment"), () => {
				frappe.set_route(
					"Form",
					"Course Enrollment Individual",
					frm.doc.course_enrollment
				);
			});
		} else if (frm.doc.program_enrollment) {
			frm.add_custom_button(__("Enroll in Project Course"), () =>
				prompt_enroll_in_project_course(frm)
			);
		}
	},
	project_type(frm) {
		apply_reader_policy_ui(frm);
	},
	academic_unit(frm) {
		apply_reader_policy_ui(frm);
	},
});

// Wire the project type's reader policy onto the form: hide unused reader slots,
// fix each slot's type, and scope the picker (unit-bound instructors or active
// External Examiners). Falls back to free pickers when the type applies no policy.
function apply_reader_policy_ui(frm) {
	const SLOTS = ["second_reader", "third_reader"];
	const free = () => {
		SLOTS.forEach((f) => {
			frm.set_df_property(f, "hidden", 0);
			frm.set_df_property(`${f}_type`, "hidden", 0);
			frm.set_query(f, () =>
				frm.doc[`${f}_type`] === "External Examiner" ? { filters: { is_active: 1 } } : {}
			);
		});
	};
	if (!frm.doc.project_type) return free();
	frappe.db.get_doc("Culminating Project Type", frm.doc.project_type).then((cpt) => {
		if (!cpt.apply_reader_policy) return free();
		const required = Math.min(cpt.readers_required || 0, 2);
		const policy = {
			second_reader: { type: cpt.second_reader_type, allow: cpt.second_reader_allow_other_units, num: 1 },
			third_reader: { type: cpt.third_reader_type, allow: cpt.third_reader_allow_other_units, num: 2 },
		};
		SLOTS.forEach((f) => {
			const p = policy[f];
			const inUse = p.num <= required;
			frm.set_df_property(f, "hidden", inUse ? 0 : 1);
			frm.set_df_property(`${f}_type`, "hidden", 1); // type dictated by policy
			if (inUse && frm.doc[`${f}_type`] !== (p.type || "Instructor")) {
				frm.set_value(`${f}_type`, p.type || "Instructor");
			}
			frm.set_query(f, () => {
				if ((p.type || "Instructor") === "External Examiner") return { filters: { is_active: 1 } };
				if (!p.allow && frm.doc.academic_unit) {
					return {
						query: "seminary.seminary.faculty.instructors_in_unit",
						filters: { unit: frm.doc.academic_unit },
					};
				}
				return {};
			});
		});
	});
}

async function prompt_assign_advisor(frm) {
	// The advisor is always gated to qualified Thesis/CP Advisors with capacity (a
	// wide net across units). When the type opts in, narrow that pool to the
	// project's Academic Unit.
	let restrict = false;
	if (frm.doc.project_type && frm.doc.academic_unit) {
		const cpt = await frappe.db.get_value("Culminating Project Type", frm.doc.project_type, [
			"apply_reader_policy",
			"advisor_from_academic_unit",
		]);
		const p = (cpt && cpt.message) || {};
		restrict = !!(p.apply_reader_policy && p.advisor_from_academic_unit);
	}
	const advisorFilters = { route: "Thesis/CP Advisor" };
	if (restrict) advisorFilters.unit = frm.doc.academic_unit;
	const d = new frappe.ui.Dialog({
		title: __("Assign Advisor"),
		fields: [
			{
				fieldname: "advisor",
				fieldtype: "Link",
				label: __("Advisor"),
				options: "Instructor",
				reqd: 1,
				get_query: () => ({
					query: "seminary.seminary.faculty.capability_holders",
					filters: advisorFilters,
				}),
				description: restrict
					? __("Qualified Thesis/CP Advisors with capacity, from this project's Academic Unit. Their capacity is claimed and the project is activated.")
					: __("Qualified Thesis/CP Advisors with capacity (any unit). Their capacity is claimed and the project is activated."),
			},
		],
		primary_action_label: __("Assign"),
		primary_action(values) {
			d.hide();
			frappe.call({
				method: "seminary.seminary.doctype.culminating_project.culminating_project.assign_advisor",
				args: { culminating_project: frm.doc.name, advisor: values.advisor },
				freeze: true,
				freeze_message: __("Assigning advisor..."),
				callback: (r) => {
					if (r.message) {
						frappe.show_alert({
							message: r.message.activated
								? __("Advisor assigned and project activated.")
								: __("Advisor assigned."),
							indicator: "green",
						});
						frm.reload_doc();
					}
				},
			});
		},
	});
	d.show();
}

function prompt_enroll_in_project_course(frm) {
	// Resolve the project type's backing course so we can scope the Course
	// Schedule picker to schedules that actually teach it.
	const get_backing_course = frm.doc.project_type
		? frappe.db.get_value("Culminating Project Type", frm.doc.project_type, "course")
		: Promise.resolve({ message: {} });

	Promise.resolve(get_backing_course).then((res) => {
		const backing_course = res && res.message && res.message.course;
		const cs_filters = backing_course ? { course: backing_course } : {};

		const d = new frappe.ui.Dialog({
			title: __("Enroll in Project Course"),
			fields: [
				{
					fieldname: "course_schedule",
					fieldtype: "Link",
					label: __("Course Schedule"),
					options: "Course Schedule",
					reqd: 1,
					get_query: () => ({ filters: cs_filters }),
				},
			],
			primary_action_label: __("Enroll"),
			primary_action(values) {
				d.hide();
				frappe.call({
					method: "seminary.seminary.doctype.culminating_project.culminating_project.enroll_in_project_course",
					args: { name: frm.doc.name, course_schedule: values.course_schedule },
					freeze: true,
					freeze_message: __("Creating course enrollment..."),
					callback: (r) => {
						if (r.message && r.message.course_enrollment) {
							frappe.show_alert({
								message: __("Course enrollment {0} created.", [
									r.message.course_enrollment,
								]),
								indicator: "green",
							});
							frm.reload_doc();
						}
					},
				});
			},
		});
		d.show();
	});
}
