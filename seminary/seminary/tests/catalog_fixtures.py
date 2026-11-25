# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Catalog years for tests (decisions/115).

A graduating program can't take enrollments, or be published, until it has a catalog year. A
fixture that enrolls students or publishes a program calls `ensure_catalog` once its courses are
in place: the catalog is a copy of the Program at that moment, from the site's earliest term, so it
covers any enrollment a test makes.
"""

import frappe


def earliest_term():
	rows = frappe.get_all(
		"Academic Term",
		filters={"term_start_date": ("is", "set")},
		pluck="name",
		order_by="term_start_date asc",
		limit=1,
	)
	if rows:
		return rows[0]
	from seminary.seminary.tests.cohort_fixtures import current_term

	return current_term()


def ensure_catalog(program):
	"""The program's catalog year, published from the Program as it is now if it has none."""
	from seminary.seminary.catalog_year import latest, publish_first_catalog

	name = program if isinstance(program, str) else program.name
	if frappe.db.get_value("Program", name, "is_ongoing"):
		return None
	return latest(name) or publish_first_catalog(name, earliest_term())


def publish_program(program):
	"""Give a program its catalog year, then publish it."""
	name = program if isinstance(program, str) else program.name
	ensure_catalog(name)
	doc = frappe.get_doc("Program", name)
	if not doc.published:
		doc.published = 1
		doc.save(ignore_permissions=True)
	return doc


def purge_catalogs(program_like):
	"""Delete the catalog years (and their rows) of programs whose name is LIKE `program_like`, for
	suites that commit their fixtures and purge them by prefix."""
	from seminary.seminary.catalog_year import CATALOG

	names = frappe.get_all(CATALOG, filters={"program_name": ("like", program_like)}, pluck="name")
	if not names:
		return
	for child in (
		"Catalog Course",
		"Catalog Track",
		"Catalog Track Course",
		"Honors Levels",
		"Program Grad Req Items",
	):
		frappe.db.delete(child, {"parent": ("in", names), "parenttype": CATALOG})
	frappe.db.delete("Comment", {"reference_doctype": CATALOG, "reference_name": ("in", names)})
	frappe.db.delete(CATALOG, {"name": ("in", names)})
