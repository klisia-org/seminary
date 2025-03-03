# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import set_name_by_naming_series
import time

class Instructor(Document):
	pass
	# def autoname(self):
	# 	naming_method = frappe.db.get_value(
	# 		"Seminary Settings", None, "instructor_created_by"
	# 	)
	# 	if not naming_method:
	# 		frappe.throw(
	# 			_("Please setup Instructor Naming System in Seminary > Seminary Settings")
	# 		)
	# 	else:
	# 		if naming_method == "Naming Series":
	# 			set_name_by_naming_series(self)
	# 		elif naming_method == "Employee Number":
	# 			if not self.employee:
	# 				frappe.throw(_("Please select Employee"))
	# 			self.name = self.employee
	# 		elif naming_method == "Full Name":
	# 			self.name = self.instructor_name

	# def validate(self):
	# 	self.validate_duplicate_employee()

	# def validate_duplicate_employee(self):
	# 	if self.employee and frappe.db.get_value(
	# 		"Instructor", {"employee": self.employee, "name": ["!=", self.name]}, "name"
	# 	):
	# 		frappe.throw(_("Employee ID is linked with another instructor"))


def get_timeline_data(doctype, name):
		"""Return timeline for course schedule meeting dates"""
		timeline_data = dict(
			frappe.db.sql(
			"""
			SELECT unix_timestamp(mt.cs_meetdate), count(mt.name)
			FROM `tabCourse Schedule Meeting Dates` mt
			JOIN `tabCourse Schedule` cs ON cs.name = mt.parent
			JOIN `tabCourse Schedule Instructors` csi ON cs.name = csi.parent
			WHERE csi.instructor = %s
			GROUP BY mt.cs_meetdate
			""",
			name,
		)
	)
		print(timeline_data)
		if not timeline_data:
			timeline_data = {int(time.time()): 0}  # Set current date as cs_meetdate if timeline_data is empty
		return timeline_data

@frappe.whitelist()
def update_instructorlog(doc):
	"""Update Instructor Log"""
	
	inst =frappe.get_doc("Instructor", doc)
	instructor = inst.name
	print("Instructor: " + instructor)
	"""Update Instructor log"""
	current_instructor_log = frappe.db.sql(
		"""
		select course, academic_term, inst_record, n_students
		from `tabInstructor Log`
		where parent = %s
		""",
		instructor, as_list=1,
	)
	full_instructor_log = frappe.db.sql(
		"""
		select cs.name, cs.academic_term, csi.inst_record, count(r.name) as students
		from `tabCourse Schedule Instructors` csi, `tabCourse Schedule` cs, `tabScheduled Course Roster` r 
		where csi.parent = cs.name and cs.name = r.course_sc and csi.instructor = %s
		group by cs.name, cs.academic_term, csi.inst_record
		""",
		instructor,	as_list=1,	
	)
	instructor_log = []
	for log in full_instructor_log:
		if current_instructor_log:
			if log not in current_instructor_log:
				instructor_log.append(log)
		else:
			instructor_log.append(log)
		
	if instructor_log:
		for log in instructor_log:
			doc = frappe.new_doc("Instructor Log")
			doc.course = log[0]
			doc.academic_term = log[1]
			doc.inst_record = log[2]
			doc.n_students = log[3]
			doc.parent = instructor
			doc.parentfield = "instructor_log"
			doc.parenttype = "Instructor"
			doc.save()
			frappe.db.commit()
		
	else:
		return
	
