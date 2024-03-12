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
		
		self.validate_time()
	
	
	def validate_time(self):
		"""Validates if from_time is greater than to_time"""
		if self.from_time > self.to_time:
			frappe.throw(_("From Time cannot be greater than To Time."))

	@frappe.whitelist()
	def get_meeting_dates(self):
		meeting_dates = []
		"""Returns a list of meeting dates and also creates a child document for each meeting date with meeting time"""     
		days_of_week = [self.monday, self.tuesday, self.wednesday, self.thursday, self.friday, self.saturday, self.sunday]
		current_date = self.c_datestart
		while current_date <= self.c_dateend:
			if days_of_week[current_date.weekday()]:
				meeting_dates.append(current_date)
				# Create a new child document for each meeting date
				child_doc = frappe.doc.append("Course Schedule Meeting Dates", {
					"parent": self.name,
					"cs_meetdate": current_date,
					"cs_fromtime": self.from_time,
					"cs_totime": self.to_time
				})
				print(child_doc)
				current_date += timedelta(days=1)
		return meeting_dates
