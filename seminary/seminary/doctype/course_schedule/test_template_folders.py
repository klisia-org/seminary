# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""Import Course Template and folder scopes (p006 F2, ADR §2.2b "rule on import").

Source section CS (instructor A) has one lesson embedding four folders — a
Course folder, A's Instructor folder, CS's own Section folder and a School
folder. Importing that template into a section taught by B, then into a section
taught by A, must apply the table exactly:

| referenced scope                  | into B's section           | into A's section      |
|-----------------------------------|----------------------------|-----------------------|
| Course                            | keep                       | keep                  |
| School                            | keep                       | keep                  |
| Section (of CS, taught by A)      | re-scope to Course         | re-scope to Instructor|
| Instructor (A's)                  | copy for B, rewrite ref    | keep                  |

Run directly (the app-wide suite does not run on the dev sites):
    bench --site <site> execute \
        seminary.seminary.doctype.course_schedule.test_template_folders.run_smoke
"""

import json

import frappe
from frappe.tests import IntegrationTestCase as FrappeTestCase

from seminary.seminary.course_pack import editorjs
from seminary.seminary.doctype.course_folder import course_folder as cf
from seminary.seminary.doctype.course_folder.test_course_folder import (
    make_course,
    make_cs,
    make_enrolled_student,
    make_folder,
    make_grading_scale,
    make_teacher,
    put_file,
)
from seminary.seminary.tests.cohort_fixtures import make_user, uid

IGNORE_TEST_RECORD_DEPENDENCIES = ["User", "Person", "Course", "Course Schedule"]


def _folder_block(folder):
    return {
        "id": frappe.generate_hash(length=8),
        "type": "folder",
        "data": {"folder_ref": folder.name, "folder": folder.foldername},
    }


def _add_lesson(cs, content_blocks, title="Week 1"):
    ch = frappe.get_doc(
        {"doctype": "Course Schedule Chapter", "coursesc": cs, "chapter_title": title}
    )
    ch.insert(ignore_permissions=True, ignore_mandatory=True)
    lesson = frappe.get_doc(
        {
            "doctype": "Course Lesson",
            "chapter": ch.name,
            "lesson_title": f"{title} lesson",
            "content": json.dumps(
                {"time": 1, "blocks": content_blocks, "version": "2.31.3"}
            ),
        }
    )
    lesson.insert(ignore_permissions=True, ignore_mandatory=True)
    for doctype, parent, parenttype, parentfield, field, value in (
        (
            "Course Schedule Lesson Reference",
            ch.name,
            "Course Schedule Chapter",
            "lessons",
            "lesson",
            lesson.name,
        ),
        (
            "Course Schedule Chapter Reference",
            cs,
            "Course Schedule",
            "chapters",
            "chapter",
            ch.name,
        ),
    ):
        frappe.get_doc(
            {
                "doctype": doctype,
                "parent": parent,
                "parenttype": parenttype,
                "parentfield": parentfield,
                "idx": 1,
                field: value,
            }
        ).insert(ignore_permissions=True)
    return lesson.name


def _add_scac(cs):
    criteria = (
        frappe.db.get_value("Assessment Criteria", {})
        or frappe.get_doc(
            {
                "doctype": "Assessment Criteria",
                "assessment_criteria": f"TF {uid()}",
                "type": "Offline",
            }
        )
        .insert(ignore_permissions=True)
        .name
    )
    frappe.get_doc(
        {
            "doctype": "Scheduled Course Assess Criteria",
            "parent": cs,
            "parenttype": "Course Schedule",
            "parentfield": "courseassescrit_sc",
            "idx": 1,
            "assesscriteria_scac": criteria,
            "title": "Participation",
            "weight_scac": 100,
        }
    ).insert(ignore_permissions=True, ignore_mandatory=True)


def _copied_lesson_refs(target_cs):
    chapter = frappe.db.get_value(
        "Course Schedule Chapter Reference", {"parent": target_cs}, "chapter"
    )
    lesson = frappe.db.get_value(
        "Course Schedule Lesson Reference", {"parent": chapter}, "lesson"
    )
    content = frappe.db.get_value("Course Lesson", lesson, "content")
    return [r["folder_ref"] for r in editorjs.scan_folder_refs(content)]


class TestTemplateImportFolders(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.scale = make_grading_scale()
        cls.course = make_course(cls.scale)
        cls.instr_a, cls.user_a = make_teacher()
        cls.instr_b, cls.user_b = make_teacher()
        cls.registrar = make_user(roles=("Registrar", "Program Chair")).name

    def setUp(self):
        frappe.set_user("Administrator")
        self.source = make_cs(self.course, self.scale, self.instr_a, f"S{uid()}"[-6:])
        _add_scac(self.source)
        self.course_folder = make_folder(course=self.course)
        self.instr_folder = make_folder(
            course=self.course, scope="Instructor", instructor=self.instr_a
        )
        put_file(
            self.instr_folder.file_reference, name="a-notes.txt", content=b"A's notes"
        )
        self.section_folder = make_folder(
            course=self.course, scope="Section", course_schedule=self.source
        )
        self.school_folder = make_folder(scope="School")
        self.lesson = _add_lesson(
            self.source,
            [
                _folder_block(self.course_folder),
                _folder_block(self.instr_folder),
                _folder_block(self.section_folder),
                _folder_block(self.school_folder),
            ],
        )

    def tearDown(self):
        frappe.set_user("Administrator")

    def _import_into(self, instructor):
        target = make_cs(self.course, self.scale, instructor, f"T{uid()}"[-6:])
        frappe.set_user(self.registrar)
        result = frappe.get_doc("Course Schedule", target).import_template(self.source)
        frappe.set_user("Administrator")
        return target, result

    def test_different_instructor(self):
        target, result = self._import_into(self.instr_b)
        self.assertEqual(result["lessons"], 1)

        refs = _copied_lesson_refs(target)
        # Course and School references are untouched.
        self.assertEqual(refs[0], self.course_folder.name)
        self.assertEqual(refs[3], self.school_folder.name)
        # The Section folder was re-scoped to Course in place (same docname).
        self.assertEqual(refs[2], self.section_folder.name)
        sec = frappe.get_doc("Course Folder", self.section_folder.name)
        self.assertEqual(sec.scope, "Course")
        self.assertIsNone(sec.course_schedule)
        self.assertEqual(
            frappe.db.get_value("File", sec.file_reference, "folder"),
            f"Home/Course Folders/{self.course}",
        )
        # A's Instructor folder was copied for B and the lesson rewritten to it.
        copy_name = refs[1]
        self.assertNotEqual(copy_name, self.instr_folder.name)
        copy = frappe.get_doc("Course Folder", copy_name)
        self.assertEqual(
            (copy.scope, copy.instructor, copy.course),
            ("Instructor", self.instr_b, self.course),
        )
        self.assertEqual(copy.foldername, self.instr_folder.foldername)
        copied_files = frappe.get_all(
            "File",
            filters={"folder": copy.file_reference},
            fields=["file_name", "is_private"],
        )
        self.assertEqual(
            [(f.file_name, f.is_private) for f in copied_files], [("a-notes.txt", 1)]
        )
        # The original is untouched and still A's.
        original = frappe.get_doc("Course Folder", self.instr_folder.name)
        self.assertEqual(
            (original.scope, original.instructor), ("Instructor", self.instr_a)
        )
        self.assertFalse(cf.user_may_write(copy.name, self.user_a))
        self.assertTrue(cf.user_may_write(copy.name, self.user_b))
        self.assertFalse(cf.user_may_write(self.instr_folder.name, self.user_b))

        # The result lists one re-scope and one copy.
        self.assertEqual(len(result["folder_rescoped"]), 1)
        self.assertEqual(result["folder_rescoped"][0]["to_scope"], "Course")
        self.assertEqual(len(result["folder_copied"]), 1)
        self.assertEqual(result["folder_copied"][0]["folder"], copy.name)

        # Activity rows on all four.
        for folder, action in (
            (self.course_folder.name, "referenced"),
            (self.school_folder.name, "referenced"),
            (self.section_folder.name, "re-scoped"),
            (copy.name, "copied"),
            (self.instr_folder.name, "copied"),
        ):
            actions = frappe.get_all(
                "Course Folder Activity", filters={"parent": folder}, pluck="action"
            )
            self.assertIn(action, actions, folder)

        # A student enrolled only in the target section reads all four.
        _student, user = make_enrolled_student(target)
        for folder in refs:
            self.assertTrue(cf.user_may_read(folder, user), folder)

    def test_same_instructor(self):
        a_filter = {
            "course": self.course,
            "scope": "Instructor",
            "instructor": self.instr_a,
        }
        before = frappe.db.count("Course Folder", a_filter)
        target, result = self._import_into(self.instr_a)

        refs = _copied_lesson_refs(target)
        self.assertEqual(
            refs,
            [
                self.course_folder.name,
                self.instr_folder.name,
                self.section_folder.name,
                self.school_folder.name,
            ],
        )
        sec = frappe.get_doc("Course Folder", self.section_folder.name)
        self.assertEqual((sec.scope, sec.instructor), ("Instructor", self.instr_a))
        self.assertEqual(
            frappe.db.get_value("File", sec.file_reference, "folder"),
            f"Home/Course Folders/{self.course}/by-instructor/{self.instr_a}",
        )
        self.assertEqual(len(result["folder_rescoped"]), 1)
        self.assertEqual(result["folder_rescoped"][0]["to_scope"], "Instructor")
        self.assertEqual(result["folder_copied"], [])
        # No new Instructor folder appeared for A.
        # Only the re-scoped Section folder joined A's Instructor folders.
        self.assertEqual(frappe.db.count("Course Folder", a_filter), before + 1)
        _student, user = make_enrolled_student(target)
        for folder in refs:
            self.assertTrue(cf.user_may_read(folder, user), folder)

    def test_source_must_be_readable(self):
        target = make_cs(self.course, self.scale, self.instr_b, f"T{uid()}"[-6:])
        # A user with the import roles but no read permission on Course Schedule.
        frappe.set_user(self.registrar)
        original = frappe.has_permission
        try:
            frappe.has_permission = lambda *a, **k: (_ for _ in ()).throw(
                frappe.PermissionError("x")
            )
            with self.assertRaises(frappe.PermissionError):
                frappe.get_doc("Course Schedule", target)._validate_target_for_import(
                    self.source
                )
        finally:
            frappe.has_permission = original


def run_smoke():
    """bench --site <site> execute seminary.seminary.doctype.course_schedule.test_template_folders.run_smoke"""
    import unittest

    frappe.flags.in_test = True
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTemplateImportFolders)
    result = unittest.TextTestRunner(verbosity=2, stream=None).run(suite)
    frappe.db.rollback()
    return {
        "ran": result.testsRun,
        "failures": [str(f[0]) + "\n" + f[1] for f in result.failures],
        "errors": [str(e[0]) + "\n" + e[1] for e in result.errors],
        "ok": result.wasSuccessful(),
    }
