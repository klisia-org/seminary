# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""ADR 081: Excused absences, leave of absence in the count, and the decision
Send Grades asks for when a student is over the absence limit."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from seminary.seminary import absence_decisions as ad
from seminary.seminary import attendance
from seminary.seminary.program_status import (
    LEAVE_STATUS,
    return_from_leave,
    set_program_status,
)
from seminary.seminary.tests import cohort_fixtures as fx


def _section():
    cs = frappe.get_doc(
        {
            "doctype": "Course Schedule",
            "name": fx.uid("CS"),
            "workflow_state": "Grading",
            "open_ended": 1,
        }
    )
    cs.db_insert()
    return cs.name


def _meeting(cs, date):
    row = frappe.get_doc(
        {
            "doctype": "Course Schedule Meeting Dates",
            "name": frappe.generate_hash(length=10),
            "parent": cs,
            "parenttype": "Course Schedule",
            "parentfield": "cs_meetinfo",
            "cs_meetdate": date,
        }
    )
    row.db_insert()
    return row.name


def _roster(cs, student, program, **values):
    doc = frappe.get_doc(
        {
            "doctype": "Scheduled Course Roster",
            "name": f"{cs}-{student}",
            "course_sc": cs,
            "student": student,
            "stuname_roster": student,
            "program_std_scr": program,
            "active": 1,
            "audit_bool": 0,
            **values,
        }
    )
    doc.db_insert()
    return doc.name


def _attend(cs, student, date, status, meeting=None):
    return frappe.get_doc(
        {
            "doctype": "Student Attendance",
            "student": student,
            "course_schedule": cs,
            "date": date,
            "meeting": meeting,
            "status": status,
        }
    ).insert(ignore_permissions=True)


class ADR081Case(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.program = fx.make_program()
        self.student = fx.make_student()
        self.cs = _section()


class TestExcused(ADR081Case):
    def test_excused_is_neither_an_absence_nor_a_tardy(self):
        _attend(self.cs, self.student.name, add_days(today(), -3), "Absent")
        _attend(self.cs, self.student.name, add_days(today(), -2), "Excused")
        _attend(self.cs, self.student.name, add_days(today(), -1), "Tardy")
        self.assertEqual(attendance._counts(self.student.name, self.cs), (1, 1))

    def test_only_excused_before_the_class(self):
        future = add_days(today(), 5)
        with self.assertRaises(frappe.ValidationError):
            _attend(self.cs, self.student.name, future, "Absent")
        _attend(self.cs, self.student.name, future, "Excused")

    def test_an_unknown_status_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _attend(self.cs, self.student.name, today(), "Sick")

    def test_excusing_ahead_is_the_whole_list_and_not_the_roll(self):
        from seminary.seminary.api import mark_attendance

        future = add_days(today(), 7)
        meeting = _meeting(self.cs, future)
        who = [{"student": self.student.name, "stuname_roster": "S"}]
        mark_attendance(
            students_present=[],
            students_absent=[],
            students_excused=who,
            course_schedule=self.cs,
            date=future,
            meeting=meeting,
        )
        rows = frappe.get_all(
            "Student Attendance", filters={"meeting": meeting}, pluck="status"
        )
        self.assertEqual(rows, ["Excused"])
        self.assertFalse(
            frappe.db.get_value("Course Schedule Meeting Dates", meeting, "attendance")
        )

        mark_attendance(
            students_present=[],
            students_absent=[],
            students_excused=[],
            course_schedule=self.cs,
            date=future,
            meeting=meeting,
        )
        self.assertFalse(
            frappe.get_all("Student Attendance", filters={"meeting": meeting})
        )


class TestLeave(ADR081Case):
    def setUp(self):
        super().setUp()
        self.pe = fx.make_enrollment(self.student, self.program)

    def test_absences_on_leave_days_are_not_counted(self):
        start, back = add_days(today(), -10), add_days(today(), -4)
        set_program_status(
            self.pe.name, LEAVE_STATUS, category="Medical/LOA", effective_date=start
        )
        return_from_leave(self.pe.name, effective_date=back)

        self.assertEqual(
            attendance.leave_periods(self.student.name, self.program.name),
            [(getdate(start), getdate(back))],
        )
        _attend(self.cs, self.student.name, add_days(today(), -11), "Absent")  # before
        _attend(self.cs, self.student.name, add_days(today(), -7), "Absent")  # on leave
        _attend(self.cs, self.student.name, back, "Absent")  # the day back counts
        counts = attendance._counts(self.student.name, self.cs, self.program.name)
        self.assertEqual(counts, (2, 0))

    def test_an_open_leave_and_its_extension(self):
        start = add_days(today(), -5)
        set_program_status(
            self.pe.name, LEAVE_STATUS, category="Medical/LOA", effective_date=start
        )
        # Re-applying LOA extends it; it does not start a second period.
        set_program_status(
            self.pe.name, LEAVE_STATUS, category="Medical/LOA", effective_date=today()
        )
        periods = attendance.leave_periods(self.student.name, self.program.name)
        self.assertEqual(periods, [(getdate(start), None)])
        self.assertTrue(attendance.on_leave(today(), periods))


class TestDecisions(ADR081Case):
    def setUp(self):
        super().setUp()
        self.over = _roster(
            self.cs,
            self.student.name,
            self.program.name,
            attendance_alert_level=2,
            effective_absences=6,
            absence_limit=4,
        )
        other = fx.make_student()
        self.fine = _roster(
            self.cs, other.name, self.program.name, attendance_alert_level=1
        )

    def test_only_undecided_students_over_the_limit_are_asked_about(self):
        self.assertEqual([r.roster for r in ad.undecided(self.cs)], [self.over])
        with self.assertRaises(frappe.ValidationError):
            ad.assert_decided(self.cs)
        ad.assert_decided(self.cs, [self.fine])  # a partial send without them

    def test_keeping_the_grade_needs_a_reason(self):
        with self.assertRaises(frappe.ValidationError):
            ad.record_absence_decisions(
                self.cs, [{"roster": self.over, "decision": ad.KEEP, "reason": " "}]
            )
        ad.record_absence_decisions(
            self.cs, [{"roster": self.over, "decision": ad.KEEP, "reason": "Hospital"}]
        )
        row = frappe.db.get_value(
            "Scheduled Course Roster",
            self.over,
            ["absence_decision", "absence_decision_reason", "absence_decided_by"],
            as_dict=True,
        )
        self.assertEqual(
            (row.absence_decision, row.absence_decision_reason, row.absence_decided_by),
            (ad.KEEP, "Hospital", "Administrator"),
        )
        ad.assert_decided(self.cs)

    def test_no_recommendation_leaves_it_to_the_registrar(self):
        ad.record_absence_decisions(
            self.cs, [{"roster": self.over, "decision": ad.NO_RECOMMENDATION}]
        )
        ad.assert_decided(self.cs)
        ad.keep_grade_despite_absences(self.over, reason="Agreed with the dean")
        self.assertEqual(
            frappe.db.get_value(
                "Scheduled Course Roster", self.over, "absence_decision"
            ),
            ad.KEEP,
        )

    def test_failing_goes_through_fail_for_absence(self):
        with patch("seminary.seminary.api._fail_for_absence") as fail:
            ad.record_absence_decisions(
                self.cs, [{"roster": self.over, "decision": ad.FAIL}]
            )
        fail.assert_called_once_with(self.over)

    def test_a_student_not_waiting_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            ad.record_absence_decisions(
                self.cs, [{"roster": self.fine, "decision": ad.FAIL}]
            )

    def test_send_selected_grades_stops_for_an_undecided_student(self):
        from seminary.seminary.api import send_selected_grades

        with self.assertRaisesRegex(frappe.ValidationError, "over the absence limit"):
            send_selected_grades(self.cs, [self.over])
