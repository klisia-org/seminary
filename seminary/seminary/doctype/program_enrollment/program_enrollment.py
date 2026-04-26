# Copyright (c) 2015, Frappe and contributors
# For license information, please see license.txt


import frappe
from frappe import _, msgprint
from frappe.desk.reportview import get_match_cond
from frappe.model.document import Document
from frappe.query_builder.functions import Min
from frappe.utils import comma_and, get_link_to_form, getdate


class ProgramEnrollment(Document):
    def validate(self):
        if frappe.flags.in_demo_install:
            return
        self.set_student_name()
        self.validate_duplication()
        self.validate_academic_term()
        self.validate_emphases()
        self.set_expected_graduation_date()

    def set_student_name(self):
        if not self.student_name:
            self.student_name = frappe.db.get_value(
                "Student", self.student, "student_name"
            )

    def before_submit(self):
        self.snapshot_graduation_requirements()

    def on_submit(self):
        self.update_student_joining_date()

    def set_expected_graduation_date(self):
        if self.expected_graduation_date:
            return
        from seminary.seminary.graduation import compute_expected_graduation_date

        default = compute_expected_graduation_date(self)
        if default:
            self.expected_graduation_date = default

    def snapshot_graduation_requirements(self):
        from seminary.seminary.graduation import (
            snapshot_graduation_requirements as _snapshot,
        )

        if self.graduation_requirements:
            return
        _snapshot(self)

    def validate_academic_term(self):
        today = getdate()
        start_date, end_date = frappe.db.get_value(
            "Academic Term", self.academic_term, ["term_start_date", "term_end_date"]
        )
        if self.enrollment_date:
            if getdate(self.enrollment_date) < today:
                frappe.throw(
                    _("Enrollment Date cannot be before today").format(
                        get_link_to_form("Academic Term", self.academic_term)
                    )
                )

            if end_date and getdate(self.enrollment_date) > getdate(end_date):
                frappe.throw(
                    _(
                        "Enrollment Date cannot be after the End Date of the Academic Term {0}"
                    ).format(get_link_to_form("Academic Term", self.academic_term))
                )

    def validate_duplication(self):
        enrollment = frappe.db.exists(
            "Program Enrollment",
            {
                "student": self.student,
                "program": self.program,
                "academic_term": self.academic_term,
                "docstatus": ("<", 2),
                "name": ("!=", self.name),
            },
        )
        if enrollment:
            frappe.throw(_("Student is already enrolled."))

    def validate_emphases(self):
        if not self.emphases:
            return

        program = frappe.get_cached_doc("Program", self.program)
        allow_multiple = program.allow_multiple_emphases

        active_emphases = [e for e in self.emphases if e.status == "Active"]

        if not allow_multiple and len(active_emphases) > 1:
            frappe.throw(
                _(
                    "Program {0} does not allow multiple emphases. Only one active emphasis is permitted."
                ).format(self.program)
            )

        # Validate each emphasis row
        for emphasis in self.emphases:
            track = frappe.db.get_value(
                "Program Track",
                emphasis.emphasis_track,
                [
                    "is_emphasis",
                    "emphasis_declaration",
                    "min_credits_to_declare",
                    "parent",
                ],
                as_dict=True,
            )
            if not track:
                frappe.throw(
                    _("Emphasis track {0} not found.").format(emphasis.emphasis_track)
                )

            if track.parent != self.program:
                frappe.throw(
                    _("Track {0} does not belong to program {1}.").format(
                        emphasis.emphasis_track, self.program
                    )
                )

            if not track.is_emphasis:
                frappe.throw(
                    _("Track {0} is not marked as an emphasis.").format(
                        emphasis.emphasis_track
                    )
                )

            # Check declaration timing
            if (
                emphasis.status == "Active"
                and track.emphasis_declaration == "At Enrollment"
            ):
                if self.docstatus == 1:
                    frappe.throw(
                        _(
                            "Emphasis {0} can only be declared at enrollment time (before submission)."
                        ).format(emphasis.emphasis_track)
                    )

            # Check minimum credits for declaration
            if (
                emphasis.status == "Active"
                and track.min_credits_to_declare
                and (self.totalcredits or 0) < track.min_credits_to_declare
            ):
                frappe.throw(
                    _(
                        "Student needs at least {0} credits before declaring emphasis {1}. Current credits: {2}"
                    ).format(
                        track.min_credits_to_declare,
                        emphasis.emphasis_track,
                        self.totalcredits or 0,
                    )
                )

            # Check auto-grant tracks cannot be manually added as Active
            if (
                emphasis.status == "Active"
                and track.emphasis_declaration == "Auto-grant"
            ):
                frappe.throw(
                    _(
                        "Emphasis {0} is set to Auto-grant and cannot be manually declared. It will be assigned automatically when requirements are met."
                    ).format(emphasis.emphasis_track)
                )

            # Set dropped_date when status changes to Dropped
            if emphasis.status == "Dropped" and not emphasis.dropped_date:
                emphasis.dropped_date = getdate()

        # Check for duplicate active emphases on the same track
        active_tracks = [e.emphasis_track for e in active_emphases]
        if len(active_tracks) != len(set(active_tracks)):
            frappe.throw(_("Cannot have duplicate active emphases on the same track."))

    def update_student_joining_date(self):
        table = frappe.qb.DocType("Program Enrollment")
        date = (
            frappe.qb.from_(table)
            .select(Min(table.enrollment_date).as_("enrollment_date"))
            .where(table.student == self.student)
        ).run(as_dict=True)

        if date:
            frappe.db.set_value(
                "Student", self.student, "joining_date", date[0].enrollment_date
            )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_program_courses(doctype, txt, searchfield, start, page_len, filters):
    if not filters.get("program"):
        frappe.msgprint(_("Please select a Program first."))
        return []

    doctype = "Program Course"
    return frappe.db.sql(
        """select course, course_name from `tabProgram Course`
		where  parent = %(program)s and course like %(txt)s {match_cond}
		order by
			if(locate(%(_txt)s, course), locate(%(_txt)s, course), 99999),
			idx desc,
			`tabProgram Course`.course asc
		limit {start}, {page_len}""".format(
            match_cond=get_match_cond(doctype), start=start, page_len=page_len
        ),
        {
            "txt": "%{0}%".format(txt),
            "_txt": txt.replace("%", ""),
            "program": filters["program"],
        },
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_emphasis(doctype, txt, searchfield, start, page_len, filters):
    if not filters.get("program"):
        frappe.msgprint(_("Please select a Program first."))
        return []

    return frappe.db.sql(
        """SELECT name, track_name
        FROM `tabProgram Track`
        WHERE parent = %(program)s
            AND is_emphasis = 1
            AND (name LIKE %(txt)s OR track_name LIKE %(txt)s)
        ORDER BY track_name
        LIMIT %(start)s, %(page_len)s""",
        {
            "program": filters["program"],
            "txt": "%{0}%".format(txt),
            "start": start,
            "page_len": page_len,
        },
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_students(doctype, txt, searchfield, start, page_len, filters):
    enrolled_students = []
    if not filters.get("academic_term"):
        filters["academic_term"] = frappe.defaults.get_defaults().academic_term
        enrolled_students = frappe.get_list(
            "Program Enrollment",
            filters={
                "academic_term": filters.get("academic_term"),
            },
            fields=["student"],
        )

    students = [d.student for d in enrolled_students] if enrolled_students else [""]

    return frappe.db.sql(
        """select
			name, student_name from tabStudent
		where
			name not in (%s)
		and
			`%s` LIKE %s
		order by
			idx desc, name
		limit %s, %s"""
        % (", ".join(["%s"] * len(students)), searchfield, "%s", "%s", "%s"),
        tuple(students + ["%%%s%%" % txt, start, page_len]),
    )
