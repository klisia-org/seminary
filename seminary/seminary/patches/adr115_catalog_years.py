"""decisions/115: every graduating program gets a catalog year, and every enrollment is bound to one.

No school is live, so a program's catalog is today's Program from the earliest term. An existing
Active policy becomes that catalog. Older, superseded policies get the same academic section (the
only one recorded) and no window, so they stay readable by the enrollments bound to them but are
never resolved for new ones. Catalog rows are written at the database level: they hold exactly what
the Program holds, so nothing needs validating or writing back.
"""

import frappe

from seminary.seminary import catalog_year as cy

CHILD_TABLES = {
	"pgr_items": "Program Grad Req Items",
	"catalog_courses": "Catalog Course",
	"catalog_tracks": "Catalog Track",
	"catalog_track_courses": "Catalog Track Course",
	"honors_levels": "Honors Levels",
}


def execute():
	earliest = frappe.get_all(
		"Academic Term",
		filters={"term_start_date": ("is", "set")},
		fields=["name", "term_start_date", "academic_year"],
		order_by="term_start_date asc",
		limit=1,
	)
	earliest = earliest[0] if earliest else None
	for program in frappe.get_all("Program", filters={"is_ongoing": 0}, pluck="name"):
		prog = frappe.get_doc("Program", program)
		submitted = frappe.get_all(
			cy.CATALOG,
			filters={"program_name": program, "docstatus": 1},
			fields=["name", "workflow_state"],
			order_by="creation asc",
		)
		if not submitted:
			if earliest:
				_new_catalog(prog, earliest)
			continue
		active = [r for r in submitted if r.workflow_state == "Active"] or submitted[-1:]
		keep = active[-1].name
		for row in submitted:
			is_current = row.name == keep
			_fill(frappe.get_doc(cy.CATALOG, row.name), prog, earliest if is_current else None)
			frappe.db.set_value(
				cy.CATALOG,
				row.name,
				{"workflow_state": "Active" if is_current else "Superseded", "active": int(is_current)},
				update_modified=False,
			)
	_bind_enrollments()


def _window(term):
	if not term:
		return {}
	return {
		"academic_term_from": term.name,
		"starts_on": term.term_start_date,
		"catalog_year": term.academic_year or term.name,
	}


def _new_catalog(prog, term):
	doc = frappe.new_doc(cy.CATALOG)
	doc.program_name = prog.name
	doc.academic_term_from = term.name
	cy.copy_from_program(doc, prog)
	doc.flags.ignore_permissions = True
	doc.insert()
	frappe.db.set_value(
		cy.CATALOG,
		doc.name,
		{"docstatus": 1, "workflow_state": "Active", "active": 1},
		update_modified=False,
	)
	for child in CHILD_TABLES.values():
		frappe.db.set_value(
			child, {"parent": doc.name, "parenttype": cy.CATALOG}, "docstatus", 1, update_modified=False
		)


def _fill(doc, prog, term):
	"""Give a submitted policy the Program's academic section, once."""
	values = {field: prog.get(field) for field in cy.SCALARS}
	values.update(_window(term))
	frappe.db.set_value(cy.CATALOG, doc.name, values, update_modified=False)
	if doc.catalog_courses or doc.catalog_track_courses:
		return
	scratch = frappe.new_doc(cy.CATALOG)
	cy.copy_from_program(scratch, prog)
	for fieldname in ("catalog_courses", "catalog_tracks", "catalog_track_courses", "honors_levels"):
		for idx, source in enumerate(scratch.get(fieldname) or [], start=1):
			row = frappe.get_doc(
				{
					**{k: v for k, v in source.as_dict().items() if k not in cy.ROW_META},
					"doctype": CHILD_TABLES[fieldname],
					"parent": doc.name,
					"parenttype": cy.CATALOG,
					"parentfield": fieldname,
					"idx": idx,
					"docstatus": 1,
				}
			)
			row.db_insert()


def _bind_enrollments():
	ongoing = set(frappe.get_all("Program", filters={"is_ongoing": 1}, pluck="name"))
	for pe in frappe.get_all(
		"Program Enrollment",
		filters={"docstatus": 1, "graduation_policy": ("is", "not set")},
		fields=["name", "program", "academic_term", "enrollment_date"],
	):
		if pe.program in ongoing:
			continue
		catalog = cy.resolve(pe.program, cy.entry_date(pe))
		if catalog:
			frappe.db.set_value(
				"Program Enrollment", pe.name, "graduation_policy", catalog, update_modified=False
			)
