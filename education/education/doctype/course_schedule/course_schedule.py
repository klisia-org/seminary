# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document


class CourseSchedule(Document):
	def validate(self):
		self.instructor_name = frappe.db.get_value(
			"Instructor", self.instructor, "instructor_name"
		)
		self.set_title()
		self.validate_course()
		self.validate_date()
		self.validate_time()
		self.validate_overlap()

	def set_title(self):
		"""Set document Title"""
		self.title = (
			self.course
			+ " by "
			+ (self.instructor_name if self.instructor_name else self.instructor)
		)

	def validate_date(self):
			academic_term = self.academic_term
			start_date, end_date = frappe.db.get_value(
				"Academic Term", academic_term, ["term_start_date", "term_end_date"]
			)
			if (
				start_date
				and end_date
				and (self.c_datestart < start_date or self.c_dateend > end_date)
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

		"""Handles specicfic case to update schedule date in calendar """
		if isinstance(self.from_time, str):
			try:
				datetime_obj = datetime.strptime(self.from_time, "%Y-%m-%d %H:%M:%S")
				self.schedule_date = datetime_obj
			except ValueError:
				pass

	def validate_overlap(self):
		"""Validates overlap for Instructor, Room"""

		from education.education.utils import validate_overlap_for

		validate_overlap_for(self, "Course Schedule", "instructor")
		validate_overlap_for(self, "Course Schedule", "room")

		@frappe.whitelist()
		def get_meeting_dates(self):
			meeting_dates = []
			days_of_week = [self.monday, self.tuesday, self.wednesday, self.thursday, self.friday, self.saturday, self.sunday]
			current_date = self.c_datestart
			import calendar
			from datetime import timedelta
			from dateutil import relativedelta
			while current_date <= self.c_dateend:
				if days_of_week[current_date.weekday()]:
					meeting_dates.append(current_date)
				current_date += timedelta(days=1)

			return meeting_dates