import frappe


def get_context(context):
	"""A returning student who can't use their old email asks the registrar to move their record
	(decisions/118 §1). Guest-reachable: they can't sign in, which is the problem."""
	context.no_cache = 1
	context.title = frappe._("Returning student")
	context.programs = frappe.get_all("Program", filters={"published": 1}, pluck="name", order_by="name asc")
	return context
