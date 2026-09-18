# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p007 §2.10: every whitelisted function in the modules Phase 0/1 touched is
classified, and the classification is enforced.

* ``STAFF_ONLY``: a Student receives ``PermissionError``; a user holding the
  school roles is not stopped by the gate (any other exception is a missing
  fixture).
* ``STUDENT_ALLOWED``: a student may call it; those that take a target are
  checked in ``test_p007_docperms`` / the potestas matrix, not here.
* ``GUEST_ALLOWED``: reachable without a session.

A whitelisted function that appears in none of the lists fails the suite, so a
new endpoint has to be classified before the branch is green.
"""

import inspect

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.tests.test_p006_api import _make_user

MODULES = (
    "seminary.seminary.api",
    "seminary.seminary.utils",
    "seminary.seminary.doctype.quiz.quiz",
    "seminary.seminary.doctype.exam_submission.exam_submission",
    "seminary.seminary.doctype.assignment_submission.assignment_submission",
    "seminary.seminary.doctype.withdrawal_request.withdrawal_request",
    "seminary.seminary.student_standing",
    "seminary.seminary.doctype.student_attendance_tool.student_attendance_tool",
    "seminary.seminary.doctype.culminating_project.culminating_project",
)

GUEST_ALLOWED = {
    "seminary.seminary.api.get_translations",
    "seminary.seminary.api.get_user_info",
    "seminary.seminary.api.get_school_abbr_logo",
    "seminary.seminary.api.get_doctrinal_statement",
    "seminary.seminary.api.get_application_payment_url",
    "seminary.seminary.api.get_default_phone_country",
    "seminary.seminary.api.active_term",
}

STUDENT_ALLOWED = {
    # lesson discussions: whoever reads the lesson posts; own-reply rules inside
    "seminary.seminary.api.reply_to_discussion_submission",
    "seminary.seminary.utils.create_discussion_topic",
    "seminary.seminary.utils.add_discussion_reply",
    "seminary.seminary.utils.edit_discussion_reply",
    "seminary.seminary.utils.delete_discussion_reply",
    # api.py — session-scoped, no target, or scoped by p007 §2.5
    "seminary.seminary.api.get_student_group",
    "seminary.seminary.api.get_student_groups_simple",
    "seminary.seminary.api.get_discussion_submissions",
    "seminary.seminary.api.get_user_discussion_submission",
    "seminary.seminary.api.get_user_discussion_replies",
    "seminary.seminary.api.add_grading_comment",
    "seminary.seminary.api.get_grading_comments",
    "seminary.seminary.api.get_discussion_dashboard",
    "seminary.seminary.api.get_enabled_languages",
    "seminary.seminary.api.set_user_language",
    "seminary.seminary.api.get_file_info",
    "seminary.seminary.api.get_instructor_info",
    "seminary.seminary.api.save_student_profile",
    "seminary.seminary.api.save_instructor_profile",
    "seminary.seminary.api.get_student_programs",
    "seminary.seminary.api.course_enroll",
    "seminary.seminary.api.get_student_enrollments_for_term",
    "seminary.seminary.api.cancel_draft_enrollment",
    "seminary.seminary.api.cancel_unpaid_enrollment",
    "seminary.seminary.api.get_program_audit",
    "seminary.seminary.api.create_graduation_request",
    "seminary.seminary.api.get_pe_unpaid_invoices",
    "seminary.seminary.api.get_available_courses_categorized",
    "seminary.seminary.api.get_student_invoices",
    "seminary.seminary.api.courses_for_student",
    "seminary.seminary.api.get_pgmenrollments",
    "seminary.seminary.api.mark_lesson_progress",
    "seminary.seminary.api.get_student_info",
    "seminary.seminary.api.get_announcements",
    "seminary.seminary.api.GradeableDiscussion",
    "seminary.seminary.api.GradeableQuiz",
    "seminary.seminary.api.GradeableExam",
    "seminary.seminary.api.GradeableAssignment",
    "seminary.seminary.api.get_submission_comments",
    "seminary.seminary.api.update_submission_comment",
    "seminary.seminary.api.delete_submission_comment",
    "seminary.seminary.api.get_invoice_payment_url",
    "seminary.seminary.api.get_student_balance_payment_url",
    "seminary.seminary.api.get_student_partial_balance_payment_url",
    # utils.py
    "seminary.seminary.utils.get_courses_for_student",
    "seminary.seminary.utils.get_courses",
    "seminary.seminary.utils.get_instructors",
    "seminary.seminary.utils.get_instructor",
    "seminary.seminary.utils.get_course_outline",
    "seminary.seminary.utils.get_course_title",
    "seminary.seminary.utils.get_course_details",
    "seminary.seminary.utils.get_roster",
    "seminary.seminary.utils.get_lesson",
    "seminary.seminary.utils.get_question_details",
    "seminary.seminary.utils.get_all_questions_details",
    "seminary.seminary.utils.get_assessments",
    "seminary.seminary.utils.get_assessment_due_date",
    "seminary.seminary.utils.get_student_course_status",
    "seminary.seminary.utils.get_discussion_topics",
    "seminary.seminary.utils.get_discussion_replies",
    "seminary.seminary.utils.ensure_single_topic",
    "seminary.seminary.utils.get_missingassessments",
    # quiz.py (taking a quiz)
    "seminary.seminary.doctype.quiz.quiz.quiz_summary",
    "seminary.seminary.doctype.quiz.quiz.get_last_submission",
    "seminary.seminary.doctype.quiz.quiz.get_question_details",
    "seminary.seminary.doctype.quiz.quiz.check_answer",
    # exam / assignment submission (own work)
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_draft",
    "seminary.seminary.doctype.exam_submission.exam_submission.submit_exam",
    "seminary.seminary.doctype.exam_submission.exam_submission.get_exam_grading_comments",
    "seminary.seminary.doctype.exam_submission.exam_submission.add_exam_grading_comment",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.upload_assignment",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.get_assignment",
}

STAFF_ONLY = {
    # api.py
    "seminary.seminary.api.get_student_groups",
    "seminary.seminary.api.get_discussion_submission_summary",
    "seminary.seminary.api.save_discussion_submission_grade",
    "seminary.seminary.api.get_quiz_dashboard",
    "seminary.seminary.api.get_exam_dashboard",
    "seminary.seminary.api.get_assignment_dashboard",
    "seminary.seminary.api.save_course",
    "seminary.seminary.api.get_virtual_meetings",
    "seminary.seminary.api.add_virtual_meeting",
    "seminary.seminary.api.remove_virtual_meeting",
    "seminary.seminary.api.roll_students",
    "seminary.seminary.api.check_schedule_conflicts",
    "seminary.seminary.api.resolve_schedule_conflict",
    "seminary.seminary.api.enroll_student",
    "seminary.seminary.api.mark_attendance",
    "seminary.seminary.api.get_course_schedule_events",
    "seminary.seminary.api.save_course_assessment",
    "seminary.seminary.api.insert_cs_assessment",
    "seminary.seminary.api.get_course_rosters",
    "seminary.seminary.api.grade_thisstudent",
    "seminary.seminary.api.fgrade_this_std",
    "seminary.seminary.api.fail_for_absence",
    "seminary.seminary.api.undo_fail_for_absence",
    "seminary.seminary.api.send_selected_grades",
    "seminary.seminary.api.send_grades",
    "seminary.seminary.api.course_event",
    "seminary.seminary.api.upsert_chapter",
    "seminary.seminary.api.delete_chapter",
    "seminary.seminary.api.delete_lesson",
    "seminary.seminary.api.delete_documents",
    "seminary.seminary.api.update_lesson_index",
    "seminary.seminary.api.update_chapter_index",
    "seminary.seminary.api.add_submission_comment",
    "seminary.seminary.api.preview_announcement_recipients",
    "seminary.seminary.api.generate_announcement_labels",
    "seminary.seminary.api.announcement_letters_pdf",
    "seminary.seminary.api.preview_announcement_letter",
    "seminary.seminary.api.room_search",
    "seminary.seminary.api.run_plagiarism_check",
    "seminary.seminary.api.get_plagiarism_result",
    "seminary.seminary.api.get_plagiarism_match_detail",
    # utils.py
    "seminary.seminary.utils.get_timezones",
    "seminary.seminary.utils.get_all_users",
    "seminary.seminary.utils.get_lesson_creation_details",
    "seminary.seminary.utils.get_gradebook",
    "seminary.seminary.utils.missing_exams",
    "seminary.seminary.utils.get_course_exams",
    "seminary.seminary.utils.get_course_meetingdates",
    "seminary.seminary.utils.get_assessments_tograde",
    "seminary.seminary.utils.get_student_groups",
    "seminary.seminary.utils.create_student_group",
    # controllers
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_grade",
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_comment",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.grade_assignment",
    "seminary.seminary.doctype.withdrawal_request.withdrawal_request.initiate_program_separation",
    "seminary.seminary.student_standing.lift_hold",
    "seminary.seminary.doctype.student_attendance_tool.student_attendance_tool.get_student_attendance_records",
    "seminary.seminary.doctype.culminating_project.culminating_project.resnapshot_milestones",
}

# Whitelisted functions in the walked modules that are neither student-facing
# nor a plain staff gate: they carry their own ownership rule (the culminating
# project's student/advisor checks) and are covered by their own test module.
OWN_RULE = {
    "seminary.seminary.doctype.culminating_project.culminating_project." + n
    for n in (
        "record_signoff",
        "add_committee_member",
        "add_submission",
        "assign_advisor",
        "create_milestone_event",
        "enroll_in_project_course",
        "get_culminating_project",
        "get_my_culminating_projects",
        "remove_committee_member",
        "review_submission",
        "save_abstract",
    )
}

# Arguments that must not be a bare string for the call to reach the gate.
KWARG_OVERRIDES = {
    "seminary.seminary.api.mark_attendance": {
        "students_present": "[]",
        "students_absent": "[]",
        "course_schedule": "ZZT-no-such-cs",
    },
    "seminary.seminary.api.send_grades": {"doc": '{"name": "ZZT-no-such-cs"}'},
    "seminary.seminary.api.save_discussion_submission_grade": {"grade": 1.0},
    "seminary.seminary.api.add_submission_comment": {"comment": "x"},
    "seminary.seminary.doctype.exam_submission.exam_submission.add_exam_grading_comment": {
        "comment": "x"
    },
    "seminary.seminary.api.insert_cs_assessment": {"criteria": {"parent": "ZZT-x"}},
    "seminary.seminary.api.save_course_assessment": {"assessment_data": "[]"},
    "seminary.seminary.api.room_search": {
        "doctype": "Room",
        "txt": "",
        "searchfield": "name",
        "start": 0,
        "page_len": 5,
        "filters": {},
    },
}


def _walk():
    import importlib

    for mod in MODULES:  # controller modules register on import
        importlib.import_module(mod)
    found = {}
    for fn in frappe.whitelisted:
        mod = getattr(fn, "__module__", "")
        if mod in MODULES:
            found[f"{mod}.{fn.__name__}"] = fn
    return found


def _dummy_kwargs(fn, dotted):
    kwargs = {}
    sig = inspect.signature(fn)
    for name, param in sig.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        if param.default is inspect.Parameter.empty:
            kwargs[name] = "ZZT-no-such"
    kwargs.update(KWARG_OVERRIDES.get(dotted, {}))
    return kwargs


class TestP007WhitelistWalk(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "walk-student")
        # The positive half runs as a user holding every school role, so a
        # registrar-only gate (term roll, separation) is not what stops them.
        cls.chair = _make_user("Program Chair", "walk-chair")
        frappe.get_doc("User", cls.chair).add_roles("Registrar", "Seminary Manager")
        cls.found = _walk()

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_every_endpoint_is_classified(self):
        classified = GUEST_ALLOWED | STUDENT_ALLOWED | STAFF_ONLY | OWN_RULE
        missing = sorted(set(self.found) - classified)
        self.assertEqual(
            missing, [], "unclassified whitelisted functions: %s" % missing
        )
        stale = sorted(classified - set(self.found))
        self.assertEqual(stale, [], "classified but not whitelisted: %s" % stale)
        overlap = (
            (GUEST_ALLOWED & STUDENT_ALLOWED)
            | (GUEST_ALLOWED & STAFF_ONLY)
            | (STUDENT_ALLOWED & STAFF_ONLY)
        )
        self.assertEqual(overlap, set())

    def test_guest_list_matches_allow_guest(self):
        guest = {
            dotted for dotted, fn in self.found.items() if fn in frappe.guest_methods
        }
        self.assertEqual(guest, GUEST_ALLOWED)

    def test_staff_only_refuses_student_and_admits_chair(self):
        for dotted in sorted(STAFF_ONLY):
            fn = self.found[dotted]
            kwargs = _dummy_kwargs(fn, dotted)
            frappe.set_user(self.student)
            with self.subTest(fn=dotted, who="student"):
                with self.assertRaises(frappe.PermissionError):
                    fn(**kwargs)
            frappe.set_user(self.chair)
            with self.subTest(fn=dotted, who="chair"):
                try:
                    fn(**kwargs)
                except frappe.PermissionError as e:
                    self.fail("Program Chair refused by the gate: %s" % e)
                except Exception as e:
                    # A missing fixture is expected; only the gate is under test.
                    self.assertNotIsInstance(e, frappe.PermissionError)
            frappe.set_user("Administrator")

    def test_guest_is_refused_everywhere_else(self):
        frappe.set_user("Guest")
        for dotted in sorted(set(self.found) - GUEST_ALLOWED):
            self.assertNotIn(self.found[dotted], frappe.guest_methods, dotted)
