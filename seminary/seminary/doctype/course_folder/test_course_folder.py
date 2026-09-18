# Copyright (c) 2025, Klisia / SeminaryERP and Contributors
# See license.txt
"""Course Folder scopes and the folder API (p006 F2, ADR §2.2a/§2.2c).

Fixture shape, the DTS case from the ADR: one Course with three sections —
CS1 and CS3 taught by instructor A, CS2 by instructor B — and one student on
each roster. Every rule in the read table is exercised from a student's seat,
and the `Home` hole is checked closed through the API itself.

Run directly (the app-wide suite does not run on the dev sites):
    bench --site <site> execute \
        seminary.seminary.doctype.course_folder.test_course_folder.run_smoke
"""

import frappe
from frappe.tests import IntegrationTestCase as FrappeTestCase

from seminary.seminary.doctype.course_folder import course_folder as cf
from seminary.seminary.tests.cohort_fixtures import (
    current_term,
    make_instructor,
    make_person,
    make_student,
    make_user,
    uid,
)

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
    "User",
    "Person",
    "Course",
    "Course Schedule",
    "Instructor",
    "File",
    "Course Folder",
]  # p006: fixtures are built in-test; the app's Student/Instructor test records predate Person-first identity


# --- fixtures ----------------------------------------------------------------


def make_grading_scale():
    name = f"CF Scale {uid()}"
    doc = frappe.get_doc(
        {
            "doctype": "Grading Scale",
            "grading_scale_name": name,
            "grscale_type": "Points",
            "maxnumgrade": 100,
            "intervals": [
                {"grade_code": "A", "threshold": 0, "grade_pass": "Pass"}  # nosec B105
            ],
        }
    )
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return doc.name


def make_course(scale):
    doc = frappe.get_doc(
        {
            "doctype": "Course",
            "course_name": f"CF Course {uid()}",
            "coursecode": f"CF{frappe.generate_hash(length=4)}",
            "default_grading_scale": scale,
        }
    )
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return doc.name


def _any_dated_term():
    """`Course Schedule.validate_date` unpacks the term's dates; a test site may
    have no term flagged current, so fall back to any dated term or make one."""
    from frappe.utils import add_days, nowdate

    term = frappe.db.get_value(
        "Academic Term",
        {"term_start_date": ["is", "set"], "term_end_date": ["is", "set"]},
        "name",
    )
    if term:
        return term
    doc = frappe.get_doc(
        {
            "doctype": "Academic Term",
            "academic_year": frappe.db.get_value("Academic Year", {}, "name"),
            "term_name": f"P006 {frappe.generate_hash(length=4)}",
            "term_start_date": nowdate(),
            "term_end_date": add_days(nowdate(), 90),
        }
    )
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return doc.name


def make_cs(course, scale, instructor, section):
    """A Course Schedule taught by `instructor`, without SCAC rows."""
    from frappe.utils import nowdate

    term = current_term() or _any_dated_term()
    dates = frappe.db.get_value(
        "Academic Term", term, ["term_start_date", "term_end_date"], as_dict=True
    )
    cs = frappe.get_doc(
        {
            "doctype": "Course Schedule",
            "course": course,
            "academic_term": term,
            "section": section,
            "gradesc_cs": scale,
            "modality": "Virtual",
            "c_datestart": (dates and dates.term_start_date) or nowdate(),
            "c_dateend": (dates and dates.term_end_date) or nowdate(),
            "instructor1": [{"instructor": instructor}],
        }
    )
    cs.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.delete(
        "Scheduled Course Assess Criteria",
        {"parent": cs.name, "parenttype": "Course Schedule"},
    )
    return cs.name


def _category(name, of_record):
    if not frappe.db.exists("Instructor Category", name):
        frappe.get_doc(
            {
                "doctype": "Instructor Category",
                "category_name": name,
                "is_instructor_of_record": 1 if of_record else 0,
            }
        ).insert(ignore_permissions=True)
    return name


def make_teacher(of_record=True):
    """An Instructor. Of record by default: p007 §2.8 makes the folder read
    rule tier-aware, and the ADR §5.10 "a professor reads any folder to copy
    from it" applies to instructors of record; a grader reads only the
    folders of the sections they are listed on."""
    user = make_user(roles=("Instructor",))
    person = make_person("Instr", user=user.name)
    inst = make_instructor(person)
    frappe.db.set_value(
        "Instructor",
        inst.name,
        "default_inst_category",
        _category("P006 Of Record" if of_record else "P006 Grader", of_record),
    )
    frappe.local.p007_cache = {}
    return inst.name, user.name


def make_enrolled_student(*course_schedules):
    """A Student (with the Student role) on the active roster of each section."""
    user = make_user(roles=("Student",))
    person = make_person("Student", user=user.name)
    student = make_student(person)
    for cs in course_schedules:
        frappe.get_doc(
            {
                "doctype": "Scheduled Course Roster",
                "student": student.name,
                "course_sc": cs,
                "active": 1,
                "stuname_roster": student.student_name,
            }
        ).insert(ignore_permissions=True, ignore_mandatory=True)
    return student.name, user.name


def make_folder(**values):
    values.setdefault("doctype", "Course Folder")
    values.setdefault("foldername", f"Folder {uid()}")
    doc = frappe.get_doc(values)
    doc.insert(ignore_permissions=True)
    return doc


def put_file(folder_file, name="note.txt", content=b"hello"):
    return frappe.get_doc(
        {
            "doctype": "File",
            "file_name": name,
            "folder": folder_file,
            "is_private": 1,
            "content": content,
        }
    ).insert(ignore_permissions=True)


class TestCourseFolderScopes(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.scale = make_grading_scale()
        cls.course = make_course(cls.scale)
        cls.other_course = make_course(cls.scale)
        cls.instr_a, cls.user_a = make_teacher()
        cls.instr_b, cls.user_b = make_teacher()
        cls.cs1 = make_cs(cls.course, cls.scale, cls.instr_a, "A")
        cls.cs2 = make_cs(cls.course, cls.scale, cls.instr_b, "B")
        cls.cs3 = make_cs(cls.course, cls.scale, cls.instr_a, "C")
        cls.cs_other = make_cs(cls.other_course, cls.scale, cls.instr_b, "A")
        cls.stu_a, cls.user_stu_a = make_enrolled_student(cls.cs1)
        cls.stu_b, cls.user_stu_b = make_enrolled_student(cls.cs2)
        cls.stu_c, cls.user_stu_c = make_enrolled_student(cls.cs3)
        cls.stu_other, cls.user_stu_other = make_enrolled_student(cls.cs_other)
        cls.stu_none, cls.user_stu_none = make_enrolled_student()
        cls.chair = make_user(roles=("Program Chair",)).name
        cls.nobody = make_user().name

        cls.course_folder = make_folder(course=cls.course)
        cls.instr_folder = make_folder(
            course=cls.course, scope="Instructor", instructor=cls.instr_a
        )
        cls.section_folder = make_folder(
            course=cls.course, scope="Section", course_schedule=cls.cs1
        )
        cls.school_folder = make_folder(scope="School", foldername="Policies")
        put_file(cls.course_folder.file_reference)

    def tearDown(self):
        frappe.set_user("Administrator")

    # --- model -----------------------------------------------------------

    def test_disk_layout_per_scope(self):
        root = "Home/Course Folders"
        self.assertEqual(self.course_folder.parent_folder, f"{root}/{self.course}")
        self.assertEqual(
            self.instr_folder.parent_folder,
            f"{root}/{self.course}/by-instructor/{self.instr_a}",
        )
        self.assertEqual(
            self.section_folder.parent_folder, f"{root}/{self.course}/{self.cs1}"
        )
        self.assertEqual(self.school_folder.parent_folder, f"{root}/School")
        for folder in (self.course_folder, self.instr_folder, self.school_folder):
            self.assertTrue(frappe.db.exists("File", folder.file_reference))
        # A Section folder derives its course from the section.
        self.assertEqual(self.section_folder.course, self.course)
        self.assertEqual(self.section_folder.scope, "Section")

    def test_duplicate_key_refused(self):
        with self.assertRaises(frappe.DuplicateEntryError):
            make_folder(course=self.course, foldername=self.course_folder.foldername)
        # Same name at another scope is a different folder.
        other = make_folder(
            course=self.course,
            scope="Instructor",
            instructor=self.instr_b,
            foldername=self.course_folder.foldername,
        )
        self.assertNotEqual(other.name, self.course_folder.name)

    # --- read rule -------------------------------------------------------

    def test_course_scope(self):
        f = self.course_folder.name
        self.assertTrue(cf.user_may_read(f, self.user_stu_a))
        self.assertTrue(cf.user_may_read(f, self.user_stu_b))
        self.assertFalse(cf.user_may_read(f, self.user_stu_other))
        self.assertFalse(cf.user_may_read(f, self.user_stu_none))
        self.assertFalse(cf.user_may_read(f, self.nobody))
        self.assertFalse(cf.user_may_read(f, "Guest"))
        # Every grader role reads every folder.
        self.assertTrue(cf.user_may_read(f, self.user_b))
        self.assertTrue(cf.user_may_read(f, self.chair))

    def test_course_scope_shared_with(self):
        folder = make_folder(course=self.course)
        self.assertFalse(cf.user_may_read(folder.name, self.user_stu_other))
        folder.append("shared_with", {"course": self.other_course})
        folder.save(ignore_permissions=True)
        self.assertTrue(cf.user_may_read(folder.name, self.user_stu_other))

    def test_instructor_scope(self):
        f = self.instr_folder.name
        # Follows instructor A into every section they teach...
        self.assertTrue(cf.user_may_read(f, self.user_stu_a))
        self.assertTrue(cf.user_may_read(f, self.user_stu_c))
        # ...and not into B's section of the same course.
        self.assertFalse(cf.user_may_read(f, self.user_stu_b))
        # A colleague reads it (grader role) but does not write it.
        self.assertTrue(cf.user_may_read(f, self.user_b))
        self.assertFalse(cf.user_may_write(f, self.user_b))
        self.assertTrue(cf.user_may_write(f, self.user_a))
        self.assertTrue(cf.user_may_write(f, self.chair))
        # p007 §2.8: a grader listed on no section of this course reads nothing.
        _, grader = make_teacher(of_record=False)
        self.assertFalse(cf.user_may_read(f, grader))

    def test_instructor_scope_shared_with_instructors(self):
        folder = make_folder(
            course=self.course, scope="Instructor", instructor=self.instr_a
        )
        self.assertFalse(cf.user_may_read(folder.name, self.user_stu_b))
        folder.append("shared_with_instructors", {"instructor": self.instr_b})
        folder.save(ignore_permissions=True)
        self.assertTrue(cf.user_may_read(folder.name, self.user_stu_b))
        # Sharing grants B's students read; it does not make B a writer.
        self.assertFalse(cf.user_may_write(folder.name, self.user_b))

    def test_section_scope(self):
        f = self.section_folder.name
        self.assertTrue(cf.user_may_read(f, self.user_stu_a))
        self.assertFalse(cf.user_may_read(f, self.user_stu_b))
        self.assertFalse(cf.user_may_read(f, self.user_stu_c))
        # Section write is per-section: A teaches CS1, B does not.
        self.assertTrue(cf.user_may_write(f, self.user_a))
        self.assertFalse(cf.user_may_write(f, self.user_b))
        self.assertTrue(cf.user_may_write(f, self.chair))

    def test_school_scope(self):
        f = self.school_folder.name
        for user in (self.user_stu_a, self.user_stu_none, self.user_a, self.chair):
            self.assertTrue(cf.user_may_read(f, user), user)
        self.assertFalse(cf.user_may_read(f, self.nobody))
        self.assertFalse(cf.user_may_read(f, "Guest"))
        # Course/School write stays with the doctype roles.
        self.assertTrue(cf.user_may_write(f, self.user_b))
        self.assertFalse(cf.user_may_write(f, self.user_stu_a))

    def test_inactive_roster_does_not_read(self):
        student, user = make_enrolled_student(self.cs1)
        frappe.db.set_value(
            "Scheduled Course Roster",
            {"student": student, "course_sc": self.cs1},
            "active",
            0,
        )
        self.assertFalse(cf.user_may_read(self.section_folder.name, user))
        self.assertFalse(cf.user_may_read(self.course_folder.name, user))

    def test_has_permission_delegates(self):
        doc = frappe.get_doc("Course Folder", self.section_folder.name)
        self.assertTrue(doc.has_permission("read", user=self.user_stu_a))
        self.assertFalse(doc.has_permission("read", user=self.user_stu_b))
        self.assertFalse(doc.has_permission("write", user=self.user_b))
        self.assertTrue(doc.has_permission("write", user=self.user_a))

    # --- supersedes ------------------------------------------------------

    def test_resolve_latest(self):
        v1 = make_folder(scope="School", foldername=f"Policy {uid()}")
        v2 = make_folder(
            scope="School", foldername=f"Policy {uid()}", supersedes=v1.name
        )
        v3 = make_folder(
            scope="School", foldername=f"Policy {uid()}", supersedes=v2.name
        )
        self.assertEqual(cf.resolve_latest(v1.name), v3.name)
        self.assertEqual(cf.resolve_latest(v2.name), v3.name)
        self.assertEqual(cf.resolve_latest(v3.name), v3.name)
        # A cycle terminates.
        frappe.db.set_value("Course Folder", v1.name, "supersedes", v3.name)
        self.assertIn(cf.resolve_latest(v1.name), {v1.name, v2.name, v3.name})
        # Only a School folder can be superseded.
        with self.assertRaises(frappe.ValidationError):
            make_folder(scope="School", supersedes=self.course_folder.name)

    # --- activity + rescope ---------------------------------------------

    def test_log_activity_and_rescope(self):
        folder = make_folder(
            course=self.course, scope="Section", course_schedule=self.cs1
        )
        cf.log_activity(folder.name, "added", file_name="a.pdf", section=self.cs1)
        rows = frappe.get_all(
            "Course Folder Activity",
            filters={"parent": folder.name},
            fields=["action", "file_name", "section", "who"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].action, "added")
        self.assertEqual(rows[0].section, self.cs1)
        self.assertEqual(rows[0].who, "Administrator")

        old_file = folder.file_reference
        moved = cf.rescope(folder.name, "Instructor", instructor=self.instr_a)
        self.assertEqual(moved.scope, "Instructor")
        self.assertEqual(moved.file_reference, old_file)
        self.assertEqual(
            frappe.db.get_value("File", old_file, "folder"),
            f"Home/Course Folders/{self.course}/by-instructor/{self.instr_a}",
        )
        self.assertIsNone(moved.course_schedule)
        actions = frappe.get_all(
            "Course Folder Activity", filters={"parent": folder.name}, pluck="action"
        )
        self.assertIn("re-scoped", actions)
        # Now stu_c (A's other section) reads it; stu_b does not.
        self.assertTrue(cf.user_may_read(folder.name, self.user_stu_c))
        self.assertFalse(cf.user_may_read(folder.name, self.user_stu_b))

    # --- whitelisted helpers ---------------------------------------------

    def test_folder_context_and_embeddable(self):
        frappe.set_user(self.user_a)
        ctx = cf.folder_context()
        self.assertEqual(
            ctx,
            {
                "course": None,
                "course_schedule": None,
                "instructor": self.instr_a,
                "can_school": False,
            },
        )
        ctx = cf.folder_context(course_schedule=self.cs1)
        self.assertEqual(ctx["course"], self.course)
        self.assertEqual(ctx["course_schedule"], self.cs1)
        names = {
            r["name"]: r["scope"]
            for r in cf.list_embeddable_folders(course_schedule=self.cs1)
        }
        self.assertIn(self.course_folder.name, names)
        self.assertIn(self.instr_folder.name, names)
        self.assertIn(self.section_folder.name, names)
        self.assertIn(self.school_folder.name, names)

        frappe.set_user(self.user_b)
        names = {
            r["name"] for r in cf.list_embeddable_folders(course_schedule=self.cs2)
        }
        self.assertNotIn(self.instr_folder.name, names)  # A's, not shared with B
        self.assertNotIn(self.section_folder.name, names)  # CS1's, not CS2's
        self.assertIn(self.course_folder.name, names)

        frappe.set_user(self.user_stu_a)
        with self.assertRaises(frappe.PermissionError):
            cf.list_embeddable_folders(course_schedule=self.cs1)

    # --- the API -----------------------------------------------------------

    def test_api_home_is_closed_to_students(self):
        from seminary.api import folder_upload as api

        frappe.set_user(self.user_stu_a)
        with self.assertRaises(frappe.PermissionError):
            api.download_folder(folder_id="Home")
        with self.assertRaises(frappe.PermissionError):
            api.get_files_in_folder(folder_id="Home/Attachments")
        # Names are not identifiers any more.
        with self.assertRaises(frappe.PermissionError):
            api.get_files_in_folder(foldername=self.course_folder.foldername)

    def test_api_scope_rule(self):
        from seminary.api import folder_upload as api

        frappe.set_user(self.user_stu_a)
        listing = api.get_files_in_folder(course_folder=self.course_folder.name)
        self.assertEqual(listing["folder_id"], self.course_folder.file_reference)
        self.assertEqual([e.file_name for e in listing["entries"]], ["note.txt"])
        api.download_folder(course_folder=self.course_folder.name)
        self.assertEqual(frappe.local.response.type, "download")
        # A subfolder File docname works as `folder_id`; a wrong section does not.
        api.get_files_in_folder(folder_id=self.section_folder.file_reference)
        frappe.set_user(self.user_stu_b)
        with self.assertRaises(frappe.PermissionError):
            api.get_files_in_folder(course_folder=self.section_folder.name)
        with self.assertRaises(frappe.PermissionError):
            api.download_folder(folder_id=self.section_folder.file_reference)

    def test_api_superseded_school_folder_resolves_forward(self):
        from seminary.api import folder_upload as api

        v1 = make_folder(scope="School", foldername=f"Policy {uid()}")
        v2 = make_folder(
            scope="School", foldername=f"Policy {uid()}", supersedes=v1.name
        )
        put_file(v2.file_reference, name="v2.txt")
        frappe.set_user(self.user_stu_a)
        listing = api.get_files_in_folder(course_folder=v1.name)
        self.assertEqual(listing["folder_id"], v2.file_reference)
        self.assertEqual([e.file_name for e in listing["entries"]], ["v2.txt"])

    def test_api_mutations_log_activity(self):
        from seminary.api import folder_upload as api

        folder = make_folder(
            course=self.course, scope="Section", course_schedule=self.cs1
        )
        frappe.set_user(self.user_a)
        sub = api.create_subfolder(
            parent_folder_id=folder.file_reference,
            subfoldername="week1",
            course_schedule=self.cs1,
        )
        self.assertEqual(sub["folder"], folder.file_reference)
        f = put_file(sub["name"], name="slides.txt")
        api.rename_file(file_id=f.name, new_name="deck.txt", course_schedule=self.cs1)
        api.delete_file(file_id=f.name, course_schedule=self.cs1)
        rows = frappe.get_all(
            "Course Folder Activity",
            filters={"parent": folder.name},
            fields=["action", "file_name", "section", "who"],
            order_by="idx asc",
        )
        self.assertEqual([r.action for r in rows], ["added", "renamed", "removed"])
        self.assertTrue(
            all(r.section == self.cs1 and r.who == self.user_a for r in rows)
        )
        # B does not teach CS1: no write on its Section folder.
        frappe.set_user(self.user_b)
        with self.assertRaises(frappe.PermissionError):
            api.create_subfolder(
                parent_folder_id=folder.file_reference, subfoldername="x"
            )
        # Outside a Course Folder only the owner (or a System Manager) gets in.
        frappe.set_user("Administrator")
        own = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": f"personal {uid()}",
                "is_folder": 1,
                "folder": "Home",
            }
        ).insert()
        frappe.db.set_value("File", own.name, "owner", self.user_a)
        frappe.set_user(self.user_a)
        api.get_files_in_folder(folder_id=own.name)
        frappe.set_user(self.user_b)
        with self.assertRaises(frappe.PermissionError):
            api.get_files_in_folder(folder_id=own.name)


def run_smoke():
    """bench --site <site> execute seminary.seminary.doctype.course_folder.test_course_folder.run_smoke"""
    import unittest

    frappe.flags.in_test = True
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCourseFolderScopes)
    result = unittest.TextTestRunner(verbosity=2, stream=None).run(suite)
    frappe.db.rollback()
    return {
        "ran": result.testsRun,
        "failures": [str(f[0]) + "\n" + f[1] for f in result.failures],
        "errors": [str(e[0]) + "\n" + e[1] for e in result.errors],
        "ok": result.wasSuccessful(),
    }
