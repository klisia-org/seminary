import frappe

def get_context(context):
	context.user = frappe.session.user
	print(context.user)
	student_name = frappe.db.sql("""select student_name from `tabStudent` where user = %s""", (context.user))
	context.student_name = student_name[0][0]
	print(context.student_name)



