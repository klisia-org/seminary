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
from frappe.utils import add_days, getdate

from seminary.seminary.utils import OverlapError
import secrets


class CourseSchedule(Document):
    @frappe.whitelist()
    def validate(self):
        self.generate_token()
        if frappe.flags.in_demo_install:
            return
        self.validate_date()
        self.validate_time()
        self.validate_assessment_criteria()
        
    def clean_name(self):
        if self.name and ("/" in self.name or "\\" in self.name):
           # Just remove forward slashes and let Frappe handle the rest
           self.name = self.course_schedule_name.replace("/", "-").replace("\\", "-")

    def validate_assessment_criteria(self):
        """Validates if the total weightage of all assessment criteria is 100%"""
        if self.courseassescrit_sc:
            total_weight_scac = 0
            for criteria in self.courseassescrit_sc:
                if criteria.extracredit_scac == 0:
                    total_weight_scac += criteria.weight_scac or 0
                elif criteria.extracredit_scac == 1:
                    continue
            if total_weight_scac != 100:
                frappe.throw(
                    _("Total Weight of all Assessment Criteria must total 100%")
                )

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
            and ((course_datestart < start_date) or (course_dateend > end_date))
        ):
            frappe.throw(
                _(
                    "Schedule date selected does not lie within the Academic Term: {}"
                ).format(self.academic_term)
            )

    def validate_time(self):
        """Validates if from_time is greater than to_time"""
        if (
            self.is_new()
            or self.has_value_changed("from_time")
            or self.has_value_changed("to_time")
        ):
            if self.from_time and self.to_time:
                if self.from_time > self.to_time:
                    frappe.throw(_("From Time cannot be greater than To Time."))

    def generate_token(self):
        if not self.calendar_token:
            self.calendar_token = secrets.token_hex(32)

    @frappe.whitelist()
    def regenerate_token(self):
        self.calendar_token = secrets.token_hex(32)
        self.save()
        return self.calendar_token

    @frappe.whitelist()
    def schedule_dates(self, days):
        # Clear existing meeting dates
        frappe.db.sql(
            "DELETE FROM `tabCourse Schedule Meeting Dates` WHERE parent=%s", self.name
        )

        """Returns a list of meeting dates and also creates a child document for each meeting date with meeting time"""
        meeting_dates = []
        meeting_dates_errors = []
        # days_of_week = [self.monday, self.tuesday, self.wednesday, self.thursday, self.friday, self.saturday, self.sunday]
        current_date = self.c_datestart
        # final_date = datetime.strptime(self.c_dateend, "%Y-%m-%d")

        while current_date <= self.c_dateend:
            if calendar.day_name[getdate(current_date).weekday()] in days:
                meeting_date = self.save_dates(current_date)
                try:
                    meeting_date.flags.ignore_permissions = True
                    meeting_date.save()
                    frappe.db.set_value("Course Schedule", self.name, "hasmtgdate", 1)
                except OverlapError:
                    meeting_dates_errors.append(current_date)
                else:
                    meeting_dates.append(meeting_date)
            current_date = add_days(current_date, 1)

        return dict(
            meeting_dates=meeting_dates,
            meeting_dates_errors=meeting_dates_errors,
        )

    @frappe.whitelist()
    def save_dates(self, current_date):
        """Define variables"""
        cs = self.name
        pt = "Course Schedule"
        pf = "cs_meetinfo"
        name = cs + "-" + str(current_date)

        # Create new meeting date
        meeting_date = frappe.new_doc("Course Schedule Meeting Dates")
        meeting_date.name = name
        meeting_date.parent = cs
        meeting_date.parentfield = pf
        meeting_date.parenttype = pt
        meeting_date.cs_meetdate = current_date
        meeting_date.cs_fromtime = self.from_time
        meeting_date.cs_totime = self.to_time
        return meeting_date
