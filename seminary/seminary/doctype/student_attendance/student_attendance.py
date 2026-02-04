# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from erpnext import get_default_company

# from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday
from frappe import _
from frappe.model.document import Document
from frappe.utils import formatdate, get_link_to_form, getdate


class StudentAttendance(Document):
    pass


# 	def validate(self):
# 		self.set_date()
# 		self.validate_student()
# 		self.validate_duplication()
# 		self.validate_is_holiday()

# 	def set_date(self):
# 		if self.course_schedule:
# 			self.date = frappe.db.sql(
# 				"""select min(smd.cs_meetdate)
# 				from `tabCourse Schedule`cs, `tabCourse Schedule Meeting Dates` smd
# 				where smd.parent = cs.name and
# 				smd.attendance = 0 and
# 				cs.name = %s""", self.course_schedule)[0][0]
# 		else:
# 			frappe.throw(_("There is no date to take attendance for."))


# 	def validate_student(self):
# 		if self.course_schedule:
# 			students = frappe.get_all(
# 				"Scheduled Course Roster",
# 				filters={"course_sc": self.course_schedule},
# 				fields=["student"],
# 			)
# 			students = [student.student for student in students]


# 	def validate_duplication(self):
# 		"""Check if the Attendance Record is Unique"""
# 		attendance_record = None
# 		attendance_record = frappe.db.exists(
# 				"Student Attendance",
# 				{
# 					"student": self.student,
# 					"course_schedule": self.course_schedule,
# 					"docstatus": ("!=", 2),
# 					"name": ("!=", self.name),
# 				},
# 			)


# 		if attendance_record:
# 			record = get_link_to_form("Student Attendance", attendance_record)
# 			frappe.throw(
# 				_("Student Attendance record {0} already exists against the Student {1}").format(
# 					record, frappe.bold(self.student)
# 				),
# 				title=_("Duplicate Entry"),
# 			)

# 	def validate_is_holiday(self):
# 		holiday_list = get_holiday_list()
# 		if is_holiday(holiday_list, self.date):
# 			frappe.throw(
# 				_("Attendance cannot be marked for {0} as it is a holiday.").format(
# 					frappe.bold(formatdate(self.date))
# 				)
# 			)


# def get_holiday_list(company=None):
# 	if not company:
# 		company = get_default_company() or frappe.get_all("Company")[0].name

# 	holiday_list = frappe.get_cached_value("Company", company, "default_holiday_list")
# 	if not holiday_list:
# 		frappe.throw(
# 			_("Please set a default Holiday List for Company {0}").format(
# 				frappe.bold(get_default_company())
# 			)
# 		)
# 	return holiday_list
