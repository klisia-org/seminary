// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt
//
// The readiness pre-flight, on the form where the rules are chosen (ADR 067
// section 11). A chair should learn that three of their eleven mentors have no
// address here, at 2pm, while they are configuring — not from an empty result
// in the planner later.

// "Follow the category" is the honest default, but a default nobody can read is
// just a shrug. Spell out what it currently resolves to, and keep it in step as
// the binding is edited.
function describe_archive_rule(frm) {
	const field = frm.get_field("on_archive");
	if (!field) return;

	// `set_new_description` only rewrites the help box; it does not touch
	// `df.description`, so the field's own wording stays available to compose
	// against on every later call.
	const base = __(field.df.description || "");
	if (frm.doc.on_archive && frm.doc.on_archive !== "Follow the category") {
		field.set_new_description(base);
		return;
	}

	const scoped_to_one_thing =
		frm.doc.category === "Course scoped" ||
		(["Paced Program", "Throughout Program"].includes(frm.doc.category) &&
			frm.doc.program);
	const resolved = scoped_to_one_thing
		? __(
				"As set up, a cohort of this type belongs to one thing that happens once, so archiving keeps its members."
		  )
		: __(
				"As set up, a cohort of this type is not bound to a single Program, so archiving releases its members."
		  );
	field.set_new_description(`${base}<br><b>${resolved}</b>`);
}

frappe.ui.form.on("Cohort Type", {
	category: describe_archive_rule,
	program: describe_archive_rule,
	program_level: describe_archive_rule,
	on_archive: describe_archive_rule,

	refresh(frm) {
		frm.dashboard.clear_headline();
		describe_archive_rule(frm);
		if (frm.is_new() || !frm.doc.plannable || !frm.doc.mentor_unit) return;

		frm.add_custom_button(__("Open Cohort Planner"), () =>
			frappe.set_route("cohort-planner")
		);

		frappe
			.call("seminary.seminary.discipleship.planner.planner_setup", {
				cohort_type: frm.doc.name,
			})
			.then((r) => show_readiness(frm, r.message))
			// A settings problem is reported by the form's own validation, in
			// words about the setting. Repeating it as a dashboard error would
			// say the same thing twice and less well.
			.catch(() => {});
	},
});

function show_readiness(frm, setup) {
	if (!setup) return;
	const waiting = (setup.scopes || {}).all || 0;
	const gaps = (setup.readiness || []).filter(
		(r) => r.mentors_missing || r.students_missing
	);

	// Mentor gaps and student gaps are never summed: one student without a
	// detail is one student unplaced, but a mentor pool without it makes the
	// rule inoperable for everybody.
	const lines = gaps.map((r) => {
		const parts = [];
		if (r.mentors_missing) {
			parts.push(
				__("{0} of {1} mentors have no {2}", [
					r.mentors_missing,
					r.mentors_total,
					r.reads_label,
				])
			);
		}
		if (r.students_missing) {
			parts.push(
				__("{0} of {1} students have no {2}", [
					r.students_missing,
					r.students_total,
					r.reads_label,
				])
			);
		}
		return `${__(r.label)}: ${parts.join("; ")}`;
	});

	const blocked = gaps.some((r) => r.mentors_missing);
	const headline = [
		__("{0} mentors available, {1} students waiting", [
			(setup.mentors || []).length,
			waiting,
		]),
	]
		.concat(lines)
		.join(" · ");

	frm.dashboard.set_headline(
		headline,
		blocked ? "orange" : lines.length ? "blue" : "green"
	);
}
