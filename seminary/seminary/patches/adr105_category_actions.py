"""decisions/105 §2: the starter categories get their actions on existing
sites too, so a Grader stops editing the course the day this lands. Every
other category gets all four, which is what it could do before.

The starter categories were named in the site's language at install, so both
the English name and its translation match."""

import frappe

from seminary.install import CATEGORY_ACTIONS, category_action_defaults


def execute():
	lang = frappe.db.get_single_value("System Settings", "language") or "en"
	starter = {}
	for english in CATEGORY_ACTIONS:
		starter[english] = english
		starter[frappe._(english, lang=lang)] = english
	for name in frappe.get_all("Instructor Category", pluck="name"):
		# Not a starter category: all four, as category_action_defaults gives.
		values = category_action_defaults(starter.get(name, ""))
		frappe.db.set_value("Instructor Category", name, values, update_modified=False)
