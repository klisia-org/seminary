# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p007 §8.2: every upload is private, a file is read through the document it
is attached to, and the public website is a registry of doctype.field pairs."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import file_policy
from seminary.seminary.tests.test_p006_api import _make_user
from seminary.seminary.tests.test_p007_docperms import (
    _any_course_schedule,
    _roster,
    _student_for,
)


def _file(user="Administrator", **fields):
    # Committed: a File insert registers a rollback that deletes its bytes,
    # which would then race the privacy flips these tests make.
    frappe.set_user(user)
    try:
        doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": f"zzt-p007-{frappe.generate_hash(length=6)}.txt",
                "content": "p007 " + frappe.generate_hash(length=8),
                **fields,
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
    finally:
        frappe.set_user("Administrator")
    return doc


class TestP007FilePolicy(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.cs, cls.cs2 = _any_course_schedule()
        cls.stu_user = _make_user("Student", "fp-a")
        cls.other_user = _make_user("Student", "fp-b")
        cls.stu = _student_for(cls.stu_user, "FPA")
        _student_for(cls.other_user, "FPB")
        _roster(cls.cs.name, cls.stu, cls.stu_user)
        cls.web_user = _make_user("Website Manager", "fp-web")
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for name in frappe.get_all(
            "File", {"file_name": ["like", "zzt-p007-%"]}, pluck="name"
        ):
            frappe.delete_doc("File", name, force=True, ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        frappe.set_user("Administrator")
        frappe.local.p007_cache = {}

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.local.p007_cache = {}

    def _readable(self, file_doc, user):
        frappe.set_user(user)
        frappe.local.p007_cache = {}
        try:
            return bool(frappe.get_doc("File", file_doc.name).is_downloadable())
        finally:
            frappe.set_user("Administrator")
            frappe.local.p007_cache = {}

    # ------------------------------------------------------------ who publishes

    def test_a_student_upload_lands_private(self):
        doc = _file(self.stu_user, is_private=0)
        self.assertEqual(doc.is_private, 1)
        self.assertTrue(doc.file_url.startswith("/private/files/"))

    def test_website_manager_and_system_manager_may_publish(self):
        self.assertEqual(_file(self.web_user, is_private=0).is_private, 0)
        self.assertEqual(_file("Administrator", is_private=0).is_private, 0)

    def test_a_file_on_a_seminary_document_is_private_whoever_uploads(self):
        doc = _file(
            "Administrator",
            is_private=0,
            attached_to_doctype="Student",
            attached_to_name=self.stu,
        )
        self.assertEqual(doc.is_private, 1)

    def test_a_student_cannot_flip_a_file_public(self):
        doc = _file(self.stu_user, is_private=1)
        frappe.set_user(self.stu_user)
        doc = frappe.get_doc("File", doc.name)
        doc.is_private = 0
        with self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)

    def test_the_server_flag_publishes(self):
        doc = _file(self.stu_user, is_private=1)
        frappe.set_user(self.stu_user)
        doc = frappe.get_doc("File", doc.name)
        doc.is_private = 0
        frappe.flags.seminary_public_file = True
        try:
            doc.save(ignore_permissions=True)
        finally:
            frappe.flags.seminary_public_file = False
        frappe.db.commit()
        self.assertTrue(doc.file_url.startswith("/files/"))

    # ------------------------------------------------------------------ registry

    def test_registry_predicate_decides_and_is_one_line_to_extend(self):
        program = frappe.get_all("Program", pluck="name", limit=1)
        if not program:
            self.skipTest("no Program on the test site")
        program = program[0]
        was = frappe.db.get_value("Program", program, "published")
        try:
            frappe.db.set_value("Program", program, "published", 0)
            doc = _file(
                "Administrator",
                is_private=0,
                attached_to_doctype="Program",
                attached_to_name=program,
                attached_to_field="hero_image",
            )
            self.assertEqual(doc.is_private, 1)
            frappe.db.set_value("Program", program, "published", 1)
            self.assertTrue(file_policy.may_be_public(doc))

            key = ("Course", "hero_image")
            self.assertFalse(file_policy._registered(*key)[0])
            file_policy.PUBLIC_FILE_FIELDS[key] = None
            try:
                self.assertEqual(file_policy._registered(*key), (True, None))
            finally:
                file_policy.PUBLIC_FILE_FIELDS.pop(key)
        finally:
            frappe.db.set_value("Program", program, "published", was)

    def test_sync_follows_the_host(self):
        program = frappe.get_all("Program", pluck="name", limit=1)
        if not program:
            self.skipTest("no Program on the test site")
        program = program[0]
        was = frappe.db.get_value(
            "Program", program, ["published", "hero_image"], as_dict=True
        )
        doc = _file(
            "Administrator",
            is_private=1,
            attached_to_doctype="Program",
            attached_to_name=program,
            attached_to_field="hero_image",
        )
        try:
            frappe.db.set_value(
                "Program", program, {"hero_image": doc.file_url, "published": 1}
            )
            file_policy.sync_public_state("Program", program)
            # A flip moves bytes on disk and registers a rollback that moves
            # them back; commit so two flips in one test do not collide.
            frappe.db.commit()
            url = frappe.db.get_value("Program", program, "hero_image")
            self.assertTrue(url.startswith("/files/"), url)
            self.assertEqual(frappe.db.get_value("File", doc.name, "is_private"), 0)

            frappe.db.set_value("Program", program, "published", 0)
            file_policy.sync_public_state("Program", program)
            frappe.db.commit()
            url = frappe.db.get_value("Program", program, "hero_image")
            self.assertTrue(url.startswith("/private/files/"), url)
        finally:
            frappe.db.set_value(
                "Program",
                program,
                {"published": was.published, "hero_image": was.hero_image},
            )

    def test_person_photo_rule(self):
        self.assertFalse(file_policy.person_photo_is_public(None))
        self.assertFalse(file_policy.person_photo_is_public("ZZT-no-such-person"))

    # -------------------------------------------------------------- who reads it

    def test_a_file_is_read_through_its_host(self):
        was = frappe.db.get_value("Course Schedule", self.cs.name, "published")
        frappe.db.set_value("Course Schedule", self.cs.name, "published", 1)
        try:
            doc = _file(
                is_private=1,
                attached_to_doctype="Course Schedule",
                attached_to_name=self.cs.name,
            )
            loose = _file(is_private=1)
            self.assertTrue(self._readable(doc, self.stu_user))
            self.assertFalse(self._readable(doc, self.other_user))
            self.assertFalse(self._readable(doc, "Guest"))
            self.assertFalse(self._readable(loose, self.stu_user))
            frappe.db.set_value("Course Schedule", self.cs.name, "published", 0)
            self.assertFalse(self._readable(doc, self.stu_user))
        finally:
            frappe.db.set_value("Course Schedule", self.cs.name, "published", was)

    def test_an_avatar_is_intranet_readable(self):
        person = frappe.get_all("Person", pluck="name", limit=1)
        if not person:
            self.skipTest("no Person on the test site")
        doc = _file(
            is_private=1,
            attached_to_doctype="Person",
            attached_to_name=person[0],
            attached_to_field="image",
        )
        self.assertTrue(self._readable(doc, self.other_user))
        self.assertFalse(self._readable(doc, "Guest"))

    # ------------------------------------------------------------ embedded files

    def _lesson_like(self, url, cs_name):
        return frappe._dict(
            doctype="Course Lesson",
            name="ZZT-p007-lesson",
            course_sc=cs_name,
            content='{"blocks":[{"type":"upload","data":{"file_url":"%s"}}]}' % url,
            get=lambda k, d=None: {
                "course_sc": cs_name,
                "content": '{"blocks":[{"type":"upload","data":{"file_url":"%s"}}]}'
                % url,
            }.get(k, d),
        )

    def test_lesson_content_adopts_the_uploaders_file(self):
        doc = _file(is_private=1)
        file_policy.adopt_embedded(self._lesson_like(doc.file_url, self.cs.name))
        row = frappe.db.get_value(
            "File", doc.name, ["attached_to_doctype", "attached_to_name"]
        )
        self.assertEqual(tuple(row), ("Course Schedule", self.cs.name))

    def test_naming_a_url_does_not_grant_access(self):
        secret = _file(
            is_private=1, attached_to_doctype="Student", attached_to_name=self.stu
        )
        frappe.set_user(self.other_user)
        try:
            file_policy.adopt_embedded(
                self._lesson_like(secret.file_url, self.cs2.name)
            )
        finally:
            frappe.set_user("Administrator")
        self.assertFalse(
            frappe.db.exists(
                "File",
                {
                    "file_url": secret.file_url,
                    "attached_to_doctype": "Course Schedule",
                    "attached_to_name": self.cs2.name,
                },
            )
        )

    def test_template_import_twins_the_source_sections_files(self):
        doc = _file(
            is_private=1,
            attached_to_doctype="Course Schedule",
            attached_to_name=self.cs.name,
        )
        frappe.set_user(self.other_user)  # cannot read the source row
        try:
            file_policy.adopt_embedded(
                self._lesson_like(doc.file_url, self.cs2.name),
                source_host=("Course Schedule", self.cs.name),
            )
        finally:
            frappe.set_user("Administrator")
        self.assertTrue(
            frappe.db.exists(
                "File",
                {
                    "file_url": doc.file_url,
                    "attached_to_doctype": "Course Schedule",
                    "attached_to_name": self.cs2.name,
                },
            )
        )
