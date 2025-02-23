import frappe
#from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.desk.page.setup_wizard.setup_wizard import make_records
import os
import re


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
	update_trigger_fee_events()
	delete_genders()
	update_grading_scale()
	
	

def setup_fixtures():
	records = [
		
		# Item Group Records
		{"doctype": "Item Group", "item_group_name": "Tuition"},
		# Customer Group Records
		{"doctype": "Customer Group", "customer_group_name": "Student"},
		{"doctype": "Customer Group", "customer_group_name": "Donor"},
		{"doctype": "Customer Group", "customer_group_name": "Church"},
		{"doctype": "Customer Group", "customer_group_name": "Denomination"},
		{"doctype": "Customer Group", "customer_group_name": "Seminary"},
		{"doctype": "Customer Group", "customer_group_name": "Para-church Organization"},
		# Stock Item Records
		{"doctype": "Item", "item_code": "Credit hour", "item_name": "Credit hour", "item_group": "Tuition", "stock_uom": "Unit", "is_sales_item": 1},
		{"doctype": "Item", "item_code": "Program Admission", "item_name": "Program Admission", "item_group": "Tuition", "stock_uom": "Unit", "is_sales_item": 1},
		{"doctype": "Item", "item_code": "Donation for Scholarship", "item_name": "Donation for Scholarship", "item_group": "Tuition", "stock_uom": "Unit", "is_sales_item": 1},
		
	
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
def update_trigger_fee_events():
		for trigger in (
			_("Program Enrollment"),
			_("Course Enrollment"),
			_("New Academic Year"),
			_("New Academic Term"),
			_("Monthly"),
		):
			doc = frappe.new_doc("Trigger Fee Event")
			doc.trigger = trigger
			doc.active = 1
			doc.insert(ignore_permissions=True, ignore_if_duplicate=True)

def delete_genders():
	# Delete auto inserted genders 
	frappe.db.sql("DELETE FROM `tabGender' WHERE name NOT IN ('Male', 'Female')")

def update_grading_scale():
	# Create Default Grading Scale and populate child table Grading Scale Interval
	if not frappe.db.exists("Grading Scale", "Default"):
		doc = frappe.get_doc({
			"doctype": "Grading Scale",
			"grading_scale_name": "Default Grading Scale",
			"maxnumgrade": 100,
			"grscale_type": "Points",
			
			"interval": [
				{"grade_code": "A+", "threshold": 98, "grade_description": "A+", "grade_pass": "Pass"},
				{"grade_code": "A", "threshold": 96, "grade_description": "A", "grade_pass": "Pass"},
				{"grade_code": "A-", "threshold": 94, "grade_description": "A-", "grade_pass": "Pass"},
				{"grade_code": "B+", "threshold": 92, "grade_description": "B+", "grade_pass": "Pass"},
				{"grade_code": "B", "threshold": 89, "grade_description": "B", "grade_pass": "Pass"},
				{"grade_code": "B-", "threshold": 86, "grade_description": "B-", "grade_pass": "Pass"},
				{"grade_code": "C+", "threshold": 83, "grade_description": "C+", "grade_pass": "Pass"},
				{"grade_code": "C", "threshold": 80, "grade_description": "C", "grade_pass": "Pass"},
				{"grade_code": "C-", "threshold": 77, "grade_description": "C-", "grade_pass": "Pass"},
				{"grade_code": "D+", "threshold": 74, "grade_description": "D+", "grade_pass": "Pass"},
				{"grade_code": "D", "threshold": 72, "grade_description": "D", "grade_pass": "Pass"},
				{"grade_code": "D-", "threshold": 69, "grade_description": "D-", "grade_pass": "Pass"},
				{"grade_code": "F", "threshold": 0, "grade_description": "F", "grade_pass": "Fail"},
			]
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()



