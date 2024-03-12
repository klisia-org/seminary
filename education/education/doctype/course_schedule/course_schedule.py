# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
import calendar
from datetime import timedelta
from dateutil import relativedelta


class CourseSchedule(Document):
	def validate(self):
		self.instructor_name = frappe.db.get_value(
			"Instructor", self.instructor1
		)
		self.validate_date()
		self.validate_time()
		

	def validate_date(self):
			academic_term = self.academic_term
			start_date, end_date = frappe.db.get_value(
				"Academic Term", academic_term, ["term_start_date", "term_end_date"]
			)
			# Convert self.c_datestart and self.c_dateend to date objects
			course_datestart = datetime.strptime(self.c_datestart, '%Y-%m-%d').date()
			course_dateend = datetime.strptime(self.c_dateend, '%Y-%m-%d').date()
			
			if (
				start_date
				and end_date
				and ((course_datestart < start_date)
		 		 or (course_dateend > end_date))
			):
				frappe.throw(
					_(
						"Schedule date selected does not lie within the Academic Term."
					).format(self.academic_term)
				)

			
	def validate_time(self):
		"""Validates if from_time is greater than to_time"""
		if self.from_time > self.to_time:
			frappe.throw(_("From Time cannot be greater than To Time."))


		@frappe.whitelist()
		def get_meeting_dates(self):
			"""Returns a list of meeting dates and also creates a child document for each meeting date with meeting time"""		
			while current_date <= self.c_dateend:
				if days_of_week[current_date.weekday()]:
					meeting_dates.append(current_date)
				current_date += timedelta(days=1)

			meeting_dates = []
			days_of_week = [self.monday, self.tuesday, self.wednesday, self.thursday, self.friday, self.saturday, self.sunday]
			current_date = self.c_datestart
			while current_date <= self.c_dateend:
				if days_of_week[current_date.weekday()]:
					meeting_dates.append(current_date)
					# Create a new child document for each meeting date
					child_doc = frappe.new_doc("Course Schedule Meeting Dates")
					child_doc.parent = self.name
					child_doc.cs_meetdate = current_date
					child_doc.cs_fromtime = self.from_time
					child_doc.cs_totime = self.to_time
					child_doc.insert()
					current_date += timedelta(days=1)
			return meeting_dates