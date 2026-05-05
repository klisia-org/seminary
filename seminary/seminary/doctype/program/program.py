# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.utils import format_date, getdate, today
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

    def get_context(self, context):
        context.open_windows = []
        context.continuous_term = None

        if self.enrollment_mode == "Timed":
            context.open_windows = self._resolve_open_windows()
        elif self.enrollment_mode == "Continuous" and self.display_cta:
            context.continuous_term = self._resolve_continuous_term()
            if not context.continuous_term:
                frappe.log_error(
                    f"Program {self.name} is Continuous with display_cta=1 "
                    "but no current/upcoming Academic Term is configured.",
                    "program.get_context",
                )

    def _resolve_open_windows(self):
        windows = frappe.db.sql(
            """
            SELECT ta.name, ta.academic_term, ta.admission_start_date,
                   ta.admission_end_date, ta.introduction,
                   at.term_name, at.term_for_web,
                   at.term_start_date, at.term_end_date
            FROM `tabTerm Admission` ta
            INNER JOIN `tabTerm Admission Program` tap
                    ON tap.parent = ta.name
                   AND tap.parenttype = 'Term Admission'
            INNER JOIN `tabAcademic Term` at
                    ON at.name = ta.academic_term
            WHERE ta.docstatus = 1
              AND ta.published = 1
              AND ta.admission_end_date >= %(today)s
              AND tap.program = %(program)s
            ORDER BY ta.admission_start_date ASC
            """,
            {"today": today(), "program": self.name},
            as_dict=True,
        )
        today_d = getdate()
        for w in windows:
            w["term_label"] = w.term_for_web or w.term_name or w.academic_term
            w["apply_window_display"] = "{} – {}".format(
                format_date(w.admission_start_date), format_date(w.admission_end_date)
            )
            w["term_window_display"] = (
                "{} – {}".format(
                    format_date(w.term_start_date), format_date(w.term_end_date)
                )
                if w.term_start_date and w.term_end_date
                else None
            )
            start = getdate(w.admission_start_date)
            end = getdate(w.admission_end_date)
            if start > today_d:
                w["status_label"] = _("Opens soon")
                w["indicator"] = "blue"
            elif end == today_d:
                w["status_label"] = _("Last day to apply")
                w["indicator"] = "red"
            else:
                w["status_label"] = _("Now accepting applications")
                w["indicator"] = "green"
        return windows

    def _resolve_continuous_term(self):
        fields = [
            "name",
            "term_name",
            "term_for_web",
            "term_start_date",
            "term_end_date",
        ]
        current = frappe.db.get_value(
            "Academic Term",
            {"iscurrent_acterm": 1},
            fields,
            as_dict=True,
        )
        if not current:
            upcoming = frappe.get_all(
                "Academic Term",
                filters={"term_start_date": [">", today()]},
                fields=fields,
                order_by="term_start_date asc",
                limit=1,
            )
            current = upcoming[0] if upcoming else None
        if not current:
            return None
        current["term_label"] = (
            current.get("term_for_web") or current.get("term_name") or current["name"]
        )
        if current.get("term_start_date") and current.get("term_end_date"):
            current["term_window_display"] = "{} – {}".format(
                format_date(current["term_start_date"]),
                format_date(current["term_end_date"]),
            )
        else:
            current["term_window_display"] = None
        return current

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
