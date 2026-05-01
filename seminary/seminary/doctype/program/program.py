# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe.website.website_generator import WebsiteGenerator


class Program(WebsiteGenerator):
    def autoname(self):
        self.name = self.program_name

    def validate(self):
        # Free programs cannot gate enrollment on payment — there are no invoices.
        # Force the gating fields off so the CEI workflow conditions evaluate
        # cleanly regardless of fetch_from chain timing.
        if self.is_free:
            self.require_pay_submit = 0
            self.percent_to_pay = 0

    def get_course_list(self):
        program_course_list = self.courses
        course_list = [
            frappe.get_doc("Course", program_course.course)
            for program_course in program_course_list
        ]
        return course_list


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_program_tracks(doctype, txt, searchfield, start, page_len, filters):
    if not filters.get("program"):
        return []

    return frappe.db.sql(
        """SELECT name, track_name
        FROM `tabProgram Track`
        WHERE parent = %(program)s
            AND name LIKE %(txt)s
        ORDER BY track_name
        LIMIT %(start)s, %(page_len)s""",
        {
            "program": filters["program"],
            "txt": "%{0}%".format(txt),
            "start": start,
            "page_len": page_len,
        },
    )
