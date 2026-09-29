# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/084: Send Grades advances the student; staff-enrolled programs."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import api, progression
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr083_bulk_enrollment import (
    _course,
    _enrollment,
    _program,
    _section,
    _term,
)


def _taken(pe, section, status="Pass", graded=True):
    """The student took `section`: a roster (active until grades are sent) and
    a transcript row carrying the final result once they are."""
    course = frappe.db.get_value("Course Schedule", section, "course")
    frappe.get_doc(
        {
            "doctype": "Scheduled Course Roster",
            "name": f"{section}-{pe.student}",
            "course_sc": section,
            "student": pe.student,
            "program_std_scr": pe.program,
            "stuname_roster": pe.student,
            "active": 0 if graded else 1,
            "audit_bool": 0,
        }
    ).db_insert()
    frappe.get_doc(
        {
            "doctype": "Program Enrollment Course",
            "name": frappe.generate_hash(length=10),
            "parent": pe.name,
            "parenttype": "Program Enrollment",
            "parentfield": "courses",
            "course": section,
            "course_name": course,
            "pec_finalgradecode": (
                ("B" if status == "Pass" else "F") if graded else None
            ),
            "status": status if graded else "Enrolled",
        }
    ).db_insert()


def _stage(pe):
    return frappe.db.get_value("Program Enrollment", pe.name, "current_std_term")


class ADR084Case(IntegrationTestCase):
    # IntegrationTestCase rolls back per class, not per test: without this, one
    # test's terms become the next test's "next Academic Term".
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        frappe.db.savepoint("adr084_test")
        # Far from any real term: "the next Academic Term" is found by start date,
        # so a site's own terms must not fall between these two.
        self.closing = _term("2091-01-10", "2091-05-10")
        self.next = _term("2091-05-11", "2091-08-30")
        self.a, self.b, self.c = _course(), _course(), _course()
        self.program = _program(
            [(self.a, 1), (self.b, 1), (self.c, 2)], terms_complete=3
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="adr084_test")
        super().tearDown()

    def rule(self, value):
        frappe.db.set_value("Program", self.program.name, "progression_rule", value)
        frappe.clear_document_cache("Program", self.program.name)


class TestSendGradesAdvances(ADR084Case):
    def test_one_pass_is_enough_by_default(self):
        pe = _enrollment(self.program, 1, self.closing)
        sa = _section(self.a, self.closing, state="Closed")
        _taken(pe, sa, "Pass")
        _taken(pe, _section(self.b, self.closing, state="Closed"), "Fail")
        progression.after_grades_sent(sa, [pe.name])
        self.assertEqual(_stage(pe), 2)
        self.assertEqual(
            frappe.db.get_value("Program Enrollment", pe.name, "advanced_from_term"),
            self.closing,
        )
        # Grades sent again for the same term move no one a second time.
        progression.after_grades_sent(sa, [pe.name])
        self.assertEqual(_stage(pe), 2)

    def test_failing_everything_holds_the_student(self):
        pe = _enrollment(self.program, 1, self.closing)
        sa = _section(self.a, self.closing, state="Closed")
        _taken(pe, sa, "Fail")
        self.assertEqual(progression.evaluate(pe.name, self.closing), "held")
        self.assertEqual(_stage(pe), 1)

    def test_waits_for_the_last_dated_section(self):
        pe = _enrollment(self.program, 1, self.closing)
        sa = _section(self.a, self.closing, state="Closed")
        _taken(pe, sa, "Pass")
        _taken(pe, _section(self.b, self.closing, state="Grading"), graded=False)
        self.assertIsNone(progression.evaluate(pe.name, self.closing))
        self.assertEqual(_stage(pe), 1)

    def test_an_open_ended_section_does_not_hold_it_back(self):
        pe = _enrollment(self.program, 1, self.closing)
        sa = _section(self.a, self.closing, state="Closed")
        _taken(pe, sa, "Pass")
        _taken(
            pe,
            _section(self.b, self.closing, state="Grading", open_ended=1),
            graded=False,
        )
        self.assertEqual(progression.evaluate(pe.name, self.closing), "advanced")

    def test_every_course_rule(self):
        self.rule(progression.EVERY_COURSE)
        pe = _enrollment(self.program, 1, self.closing)
        _taken(pe, _section(self.a, self.closing, state="Closed"), "Pass")
        _taken(pe, _section(self.b, self.closing, state="Closed"), "Fail")
        self.assertEqual(progression.evaluate(pe.name, self.closing), "held")

    def test_registrar_rule_never_moves_anyone(self):
        self.rule(progression.REGISTRAR)
        pe = _enrollment(self.program, 1, self.closing)
        _taken(pe, _section(self.a, self.closing, state="Closed"), "Pass")
        self.assertIsNone(progression.evaluate(pe.name, self.closing))
        self.assertEqual(_stage(pe), 1)

    def test_the_final_term_does_not_advance(self):
        pe = _enrollment(self.program, 3, self.closing)
        _taken(pe, _section(self.a, self.closing, state="Closed"), "Pass")
        self.assertIsNone(progression.evaluate(pe.name, self.closing))
        self.assertEqual(_stage(pe), 3)

    def test_send_grades_reaches_progression(self):
        pe = _enrollment(self.program, 1, self.closing)
        sa = _section(self.a, self.closing, state="Closed")
        _taken(pe, sa, "Pass")
        # Both Send Grades paths finish in _post_finalization + after_grades_sent;
        # the section is already Closed, so call the tail directly.
        api._post_finalization({pe.name})
        progression.after_grades_sent(sa, {pe.name})
        self.assertEqual(_stage(pe), 2)


class TestHeldBack(ADR084Case):
    def test_remove_from_program_cohort(self):
        frappe.db.set_value(
            "Program",
            self.program.name,
            "cohort_failure_policy",
            progression.REMOVE_FROM_COHORT,
        )
        frappe.clear_document_cache("Program", self.program.name)
        ctype = fx.make_cohort_type(category="Paced Program", program=self.program.name)
        leader = fx.make_person("Leader")
        cohort = fx.make_cohort(ctype.name, leader.name)
        pe = _enrollment(self.program, 1, self.closing)
        person = frappe.db.get_value("Student", pe.student, "person")
        member = fx.add_member(cohort.name, person)
        _taken(pe, _section(self.a, self.closing, state="Closed"), "Fail")
        progression.evaluate(pe.name, self.closing)
        self.assertEqual(
            frappe.db.get_value("Cohort Membership", member.name, "invite_status"),
            "Removed",
        )

    def test_staying_is_the_default(self):
        self.assertEqual(
            frappe.db.get_value("Program", self.program.name, "cohort_failure_policy"),
            "Stay in the current cohort",
        )


class TestChangeTerm(ADR084Case):
    def test_registrar_moves_one_student_with_a_reason(self):
        pe = _enrollment(self.program, 1, self.closing)
        _taken(pe, _section(self.a, self.closing, state="Closed"), "Fail")
        with self.assertRaises(frappe.ValidationError):
            progression.change_term(pe.name, 2, "")
        progression.change_term(pe.name, 2, "Continues despite a failed course")
        self.assertEqual(_stage(pe), 2)
        self.assertTrue(
            frappe.db.exists(
                "Comment",
                {
                    "reference_name": pe.name,
                    "content": ["like", "%Continues despite a failed course%"],
                },
            )
        )
        self.assertEqual(
            frappe.db.get_value("Program Enrollment", pe.name, "advanced_from_term"),
            self.closing,
        )
        # The term they were moved out of can't move them again.
        self.assertIsNone(progression.evaluate(pe.name, self.closing))
        self.assertEqual(_stage(pe), 2)

    def test_students_cannot_change_terms(self):
        pe = _enrollment(self.program, 1, self.closing)
        frappe.set_user(fx.make_user(roles=("Student",)).name)
        with self.assertRaises(frappe.PermissionError):
            progression.change_term(pe.name, 2, "please")


class TestStaffEnrolledPrograms(ADR084Case):
    def setUp(self):
        super().setUp()
        frappe.db.set_value(
            "Program",
            self.program.name,
            {"staff_enroll_only": 1, "auto_enroll_next_term": 1},
        )
        frappe.clear_document_cache("Program", self.program.name)

    def test_advancing_enrolls_in_the_next_terms_courses(self):
        pe = _enrollment(self.program, 1, self.closing)
        target = _section(self.c, self.next)
        _taken(pe, _section(self.a, self.closing, state="Closed"), "Pass")
        progression.evaluate(pe.name, self.closing)
        self.assertEqual(
            frappe.db.get_value(
                "Course Enrollment Individual",
                {"program_ce": pe.name, "coursesc_ce": target, "docstatus": 1},
                "workflow_state",
            ),
            "Submitted",
        )

    def test_a_section_opening_later_enrolls_them(self):
        pe = _enrollment(self.program, 1, self.closing)
        _taken(pe, _section(self.a, self.closing, state="Closed"), "Pass")
        progression.evaluate(pe.name, self.closing)
        later = _section(self.c, self.next, state="Draft")
        frappe.db.set_value(
            "Course Schedule", later, "workflow_state", "Open for Enrollment"
        )
        progression._backfill(frappe.get_doc("Course Schedule", later))
        self.assertTrue(
            frappe.db.exists(
                "Course Enrollment Individual",
                {"program_ce": pe.name, "coursesc_ce": later, "docstatus": 1},
            )
        )

    def test_students_cannot_enroll_themselves(self):
        pe = _enrollment(self.program, 2, self.closing)
        frappe.db.set_single_value("Seminary Settings", "allow_portal_enroll", 1)
        user = frappe.db.get_value("Student", pe.student, "user")
        frappe.set_user(user)
        with self.assertRaises(frappe.PermissionError):
            api.course_enroll(pe.name, _section(self.c, self.next))

    def test_program_settings_are_kept_consistent(self):
        doc = frappe.get_doc("Program", self.program.name)
        doc.registrar_block_cei = 1
        doc.save()
        self.assertEqual(doc.registrar_block_cei, 0)
        doc.staff_enroll_only = 0
        doc.save()
        self.assertEqual(doc.auto_enroll_next_term, 0)

    def test_self_paced_is_refused_on_time_based(self):
        doc = frappe.get_doc("Program", self.program.name)
        doc.pacing_mode = "Self-paced"
        with self.assertRaises(frappe.ValidationError):
            doc.save()
