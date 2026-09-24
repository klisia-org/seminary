// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

// A gated release mode waits on the self-assessment at the end of each
// competency, so it is offered only where the framework asks for one (ADR 079
// decision 7). The controller refuses the combination too; this only keeps the
// form from offering what it would refuse.
const END_OF_COMPETENCY = [
	"End of each competency",
	"Start of course and end of each competency",
];

function filter_release_modes(frm) {
	const all = (
		frappe.get_meta("Competency Framework").fields.find(
			(df) => df.fieldname === "content_release_mode"
		)?.options || ""
	)
		.split("\n")
		.filter(Boolean);
	const gated_ok =
		frm.doc.course_self_eval &&
		END_OF_COMPETENCY.includes(frm.doc.course_self_eval_points);
	let options = gated_ok ? all : ["Ungated"];
	// A stored gated mode stays visible rather than silently changing, so the
	// save explains why it is refused instead of the value just disappearing.
	if (frm.doc.content_release_mode && !options.includes(frm.doc.content_release_mode)) {
		options = [...options, frm.doc.content_release_mode];
	}
	frm.set_df_property("content_release_mode", "options", options);
}

frappe.ui.form.on("Competency Framework", {
	refresh: filter_release_modes,
	course_self_eval: filter_release_modes,
	course_self_eval_points: filter_release_modes,
});
