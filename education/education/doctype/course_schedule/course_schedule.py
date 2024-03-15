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

	def convert_to_date(self, date):
		if isinstance(date, str):
			return datetime.strptime(date, "%Y-%m-%d").date()
		if isinstance(date, datetime):
			return date.date()
		return date
	
	def validate_date(self):
		academic_term = self.academic_term
		start_date, end_date = frappe.db.get_value(
		"Academic Term", academic_term, ["term_start_date", "term_end_date"]
            )
		start_date = self.convert_to_date(start_date)
		end_date = self.convert_to_date(end_date)
		course_datestart = self.c_datestart 
		course_dateend = self.c_dateend
		course_datestart = self.convert_to_date(course_datestart)
		course_dateend = self.convert_to_date(course_dateend) 
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
	def convert_to_time(self, time):
		if isinstance(time, str):
			return datetime.strptime(time, '%H:%M:%S').time()
		if isinstance(time, datetime):
			return time.time()
		return time
	
	def validate_time(self):
		"""Validates if from_time is greater than to_time"""
		if self.from_time > self.to_time:
			frappe.throw(_("From Time cannot be greater than To Time."))

	@frappe.whitelist()
	def get_meeting_dates(self):
		meeting_dates = []
		"""Returns a list of meeting dates and also creates a child document for each meeting date with meeting time"""     
		days_of_week = [self.monday, self.tuesday, self.wednesday, self.thursday, self.friday, self.saturday, self.sunday]
		current_date = datetime.strptime(self.c_datestart, "%Y-%m-%d")
		final_date = datetime.strptime(self.c_dateend, "%Y-%m-%d")
		while current_date <= final_date:
			if days_of_week[current_date.weekday()]:
				meeting_dates.append(current_date)
				current_date += timedelta(days=1)
		return meeting_dates
	@frappe.whitelist()
	def save_dates(self):
		"""Create child documents for each meeting date"""
		meeting_dates = self.get_meeting_dates()
		from_time = self.convert_to_time(self.from_time)
		to_time = self.convert_to_time(self.to_time)
		for meeting_date in meeting_dates:
			meeting = frappe.get_doc({
				"doctype": "Course Schedule Meeting Dates", 
				"parent": self.name,
				"parentfield": "cs_meetinfo",
				"parenttype": "Course Schedule", 
				"cs_meetdate": meeting_date,
				"cs_fromtime": from_time.strftime("%H:%M:%S"),
				"cs_totime": to_time.strftime("%H:%M:%S"),
				})
			meeting.insert()
		frappe.msgprint(_("Meeting Dates Created Successfully. Please save the document to continue."))
			