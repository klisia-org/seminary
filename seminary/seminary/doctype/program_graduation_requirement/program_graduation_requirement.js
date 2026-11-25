// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Program Graduation Requirement", {
	refresh(frm) {
		// Hide retired library items from the picker. The Library uses an
		// Active/Retired workflow (no longer submittable); retired requirements
		// must not be selectable for new policies.
		frm.set_query("grad_requirement_item", "pgr_items", () => ({
			filters: { workflow_state: ["!=", "Retired"] },
		}));

		// Same retired filter for the After-Requirement prerequisite picker.
		frm.set_query("prerequisite_requirement", "pgr_items", () => ({
			filters: { workflow_state: ["!=", "Retired"] },
		}));

		// Program Track is a child table (no independent read permission), so the
		// default link search throws "no permission for Program Track". Reuse the
		// whitelisted get_emphasis query (raw SQL, bypasses that check) to list
		// only THIS program's emphases for the applies_to_emphasis scope picker.
		frm.set_query("applies_to_emphasis", "pgr_items", () => ({
			query: "seminary.seminary.doctype.program_enrollment.program_enrollment.get_emphasis",
			filters: { program: frm.doc.program_name },
		}));

		// Catalog years (decisions/115): courses come from the Program's own
		// courses, disabled ones included, and tracks from its tracks.
		frm.set_query("course", "catalog_courses", () => ({
			query: "seminary.seminary.catalog_year.program_course_query",
			filters: { program: frm.doc.program_name },
		}));
		for (const table of ["catalog_tracks", "catalog_track_courses"]) {
			frm.set_query("program_track", table, () => ({
				query: "seminary.seminary.doctype.program.program.get_program_tracks",
				filters: { program: frm.doc.program_name },
			}));
		}
		show_catalog_state(frm);
		if (!frm.is_new()) {
			frm.add_custom_button(__("Compare"), () => compare_catalogs(frm));
		}

		// Safety net: bind a row-click handler that opens the row's full form
		// view. Useful in case Frappe's built-in pencil binding misfires due
		// to the heavy depends_on / fetch_from chain on this child doctype.
		const grid_field = frm.fields_dict.pgr_items;
		if (!grid_field || !grid_field.grid) return;
		const grid = grid_field.grid;

		grid.wrapper.off("click.pgrOpenForm");
		grid.wrapper.on("click.pgrOpenForm", ".grid-row .data-row .col", function (e) {
			if (
				$(e.target).closest("input, select, textarea, button, a, .grid-row-check").length
			) {
				return;
			}
			const $row = $(this).closest(".grid-row");
			const docname = $row.attr("data-name") || $row.data("name");
			if (!docname) return;
			const row = grid.grid_rows_by_docname[docname];
			if (row) {
				row.toggle_view(true);
				e.stopPropagation();
				e.preventDefault();
			}
		});
	},
	pgr_items_add(frm, cdt, cdn) {
		// Auto-open the form view for newly added rows so the registrar sees
		// the conditional sections immediately.
		const grid_row = frm.fields_dict.pgr_items.grid.grid_rows_by_docname[cdn];
		if (grid_row) {
			setTimeout(() => grid_row.toggle_view(true), 50);
		}
	},
});

frappe.ui.form.on("Program Grad Req Items", {
	grad_requirement_item(frm, cdt, cdn) {
		// Mirror requirement_type client-side so depends_on works before the
		// parent is saved (fetch_from only runs server-side on save).
		const row = locals[cdt][cdn];
		if (!row || !row.grad_requirement_item) return;
		frappe.db
			.get_value(
				"Graduation Requirement Item",
				row.grad_requirement_item,
				"requirement_type"
			)
			.then((res) => {
				const value = res && res.message && res.message.requirement_type;
				if (value) {
					frappe.model.set_value(cdt, cdn, "requirement_type", value);
				}
			});
	},
});

function show_catalog_state(frm) {
	const link = (name, label) =>
		`<a href="/app/program-graduation-requirement/${encodeURIComponent(
			name
		)}">${frappe.utils.escape_html(label || name)}</a>`;
	const state = frm.doc.workflow_state;
	if (state === "Draft" && !frm.is_new()) {
		frm.dashboard.set_headline(
			__(
				"Draft catalog year. Edit its courses here; the program is unchanged until it takes effect, when its first term starts."
			)
		);
	} else if (state === "Scheduled") {
		frm.dashboard.set_headline(
			__(
				"Scheduled: takes effect when {0} starts, and then replaces the program's courses.",
				[frappe.utils.escape_html(frm.doc.academic_term_from || "")]
			)
		);
	} else if (state === "Superseded" && frm.doc.superseded_by) {
		frm.dashboard.set_headline(
			__("Followed by {0}. Students who entered under this catalog year keep it.", [
				link(frm.doc.superseded_by),
			])
		);
	}
}

function compare_catalogs(frm) {
	frappe.prompt(
		[
			{
				fieldname: "other",
				fieldtype: "Link",
				label: __("Compare with"),
				options: "Program Graduation Requirement",
				default: frm.doc.supersedes,
				reqd: 1,
				get_query: () => ({
					filters: { program_name: frm.doc.program_name, name: ["!=", frm.doc.name] },
				}),
			},
		],
		(values) => show_comparison(frm, values.other),
		__("Compare catalog years"),
		__("Compare")
	);
}

function show_comparison(frm, other) {
	frappe
		.call("seminary.seminary.catalog_year.compare", { catalog: frm.doc.name, other })
		.then(({ message }) => {
			if (!message) return;
			const esc = frappe.utils.escape_html;
			const title = message.other
				? __("{0} compared with {1}", [
						esc(message.catalog.catalog_year || message.catalog.name),
						esc(message.other.catalog_year || message.other.name),
				  ])
				: __("Compare");
			const body = message.changes.length
				? `<ul>${message.changes.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>`
				: `<p>${__("No differences.")}</p>`;
			frappe.msgprint({ title, message: body, wide: true });
		});
}
