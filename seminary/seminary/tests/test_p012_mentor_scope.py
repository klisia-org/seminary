# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""privatedocs p012 decisions 1-2 -- a mentor reaches a competency section
through their mentees, and sees nobody else.

Two mentors, two students, one section: each mentor must reach the section's
content and their own student, and be refused the other student everywhere.
"""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import cbe, cbe_api, guards, utils
from seminary.seminary.tests import cohort_fixtures as cf
from seminary.seminary.tests.test_adr079_reflection import World, _insert


def _submitted_enrollment(student, program):
    # Inserted directly: Program Enrollment's on_submit commits, which would
    # outlive the test's rollback.
    pe = frappe.new_doc("Program Enrollment")
    pe.update({"student": student, "program": program, "docstatus": 1})
    pe.set_new_name()
    pe.db_insert()
    return pe.name


def _reset_request_cache():
    frappe.local.p007_cache = {}
    cf.bust_cbe_cache()


class MentorWorld:
    def __init__(self):
        categories = frappe.get_all("Instructor Category", limit=2, pluck="name")
        if len(categories) < 2:
            import unittest

            raise unittest.SkipTest("Needs two Instructor Categories.")
        self.ctype = cf.make_cohort_type().name
        self.world = World(
            evaluators=[
                {
                    "instructor_category": categories[0],
                    "assignment_source": "Course Schedule Instructors",
                    "grades_activities": 1,
                    "gives_competency_verdict": 1,
                },
                {
                    "instructor_category": categories[1],
                    "assignment_source": "Program Cohort",
                    "cohort_type": self.ctype,
                    "grades_activities": 1,
                    "gives_competency_verdict": 1,
                },
            ]
        )
        self.cs = self.world.cs
        self.mentors, self.students, self.rosters = [], [], []
        for _ in range(2):
            instructor = cf.make_instructor()
            user = frappe.db.get_value("Instructor", instructor.name, "user")
            frappe.get_doc("User", user).add_roles("Instructor")
            student = cf.make_student()
            _submitted_enrollment(student.name, self.world.program)
            # The leader is made the cohort's Mentor member automatically.
            cohort = cf.make_cohort(self.ctype, instructor.person)
            cf.add_member(cohort.name, student.person)
            roster = _insert(
                {
                    "doctype": "Scheduled Course Roster",
                    "course_sc": self.cs,
                    "student": student.name,
                    "stuemail_rc": student.user,
                    "active": 1,
                }
            ).name
            self.mentors.append(user)
            self.students.append(student.name)
            self.rosters.append(roster)
        _reset_request_cache()


class TestMentorScope(IntegrationTestCase):
    def setUp(self):
        try:
            self.w = MentorWorld()
        except Exception:
            # tearDown does not run when setUp fails; roll back here so one
            # broken world does not poison the next test.
            frappe.db.rollback()
            raise

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        super().tearDown()

    def as_mentor(self, i):
        frappe.set_user(self.w.mentors[i])
        _reset_request_cache()

    def test_each_mentor_reaches_the_section_through_their_own_student(self):
        for i in (0, 1):
            self.as_mentor(i)
            self.assertEqual(guards.section_mentees(self.w.cs), {self.w.students[i]})
            self.assertEqual(guards.section_access(self.w.cs), "mentor")
            self.assertTrue(guards.may_view_content(self.w.cs))
            self.assertFalse(guards.is_course_staff(self.w.cs))
            self.assertIn(self.w.cs, guards.mentored_sections())
            # Content reads open; the outline is the section's own.
            utils.get_course_outline(self.w.cs)

    def test_a_mentor_lists_only_their_student(self):
        self.as_mentor(0)
        roster = cbe_api.get_competency_roster(self.w.cs)
        self.assertEqual([r.student for r in roster], [self.w.students[0]])
        book = cbe_api.get_cbe_gradebook(self.w.cs)
        self.assertEqual(
            [s.get("student") for s in book["students"]], [self.w.students[0]]
        )
        self.assertEqual(
            [r.student for r in utils.get_roster(self.w.cs)], [self.w.students[0]]
        )
        listed = frappe.get_list(
            "Scheduled Course Roster",
            filters={"course_sc": self.w.cs},
            pluck="student",
        )
        self.assertEqual(listed, [self.w.students[0]])

    def test_a_mentor_is_refused_the_other_student_everywhere(self):
        self.as_mentor(0)
        other = self.w.rosters[1]
        with self.assertRaises(frappe.PermissionError):
            cbe_api.get_student_competency_detail(other)
        with self.assertRaises(frappe.PermissionError):
            cbe_api.save_activity_grade(other, "x", "3")
        with self.assertRaises(frappe.PermissionError):
            cbe_api.get_development_plan(self.w.cs, student=self.w.students[1])
        doc = frappe.get_doc("Scheduled Course Roster", other)
        self.assertFalse(frappe.has_permission(doc=doc, ptype="read"))
        mine = frappe.get_doc("Scheduled Course Roster", self.w.rosters[0])
        self.assertTrue(frappe.has_permission(doc=mine, ptype="read"))
        # Read-only: a mentor never writes the roster.
        self.assertFalse(frappe.has_permission(doc=mine, ptype="write"))

    def test_course_staff_only_actions_refuse_a_mentor(self):
        self.as_mentor(0)
        with self.assertRaises(frappe.PermissionError):
            cbe_api._assert_course_staff(self.w.cs)
        with self.assertRaises(frappe.PermissionError):
            cbe_api.save_assessment_competency_config(self.w.cs, "{}")

    def test_an_instructor_with_no_tie_sees_nothing(self):
        stranger = cf.make_instructor()
        user = frappe.db.get_value("Instructor", stranger.name, "user")
        frappe.get_doc("User", user).add_roles("Instructor")
        frappe.set_user(user)
        _reset_request_cache()
        self.assertIsNone(guards.section_access(self.w.cs))
        self.assertEqual(cbe.visible_students(self.w.cs), set())
        with self.assertRaises(frappe.PermissionError):
            cbe_api.get_competency_roster(self.w.cs)
        with self.assertRaises(frappe.PermissionError):
            utils.get_course_outline(self.w.cs)

    def test_school_roles_still_see_everyone(self):
        frappe.set_user("Administrator")
        _reset_request_cache()
        self.assertIsNone(cbe.visible_students(self.w.cs))
        self.assertEqual(guards.section_access(self.w.cs), "instructor")


def _assessment(w, i, kind, stage, levels, instructor=None, category=None):
    """Written directly: saving runs the result recompute, which this world
    has no programme enrollment for."""
    doc = frappe.get_doc(
        {
            "doctype": "Competency Assessment",
            "student": w.students[i],
            "course_schedule": w.cs,
            "course_competency": w.world.competencies[0],
            "stage": stage,
            "status": "Submitted",
            "submitted_on": frappe.utils.now_datetime(),
            "evaluator_kind": kind,
            "instructor": instructor,
            "instructor_category": category,
            "narrative": f"<p>{kind} {stage}</p>",
            "ratings": [
                {"dimension_code": c, "level_code": str(v), "level_value": v}
                for c, v in levels.items()
            ],
        }
    )
    doc.set_new_name()
    doc.db_insert()
    for row in doc.ratings:
        row.parent, row.parenttype, row.parentfield = doc.name, doc.doctype, "ratings"
        row.set_new_name()
        row.db_insert()
    return doc


class TestCompetencyReview(IntegrationTestCase):
    """privatedocs p012 decision 3: every voice apart, gated for the student."""

    def setUp(self):
        try:
            self.w = MentorWorld()
        except Exception:
            frappe.db.rollback()
            raise
        w = self.w
        _assessment(w, 0, "Self", "Baseline", {"knowledge": 1, "character": 2})
        _assessment(w, 0, "Self", "Final", {"knowledge": 3, "character": 3})
        self.mentor_instructor = frappe.db.get_value(
            "Instructor", {"user": w.mentors[0]}, "name"
        )
        framework = frappe.get_doc("Competency Framework", w.world.framework)
        self.mentor_category = next(
            e.instructor_category
            for e in framework.evaluators
            if e.assignment_source == "Program Cohort"
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        super().tearDown()

    def kinds(self, review):
        return [s["kind"] for s in review["competencies"][0]["series"]]

    def test_the_student_sees_their_own_change_and_waits_for_mentors(self):
        student_user = frappe.db.get_value("Student", self.w.students[0], "user")
        frappe.set_user(student_user)
        _reset_request_cache()
        review = cbe_api.get_competency_review(self.w.cs)
        self.assertTrue(review["own"])
        self.assertEqual(self.kinds(review), ["baseline", "self"])
        self.assertFalse(review["competencies"][0]["mentors_shown"])

        frappe.set_user("Administrator")
        _assessment(
            self.w,
            0,
            "Mentor",
            "Final",
            {"knowledge": 4, "character": 3},
            instructor=self.mentor_instructor,
            category=self.mentor_category,
        )
        frappe.set_user(student_user)
        _reset_request_cache()
        review = cbe_api.get_competency_review(self.w.cs)
        self.assertEqual(self.kinds(review), ["baseline", "self", "mentor"])
        mentor = review["competencies"][0]["series"][2]
        self.assertEqual(mentor["sublabel"], self.mentor_category)
        self.assertEqual(mentor["values"]["knowledge"], 4)

    def test_a_mentor_reads_their_mentee_and_not_the_other(self):
        frappe.set_user(self.w.mentors[0])
        _reset_request_cache()
        framework = frappe.get_doc("Competency Framework", self.w.world.framework)
        review = cbe_api.get_competency_review(self.w.cs, student=self.w.students[0])
        self.assertFalse(review["own"])
        if framework.mentor_sees_self_eval == "After mentor submits":
            # The student's view is withheld until the mentor has formed theirs.
            self.assertEqual(self.kinds(review), [])
            frappe.set_user("Administrator")
            _assessment(
                self.w,
                0,
                "Mentor",
                "Final",
                {"knowledge": 2, "character": 3},
                instructor=self.mentor_instructor,
                category=self.mentor_category,
            )
            frappe.set_user(self.w.mentors[0])
            _reset_request_cache()
            review = cbe_api.get_competency_review(
                self.w.cs, student=self.w.students[0]
            )
        self.assertIn("self", self.kinds(review))
        with self.assertRaises(frappe.PermissionError):
            cbe_api.get_competency_review(self.w.cs, student=self.w.students[1])

    def test_a_classmate_cannot_read_it(self):
        frappe.set_user(frappe.db.get_value("Student", self.w.students[1], "user"))
        _reset_request_cache()
        with self.assertRaises(frappe.PermissionError):
            cbe_api.get_competency_review(self.w.cs, student=self.w.students[0])
