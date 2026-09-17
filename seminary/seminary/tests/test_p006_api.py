# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p006 Phase 0 role gates on api.py / utils.py endpoints (privatedocs
p006-OWASP-ADR-Phase0 §2.1, 2.3, 2.4, 2.7, 2.9, 2.11, 2.14).

Every gated function must throw ``frappe.PermissionError`` for a Student-only
user and must NOT throw PermissionError for an Instructor. The Instructor path
runs against no fixtures, so any *other* exception (a missing roster, a
``DoesNotExistError``) is acceptable: the assertion is only that the gate is
not what stopped them.
"""

import frappe
from frappe.tests import IntegrationTestCase as FrappeTestCase

from seminary.seminary import api, utils

PREFIX = "zzt.p006"


def _make_user(role, tag):
    email = "%s.%s.%s@example.test" % (PREFIX, tag, frappe.generate_hash(length=6))
    doc = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": "P006",
            "last_name": tag,
            "send_welcome_email": 0,
        }
    )
    doc.flags.no_welcome_mail = True
    doc.insert(ignore_permissions=True)
    if not frappe.db.exists("Role", role):
        frappe.get_doc({"doctype": "Role", "role_name": role}).insert(
            ignore_permissions=True
        )
    doc.add_roles(role)
    return doc.name


class TestP006ApiGates(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "student")
        cls.instructor = _make_user("Instructor", "instructor")

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")

    # ------------------------------------------------------------ helpers

    def assert_gated(self, fn, *args, **kwargs):
        """Student -> PermissionError; Instructor -> anything but."""
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            fn(*args, **kwargs)

        frappe.set_user(self.instructor)
        try:
            fn(*args, **kwargs)
        except frappe.PermissionError as e:
            self.fail("Instructor was refused by the gate: %s" % e)
        except Exception:
            # Missing fixtures are fine; only the gate is under test.
            return

    # ------------------------------------------------------------ F1 §2.1

    def test_delete_chapter_requires_outline_editor(self):
        self.assert_gated(api.delete_chapter, "ZZT-no-such-chapter")

    def test_delete_lesson_requires_outline_editor(self):
        self.assert_gated(api.delete_lesson, "ZZT-no-such-lesson", "ZZT-no-such")

    def test_update_lesson_index_requires_outline_editor(self):
        self.assert_gated(
            api.update_lesson_index, "ZZT-no-such-lesson", "ZZT-a", "ZZT-b", 1
        )

    def test_delete_scorm_package_refuses_path_outside_root(self):
        # A chapter title that would climb out of public/scorm must be refused
        # without touching the filesystem. rmtree is patched to prove it.
        import shutil

        calls = []
        orig = shutil.rmtree
        shutil.rmtree = lambda *a, **k: calls.append(a)
        try:
            api.delete_scorm_package(
                frappe._dict(
                    name="ZZT-chapter",
                    coursesc="..",
                    chapter_title="..",
                    scorm_package_path="/scorm/../..",
                )
            )
        finally:
            shutil.rmtree = orig
        self.assertEqual(calls, [])

    def test_scorm_fields_are_read_only(self):
        meta = frappe.get_meta("Course Schedule Chapter")
        self.assertEqual(meta.get_field("scorm_package_path").read_only, 1)
        self.assertEqual(meta.get_field("is_scorm_package").read_only, 1)

    # ------------------------------------------------------------ F3 §2.3

    def test_roll_pe_and_petb_enroll_not_whitelisted(self):
        self.assertFalse(getattr(api.roll_pe, "is_whitelisted", False))
        self.assertFalse(getattr(api.petb_enroll, "is_whitelisted", False))
        self.assertNotIn(api.roll_pe, frappe.whitelisted)
        self.assertNotIn(api.petb_enroll, frappe.whitelisted)

    # ------------------------------------------------------------ F4 §2.4

    def test_mark_attendance_requires_grader(self):
        self.assert_gated(
            api.mark_attendance, "[]", "[]", course_schedule="ZZT-no-such-cs"
        )

    # ------------------------------------------------------------ F7 §2.7

    def test_save_discussion_submission_grade_requires_grader(self):
        self.assert_gated(api.save_discussion_submission_grade, "ZZT-no-such", 1)

    def test_grade_thisstudent_requires_grader(self):
        self.assert_gated(api.grade_thisstudent, "ZZT-no-such-roster")

    def test_fgrade_this_std_requires_grader(self):
        self.assert_gated(api.fgrade_this_std, "ZZT-no-such-roster")

    def test_internal_grade_functions_exist_and_are_not_whitelisted(self):
        self.assertTrue(callable(api._grade_thisstudent))
        self.assertTrue(callable(api._fgrade_this_std))
        self.assertNotIn(api._grade_thisstudent, frappe.whitelisted)
        self.assertNotIn(api._fgrade_this_std, frappe.whitelisted)

    def test_save_course_assessment_requires_outline_editor(self):
        self.assert_gated(api.save_course_assessment, "ZZT-no-such-cs", "[]")

    def test_insert_cs_assessment_requires_outline_editor(self):
        self.assert_gated(api.insert_cs_assessment, {"title": "x"})

    # ------------------------------------------------------------ F9 §2.9

    def test_get_gradebook_requires_grader(self):
        self.assert_gated(utils.get_gradebook, "ZZT-no-such-cs")

    def test_get_all_questions_details_is_parameterised(self):
        frappe.set_user(self.instructor)
        self.assertEqual(utils.get_all_questions_details(["x') OR 1=1 -- "]), [])
        self.assertEqual(utils.get_all_questions_details([]), [])
        self.assertEqual(utils.get_all_questions_details('["x\') OR 1=1 -- "]'), [])

    # ------------------------------------------------------------ F11 §2.11

    def test_utils_endpoints_no_longer_allow_guest(self):
        for fn in (
            utils.has_student_role,
            utils.has_course_moderator_role,
            utils.has_course_instructor_role,
            utils.has_course_evaluator_role,
            utils.get_courses_for_student,
            utils.get_course_details,
            utils.get_courses,
            utils.get_course_outline,
            utils.get_course_title,
            utils.get_instructors,
            utils.get_instructor,
        ):
            self.assertIn(fn, frappe.whitelisted, fn.__name__)
            self.assertNotIn(fn, frappe.guest_methods, fn.__name__)

    def test_has_role_ignores_member_for_non_staff(self):
        # A student asking about the instructor's roles gets their own answer.
        frappe.set_user(self.student)
        self.assertFalse(utils.has_course_evaluator_role(member=self.instructor))
        self.assertTrue(utils.has_student_role(member=self.instructor))
        # Staff may still ask about another user.
        frappe.set_user(self.instructor)
        self.assertTrue(utils.has_student_role(member=self.student))

    def test_get_courses_for_student_forces_session_user(self):
        frappe.set_user(self.student)
        # Asking for someone else's list must not raise and must be scoped to
        # the caller; with no enrollments it is simply empty.
        self.assertEqual(utils.get_courses_for_student(self.instructor), [])

    def test_get_courses_forces_published_for_non_staff(self):
        frappe.set_user(self.student)
        # Would list unpublished sections before p006; now yields published only.
        rows = utils.get_courses(filters={"published": 0}, page_length=5)
        self.assertTrue(all(r.get("published", 1) for r in rows))

    def test_get_application_payment_url_requires_key_for_non_staff(self):
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            api.get_application_payment_url("ZZT-no-such-applicant", key=None)

    # ------------------------------------------------------------ F14 §2.14

    def test_course_enroll_refuses_other_students_enrollment(self):
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            api.course_enroll("ZZT-no-such-pe", "ZZT-no-such-cs")

    def test_course_enroll_staff_passes_gate(self):
        frappe.set_user(self.instructor)
        try:
            api.course_enroll("ZZT-no-such-pe", "ZZT-no-such-cs")
        except frappe.PermissionError as e:
            self.fail("Instructor was refused by the gate: %s" % e)
        except Exception:
            return  # missing fixtures are fine; only the gate is under test
