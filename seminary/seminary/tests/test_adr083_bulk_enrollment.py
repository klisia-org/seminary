# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/083: Advance Students by program step, Bulk Course Enrollment and
the enrollment check report."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from seminary.seminary import advancement
from seminary.seminary.doctype.bulk_course_enrollment.bulk_course_enrollment import (
    enroll,
    execute_run,
    new_run,
)
from seminary.seminary.report.time_based_enrollment_gaps import (
    time_based_enrollment_gaps as gaps_report,
)
from seminary.seminary.tests import cohort_fixtures as fx


def _term(start, end):
    name = fx.uid("AT")
    frappe.get_doc(
        {
            "doctype": "Academic Term",
            "name": name,
            "title": name,
            "term_name": name,
            "term_start_date": start,
            "term_end_date": end,
        }
    ).db_insert()
    return name


def _course():
    name = fx.uid("C083")
    frappe.get_doc(
        {
            "doctype": "Course",
            "name": name,
            "course_name": name,
            "coursecode": name[-10:],
        }
    ).db_insert()
    return name


def _section(course, term, state="Open for Enrollment", **values):
    name = fx.uid("CS")
    frappe.get_doc(
        {
            "doctype": "Course Schedule",
            "name": name,
            "course": course,
            "academic_term": term,
            "workflow_state": state,
            "modality": "Virtual",
            "gradesc_cs": fx.cbe_grading_scale(),
            **values,
        }
    ).db_insert()
    return name


def _program(courses, **values):
    """A Time-based program; `courses` is [(course, term)]."""
    program = fx.make_program("Time-based")
    for idx, (course, term) in enumerate(courses, 1):
        frappe.get_doc(
            {
                "doctype": "Program Course",
                "name": frappe.generate_hash(length=10),
                "parent": program.name,
                "parenttype": "Program",
                "parentfield": "courses",
                "idx": idx,
                "course": course,
                "course_name": course,
                "course_term": term,
                "pgmcourse_credits": 3,
            }
        ).db_insert()
    if values:
        frappe.db.set_value("Program", program.name, values)
    return program


def _enrollment(program, term_index, intake):
    pe = fx.make_enrollment(fx.make_student(), program)
    frappe.db.set_value(
        "Program Enrollment",
        pe.name,
        {"current_std_term": term_index, "academic_term": intake},
    )
    return frappe.get_doc("Program Enrollment", pe.name)


def _cei(pe, section):
    """A submitted enrollment row, enough for the grade check to see."""
    frappe.get_doc(
        {
            "doctype": "Course Enrollment Individual",
            "name": fx.uid("CEI"),
            "program_ce": pe.name,
            "student_ce": pe.student,
            "coursesc_ce": section,
            "course_data": frappe.db.get_value("Course Schedule", section, "course"),
            "docstatus": 1,
            "workflow_state": "Submitted",
        }
    ).db_insert()


def _steps(term, program):
    return {
        (s.from_term, s.status): s
        for s in advancement.compute_steps(term, program.name)
    }


class ADR083Case(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        base = getdate(today())
        self.closing = _term(add_days(base, -120), add_days(base, -5))
        self.next = _term(add_days(base, -4), add_days(base, 110))
        self.later = _term(add_days(base, 111), add_days(base, 220))

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()


class TestAdvanceStudents(ADR083Case):
    def setUp(self):
        super().setUp()
        self.course = _course()
        self.program = _program([], terms_complete=3)

    def test_step_waits_for_grades_then_advances_once(self):
        pe = _enrollment(self.program, 1, self.closing)
        cs = _section(self.course, self.closing, state="Grading")
        _cei(pe, cs)

        step = _steps(self.closing, self.program)[(1, advancement.BLOCKED)]
        self.assertEqual(step.sections, [cs])
        out = advancement.advance(
            self.closing,
            [{"program": self.program.name, "from_term": 1}],
            self.program.name,
        )
        self.assertEqual(out["advanced"], [])
        self.assertIn(cs, out["messages"][0]["message"])
        self.assertEqual(
            frappe.db.get_value("Program Enrollment", pe.name, "current_std_term"), 1
        )

        frappe.db.set_value("Course Schedule", cs, "workflow_state", "Closed")
        self.assertIn((1, advancement.READY), _steps(self.closing, self.program))
        advancement.advance(
            self.closing,
            [{"program": self.program.name, "from_term": 1}],
            self.program.name,
        )
        row = frappe.db.get_value(
            "Program Enrollment",
            pe.name,
            ["current_std_term", "advanced_from_term"],
            as_dict=True,
        )
        self.assertEqual(
            (row.current_std_term, row.advanced_from_term), (2, self.closing)
        )

        # A second click finds the step Done and moves no one.
        out = advancement.advance(
            self.closing,
            [{"program": self.program.name, "from_term": 1}],
            self.program.name,
        )
        self.assertEqual(out["advanced"], [])
        self.assertEqual(out["messages"][0]["status"], advancement.DONE)
        self.assertEqual(
            frappe.db.get_value("Program Enrollment", pe.name, "current_std_term"), 2
        )

    def test_steps_advance_together_without_double_moving(self):
        first = _enrollment(self.program, 1, self.closing)
        second = _enrollment(self.program, 2, self.closing)
        advancement.advance(
            self.closing,
            [
                {"program": self.program.name, "from_term": 1},
                {"program": self.program.name, "from_term": 2},
            ],
            self.program.name,
        )
        self.assertEqual(
            frappe.db.get_value("Program Enrollment", first.name, "current_std_term"), 2
        )
        self.assertEqual(
            frappe.db.get_value("Program Enrollment", second.name, "current_std_term"),
            3,
        )

    def test_only_blocking_sections_of_that_step_count(self):
        ready = _enrollment(self.program, 2, self.closing)
        blocked = _enrollment(self.program, 1, self.closing)
        _cei(blocked, _section(self.course, self.closing, state="Grading"))
        _cei(ready, _section(self.course, self.closing, state="Cancelled"))
        _cei(ready, _section(self.course, self.closing, state="Grading", open_ended=1))
        steps = _steps(self.closing, self.program)
        self.assertIn((2, advancement.READY), steps)
        self.assertIn((1, advancement.BLOCKED), steps)

    def test_final_term_and_later_intake_are_not_offered(self):
        _enrollment(self.program, 3, self.closing)
        _enrollment(self.program, 1, self.later)
        steps = _steps(self.closing, self.program)
        self.assertEqual(set(steps), {(3, advancement.FINAL)})

    def test_students_cannot_open_advancement(self):
        user = fx.make_user(roles=("Student",))
        frappe.set_user(user.name)
        with self.assertRaises(frappe.PermissionError):
            advancement.get_steps(self.closing)


class TestBulkCourseEnrollment(ADR083Case):
    def setUp(self):
        super().setUp()
        self.c1, self.c2 = _course(), _course()
        self.program = _program([(self.c1, 1), (self.c2, 1)])
        self.cs1 = _section(self.c1, self.next)

    def run_for(self, *pes):
        name = new_run(
            self.next, [self.program.name], enrollments=[pe.name for pe in pes]
        )
        return frappe.get_doc("Bulk Course Enrollment", name)

    def execute(self, run):
        enroll(run.name)
        execute_run(run.name)
        run.reload()
        return {(r.program_enrollment, r.course): r for r in run.results}

    def test_run_lists_the_plan_and_enrolls(self):
        pe = _enrollment(self.program, 1, self.next)
        run = self.run_for(pe)
        self.assertEqual([s.program_enrollment for s in run.students], [pe.name])
        rows = {r.course: r for r in run.courses}
        self.assertEqual(rows[self.c1].course_schedule, self.cs1)
        self.assertIsNone(rows[self.c2].course_schedule)
        self.assertEqual(rows[self.c1].students, 1)

        results = self.execute(run)
        done = results[(pe.name, self.c1)]
        self.assertEqual(done.status, "Enrolled", done.message)
        self.assertEqual(
            frappe.db.get_value(
                "Course Enrollment Individual", done.cei, "coursesc_ce"
            ),
            self.cs1,
        )
        self.assertEqual(results[(pe.name, self.c2)].status, "Skipped")
        self.assertEqual(run.run_status, "Completed")

        # Nothing is left to do, so a second run is refused.
        with self.assertRaises(frappe.ValidationError):
            enroll(run.name)

    def test_registrar_block_does_not_hold_back_the_run(self):
        frappe.db.set_value("Program", self.program.name, "registrar_block_cei", 1)
        pe = _enrollment(self.program, 1, self.next)
        results = self.execute(self.run_for(pe))
        cei = results[(pe.name, self.c1)].cei
        self.assertEqual(
            frappe.db.get_value("Course Enrollment Individual", cei, "docstatus"), 1
        )

    def test_already_enrolled_is_skipped(self):
        pe = _enrollment(self.program, 1, self.next)
        _cei(pe, self.cs1)
        results = self.execute(self.run_for(pe))
        self.assertEqual(results[(pe.name, self.c1)].status, "Skipped")

    def test_max_students_splits_between_sections(self):
        cs_b = _section(self.c1, self.next)
        a = _enrollment(self.program, 1, self.next)
        b = _enrollment(self.program, 1, self.next)
        run = self.run_for(a, b)
        first = next(r for r in run.courses if r.course == self.c1)
        first.max_students = 1
        run.append(
            "courses",
            {
                "include": 1,
                "program": self.program.name,
                "term": 1,
                "course": self.c1,
                "course_schedule": cs_b,
            },
        )
        run.save()
        results = self.execute(run)
        sections = {results[(pe.name, self.c1)].course_schedule for pe in (a, b)}
        self.assertEqual(sections, {self.cs1, cs_b})
        self.assertEqual(
            {results[(pe.name, self.c1)].status for pe in (a, b)}, {"Enrolled"}
        )

    def test_unticked_student_is_left_out(self):
        a = _enrollment(self.program, 1, self.next)
        b = _enrollment(self.program, 1, self.next)
        run = self.run_for(a, b)
        next(s for s in run.students if s.program_enrollment == b.name).include = 0
        run.save()
        results = self.execute(run)
        self.assertIn((a.name, self.c1), results)
        self.assertNotIn((b.name, self.c1), results)

    def test_credits_based_program_is_refused(self):
        other = fx.make_program("Credits-based")
        run = frappe.new_doc("Bulk Course Enrollment")
        run.academic_term = self.next
        run.append("programs", {"program": other.name})
        run.flags.filled = True
        with self.assertRaises(frappe.ValidationError):
            run.insert()


class TestEnrollmentCheck(ADR083Case):
    def test_report_shows_enrolled_and_missing(self):
        c1, c2 = _course(), _course()
        program = _program([(c1, 1), (c2, 1)])
        cs1 = _section(c1, self.next)
        _section(c2, self.next, state="Enrollment Closed")
        pe = _enrollment(program, 1, self.next)
        _cei(pe, cs1)

        rows = gaps_report.get_data(
            {"academic_term": self.next, "program": program.name, "gaps_only": 0}
        )
        by_course = {r["course"]: r for r in rows}
        self.assertEqual(by_course[c1]["status"], "Enrolled")
        self.assertEqual(by_course[c1]["gap"], 0)
        self.assertEqual(by_course[c2]["reason"], "Offering closed")

        gaps = gaps_report.get_data(
            {"academic_term": self.next, "program": program.name, "gaps_only": 1}
        )
        self.assertEqual([r["course"] for r in gaps], [c2])
