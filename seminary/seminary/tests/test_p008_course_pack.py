# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008 F9 / F10: a Course Pack is untrusted input (p005 A01-7 Critical, A08-2,
A10-3; p005a A08-6). Units rather than a full import run -- the app's own
test_course_pack dies in its bootstrap on the Instructor test records (p007
§7.4), and the properties under test live in these functions."""

import io
import json
import zipfile
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.course_pack import import_ as imp
from seminary.seminary.course_pack.constants import (
    CHAPTER_FIELDS,
    QUESTION_FIELDS,
    SCAC_FIELDS,
)
from seminary.seminary.tests.test_p006_api import _make_user


def _zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _importer(manifest, zf=None):
    obj = object.__new__(imp._Importer)
    obj.m, obj.zf = manifest, zf
    obj.url_map, obj.q_map, obj.a_map = {}, {}, {}
    obj.course, obj.warnings = None, []
    return obj


class TestP008CoursePack(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "f9-student")
        cls.chair = _make_user("Program Chair", "f9-chair")

    def tearDown(self):
        frappe.set_user("Administrator")
        for key in (
            "course_pack_max_entries",
            "course_pack_max_manifest_bytes",
            "course_pack_max_member_bytes",
        ):
            frappe.conf.pop(key, None)

    # ------------------------------------------------------------ allow-lists
    def test_a_doctype_the_format_does_not_define_is_refused(self):
        for section, doctype in (
            ("questions", "User"),
            ("activities", "Client Script"),
            ("activities", "Question"),
            ("questions", None),
        ):
            with self.subTest(section=section, doctype=doctype):
                with self.assertRaises(frappe.ValidationError):
                    imp._importable(section, doctype)
        self.assertEqual(imp._importable("questions", "Question"), QUESTION_FIELDS)

    def test_a_pack_naming_user_creates_nothing(self):
        users_before = frappe.db.count("User")
        hostile = {
            "activities": {
                "a1": {
                    "doctype": "User",
                    "fields": {
                        "email": "pwn@evil.test",
                        "first_name": "pwn",
                        "roles": [{"role": "System Manager"}],
                    },
                }
            }
        }
        with self.assertRaises(frappe.ValidationError):
            _importer(hostile).import_activities()
        with self.assertRaises(frappe.ValidationError):
            _importer(
                {"questions": {"q1": {"doctype": "Client Script", "fields": {}}}}
            ).import_questions()
        self.assertEqual(frappe.db.count("User"), users_before)
        self.assertFalse(frappe.db.exists("User", "pwn@evil.test"))

    def test_fields_outside_the_allow_list_do_not_ride_in(self):
        picked = imp._only(
            {
                "question": "Q?",
                "type": "User Input",
                "owner": "evil@x.y",
                "docstatus": 1,
                "name": "chosen-name",
                "doctype": "User",
                "parent": "x",
            },
            QUESTION_FIELDS,
        )
        self.assertEqual(set(picked), {"question", "type"})
        # the second vector: import_scac spread the manifest's fields LAST
        self.assertEqual(
            imp._only({"doctype": "User", "parent": "x", "title": "t"}, SCAC_FIELDS),
            {"title": "t"},
        )
        self.assertEqual(imp._only("not a dict", SCAC_FIELDS), {})
        for gone in ("scorm_package_path", "manifest_file", "launch_file"):
            self.assertNotIn(gone, CHAPTER_FIELDS)

    def test_an_imported_question_keeps_only_pack_fields(self):
        manifest = {
            "questions": {
                "q1": {
                    "doctype": "Question",
                    "fields": {
                        "question": f"F9-{frappe.generate_hash(length=6)}",
                        "type": "User Input",
                        "possibility_1": "x",
                        "owner": "evil@x.y",
                    },
                }
            }
        }
        frappe.set_user(self.chair)
        importer = _importer(manifest)
        importer.import_questions()
        frappe.set_user("Administrator")
        doc = frappe.get_doc("Question", importer.q_map["q1"])
        self.assertEqual(doc.owner, self.chair)
        self.assertEqual(doc.possibility_1, "x")

    # ------------------------------------------------------ order of operations
    def test_a_student_is_refused_before_the_archive_is_opened(self):
        frappe.set_user(self.student)
        with patch.object(
            imp.zipfile, "ZipFile", side_effect=AssertionError("archive was opened")
        ):
            with self.assertRaises(frappe.PermissionError):
                imp.import_pack_from_bytes(b"irrelevant", "new")
            with self.assertRaises(frappe.PermissionError):
                imp.import_course_pack("/private/files/whatever.zip", "new")

    def test_the_pack_file_must_be_readable_and_a_zip(self):
        def _file(name, content, owner):
            doc = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": name,
                    "content": content,
                    "is_private": 1,
                }
            )
            doc.flags.ignore_permissions = True
            doc.insert()
            frappe.db.set_value("File", doc.name, "owner", owner, update_modified=False)
            return doc.file_url

        other = _make_user("Registrar", "f9-other-reg")
        theirs = _file("f9-theirs.zip", _zip({"manifest.json": "{}"}), other)
        notes = _file("f9-notes.txt", b"secret notes", self.chair)
        frappe.set_user(self.chair)
        with self.assertRaises(frappe.PermissionError):
            imp._read_pack_bytes(theirs)
        with self.assertRaises(frappe.ValidationError):
            imp._read_pack_bytes(notes)

    # ------------------------------------------------------------------ bounds
    def test_bounds_are_checked_before_anything_is_read(self):
        frappe.set_user(self.chair)
        with self.assertRaises(frappe.ValidationError):
            imp.import_pack_from_bytes(b"this is not a zip", "new")
        with self.assertRaises(frappe.ValidationError):  # no manifest
            imp.import_pack_from_bytes(_zip({"other.json": "{}"}), "new")
        frappe.conf["course_pack_max_entries"] = 2
        with self.assertRaises(frappe.ValidationError):
            imp.import_pack_from_bytes(
                _zip({"manifest.json": "{}", "a": "1", "b": "2"}), "new"
            )
        frappe.conf.pop("course_pack_max_entries")
        frappe.conf["course_pack_max_manifest_bytes"] = 10
        with self.assertRaises(frappe.ValidationError):
            imp.import_pack_from_bytes(
                _zip({"manifest.json": json.dumps({"x": "y" * 50})}), "new"
            )

    def test_a_bomb_trips_the_ratio(self):
        bomb = _zip(
            {
                "manifest.json": "{}",
                "media/zeros": b"\0" * (imp.PACK_RATIO_FLOOR_BYTES + 1024),
            }
        )
        self.assertLess(len(bomb), 2 * 1024 * 1024)
        frappe.set_user(self.chair)
        with self.assertRaises(frappe.ValidationError):
            imp.import_pack_from_bytes(bomb, "new")

    def test_one_enormous_member_is_refused(self):
        """The uncompressed total is a *sum*: before F17b a single 4 GB member
        passed every check, and the worker then held two copies of it."""
        frappe.set_user(self.chair)
        pack = _zip({"manifest.json": "{}", "media/big": b"x" * 4096})
        frappe.conf["course_pack_max_member_bytes"] = 1024
        try:
            with self.assertRaises(frappe.ValidationError):
                imp.import_pack_from_bytes(pack, "new")
        finally:
            frappe.conf.pop("course_pack_max_member_bytes", None)

    def test_a_manifest_that_is_not_an_object_is_refused(self):
        frappe.set_user(self.chair)
        with self.assertRaises(frappe.ValidationError):
            imp.import_pack_from_bytes(_zip({"manifest.json": "[1, 2]"}), "new")

    # ------------------------------------------------------------------- media
    def test_imported_media_is_private_whatever_the_manifest_says(self):
        import hashlib

        blob = b"lecture-notes"
        manifest = {
            "media": {
                "/files/orig.pdf": {
                    "key": "m1",
                    "file_name": f"f9-{frappe.generate_hash(length=6)}.txt",
                    "sha256": hashlib.sha256(blob).hexdigest(),
                    "is_private": 0,
                }
            }
        }
        zf = zipfile.ZipFile(io.BytesIO(_zip({"media/m1": blob})))
        importer = _importer(manifest, zf)
        importer._folder_media_urls = lambda: set()
        importer.import_media()
        url = importer.url_map["/files/orig.pdf"]
        self.assertTrue(url.startswith("/private/files/"))
        self.assertEqual(
            frappe.db.get_value("File", {"file_url": url}, "is_private"), 1
        )

    # --------------------------------------------------------------------- F10
    def test_imported_courses_get_distinct_codes(self):
        importer = _importer({"source": {"course_code": "ID-101<script>"}})
        first = importer._unique_coursecode("Imported A")
        self.assertEqual(first, "ID-101script")
        course = frappe.new_doc("Course")
        course.course_name = f"F10 {frappe.generate_hash(length=6)}"
        course.coursecode = first
        course.flags.ignore_permissions = True
        course.insert(ignore_mandatory=True)
        self.assertEqual(importer._unique_coursecode("Imported B"), "ID-101script-2")
        self.assertTrue(_importer({"source": {}})._unique_coursecode("Some Course"))

    def test_a_competency_never_gets_an_empty_prefix(self):
        doc = frappe.new_doc("Course Competency")
        doc.course, doc.coursecode, doc.competency_code = (
            "ZZT No Such Course",
            None,
            "ICVit",
        )
        doc.autoname()
        self.assertFalse(doc.name.startswith("-"))
        self.assertTrue(doc.name.endswith("-ICVit"))
