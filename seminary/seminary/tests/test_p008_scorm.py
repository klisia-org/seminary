# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008 F8 / F12: SCORM packages are stored, never unpacked, and the dead
renderer is gone (p005 A01-6, A02-4, A08-3; p005a A05-8, A05-9, A05-13)."""

import io
import os
import zipfile

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import api
from seminary.seminary.tests.test_p006_api import _make_user


def _zip_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("imsmanifest.xml", "<manifest/>")
        zf.writestr("index.html", "<script>alert(1)</script>")
    return buf.getvalue()


def _file(name, content, owner=None, private=1):
    doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": name,
            "content": content,
            "is_private": private,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert()
    if owner:
        frappe.db.set_value("File", doc.name, "owner", owner, update_modified=False)
    return doc.name


class TestP008Scorm(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uploader = _make_user("Instructor", "f8-uploader")
        cls.other = _make_user("Instructor", "f8-other")

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_the_extraction_code_is_gone(self):
        for name in (
            "extract_package",
            "check_for_malicious_code",
            "get_manifest_file",
            "get_launch_file",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(api, name))
        import seminary.page_renderers as pr

        self.assertFalse(hasattr(pr, "SCORMRenderer"))

    def test_a_package_the_caller_cannot_read_is_refused(self):
        name = _file("f8-private.zip", _zip_bytes(), owner=self.uploader)
        frappe.set_user(self.other)
        with self.assertRaises(frappe.PermissionError):
            api._check_scorm_package(name)
        frappe.set_user(self.uploader)
        self.assertEqual(api._check_scorm_package(name).name, name)

    def test_only_a_zip_is_a_package(self):
        name = _file("f8-notes.txt", b"hello")
        with self.assertRaises(frappe.ValidationError):
            api._check_scorm_package(name)
        with self.assertRaises(frappe.DoesNotExistError):
            api._check_scorm_package("ZZT-no-such-file")

    def test_pin_attaches_an_unattached_package_and_keeps_it_private(self):
        name = _file("f8-pin.zip", _zip_bytes())
        api.pin_scorm_package("ZZT-f8-chapter", name)
        got = frappe.db.get_value(
            "File",
            name,
            [
                "attached_to_doctype",
                "attached_to_name",
                "attached_to_field",
                "is_private",
            ],
            as_dict=True,
        )
        self.assertEqual(got.attached_to_doctype, "Course Schedule Chapter")
        self.assertEqual(got.attached_to_name, "ZZT-f8-chapter")
        self.assertEqual(got.attached_to_field, "scorm_package")
        self.assertEqual(got.is_private, 1)

    def test_pin_leaves_a_shared_package_where_it_is(self):
        name = _file("f8-shared.zip", _zip_bytes())
        api.pin_scorm_package("ZZT-f8-first", name)
        api.pin_scorm_package("ZZT-f8-second", name)  # a template import shares it
        self.assertEqual(
            frappe.db.get_value("File", name, "attached_to_name"), "ZZT-f8-first"
        )

    def test_the_teardown_patch_removes_the_public_tree_and_is_idempotent(self):
        from seminary.seminary.patches import p008_scorm_teardown

        planted = frappe.get_site_path("public", "scorm", "ZZT-course", "ZZT-chapter")
        os.makedirs(planted, exist_ok=True)
        with open(os.path.join(planted, "index.html"), "w") as fh:
            fh.write("<script>alert(1)</script>")
        keep = frappe.get_site_path("public", "files")
        p008_scorm_teardown.execute()
        self.assertFalse(os.path.exists(frappe.get_site_path("public", "scorm")))
        self.assertTrue(os.path.isdir(keep))
        p008_scorm_teardown.execute()  # nothing left: still fine
