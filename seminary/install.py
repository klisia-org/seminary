import frappe
#from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.desk.page.setup_wizard.setup_wizard import make_records


# TODO: create uninstall file and remove all the custom fields, roles, assessment groups, fixtures, etc
# TODO: Remove all Items created when Fee Category is created
# TODO: Remove all Customers (with group = Student) & Users created (with role = Student) when Student is created.


def after_install():
	setup_fixtures()
	create_studentappl_role()
	create_student_role()
	create_registrar_role()
	create_instructor_role()
	get_custom_fields()
	

def setup_fixtures():
	records = [
		# Party Type Records
		{"doctype": "Party Type", "party_type": "Student", "account_type": "Receivable"},	
		# Item Group Records
		{"doctype": "Item Group", "item_group_name": "Tuition"},
		# Customer Group Records
		{"doctype": "Customer Group", "customer_group_name": "Student"},
		{"doctype": "Customer Group", "customer_group_name": "Donor"},
		{"doctype": "Customer Group", "customer_group_name": "Church"},
		{"doctype": "Customer Group", "customer_group_name": "Denomination"},
		{"doctype": "Customer Group", "customer_group_name": "Seminary"},
		{"doctype": "Customer Group", "customer_group_name": "Para-church Organization"},
		]
	make_records(records)


def create_studentappl_role():
	if not frappe.db.exists("Role", "Student Applicant"):
		frappe.get_doc({"doctype": "Role", "role_name": "Student Applicant", "desk_access": 0}).save()

def create_student_role():
	if not frappe.db.exists("Role", "Student"):
		frappe.get_doc({"doctype": "Role", "role_name": "Student", "desk_access": 0}).save()

def create_registrar_role():
	if not frappe.db.exists("Role", "Registrar"):
		frappe.get_doc({"doctype": "Role", "role_name": "Registrar", "desk_access": 1}).save()

def create_instructor_role():
	if not frappe.db.exists("Role", "Instructor"):
		frappe.get_doc({"doctype": "Role", "role_name": "Instructor", "desk_access": 1}).save()

def get_custom_fields():
	"""Seminary specific custom fields that needs to be added to the Sales Invoice DocType."""
	return {
		"Sales Invoice": [
			{
				"fieldname": "student_info_section",
				"fieldtype": "Section Break",
				"label": "Student Info",
				"collapsible": 1,
				"insert_after": "ignore_pricing_rule",
			},
			{
				"fieldname": "student",
				"fieldtype": "Link",
				"label": "Student",
				"options": "Student",
				"insert_after": "student_info_section",
			},
				],}
