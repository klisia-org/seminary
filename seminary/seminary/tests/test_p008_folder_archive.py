# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008 F17a: a course folder download is a cached artifact, not a zip built in
the request.

The bug this closes: `download_folder` assembled the whole archive in an
`io.BytesIO()` and then copied it again with `getvalue()`, with no cap on folder
size, entry count or depth and no rate limit -- and `user_may_read` admits a
student to the folders of their own sections, so any enrolled student could ask
a worker to build a multi-gigabyte zip in RAM, repeatedly.
"""

import os
import zipfile
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.api import folder_archive as fa
from seminary.api import folder_upload as fu
from seminary.seminary.tests.test_p006_api import _make_user


def _file(name, content, folder):
    doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": name,
            "content": content,
            "folder": folder,
            "is_private": 1,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert()
    return doc.name


def _subfolder(name, parent):
    doc = frappe.get_doc(
        {"doctype": "File", "file_name": name, "folder": parent, "is_folder": 1}
    )
    doc.flags.ignore_permissions = True
    doc.insert()
    return doc.name


class TestP008FolderArchiveNames(IntegrationTestCase):
    """F17d: the arcnames we hand to whoever extracts the archive."""

    def test_a_backslash_cannot_climb_out_of_the_archive(self):
        # Frappe strips `/` from `File.file_name` but not `\`, and several
        # Windows extractors treat a backslash as a separator.
        self.assertEqual(fa.arc_segment(r"..\..\evil.exe"), ".._.._evil.exe")
        self.assertEqual(fa.arc_segment("a/b"), "a_b")

    def test_a_segment_of_only_dots_cannot_climb(self):
        self.assertEqual(fa.arc_segment(".."), "__")
        self.assertEqual(fa.arc_segment("."), "_")

    def test_an_empty_name_still_produces_a_segment(self):
        self.assertEqual(fa.arc_segment(""), "unnamed")
        self.assertEqual(fa.arc_segment(None), "unnamed")


class TestP008FolderArchive(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "f17-student")
        cls.chair = _make_user("Program Chair", "f17-chair")

        # School scope so the read rule resolves without a roster: this suite is
        # about the archive, not about who may read a folder.
        cls.cf = frappe.get_doc(
            {"doctype": "Course Folder", "scope": "School", "foldername": "f17-folder"}
        )
        cls.cf.flags.ignore_permissions = True
        cls.cf.insert()
        cls.root = cls.cf.file_reference
        if not cls.root:
            cls.root = _subfolder("f17-root", "Home")
            frappe.db.set_value(
                "Course Folder", cls.cf.name, "file_reference", cls.root
            )
        _file("f17-a.txt", b"alpha", cls.root)

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")

    # ------------------------------------------------------------- the manifest
    def test_the_hash_moves_when_the_folder_changes(self):
        first, _ = fa.folder_manifest(self.root)

        added = _file("f17-b.txt", b"beta", self.root)
        second, _ = fa.folder_manifest(self.root)
        self.assertNotEqual(first, second, "adding a file must change the hash")

        frappe.db.set_value("File", added, "file_name", "f17-b-renamed.txt")
        third, _ = fa.folder_manifest(self.root)
        self.assertNotEqual(second, third, "renaming must change the hash")

        sub = _subfolder("f17-sub", self.root)
        fourth, _ = fa.folder_manifest(self.root)
        self.assertNotEqual(third, fourth, "a new subfolder must change the hash")

        frappe.delete_doc("File", sub, ignore_permissions=True, force=True)
        frappe.delete_doc("File", added, ignore_permissions=True, force=True)
        self.assertEqual(fa.folder_manifest(self.root)[0], first)

    def test_the_hash_is_stable_across_calls(self):
        self.assertEqual(
            fa.folder_manifest(self.root)[0], fa.folder_manifest(self.root)[0]
        )

    def test_a_cycle_does_not_hang_the_walk(self):
        a = _subfolder("f17-cycle-a", self.root)
        b = _subfolder("f17-cycle-b", a)
        frappe.db.set_value("File", a, "folder", b)  # a -> b -> a
        try:
            fa.folder_manifest(self.root)  # must simply return
        finally:
            frappe.db.set_value("File", a, "folder", self.root)
            frappe.delete_doc("File", b, ignore_permissions=True, force=True)
            frappe.delete_doc("File", a, ignore_permissions=True, force=True)

    def test_a_tree_of_only_empty_folders_has_nothing_to_download(self):
        """An empty subfolder is a manifest entry -- adding one must move the
        hash -- but it is not content. Counting placeholders as content built a
        126-byte zip and reported it ready (found on the potestas smoke)."""
        empty_cf = frappe.get_doc(
            {"doctype": "Course Folder", "scope": "School", "foldername": "f17-empty"}
        )
        empty_cf.flags.ignore_permissions = True
        empty_cf.insert()
        root = empty_cf.file_reference or _subfolder("f17-empty-root", "Home")
        _subfolder("f17-empty-sub", root)

        _hash, entries = fa.folder_manifest(root)
        self.assertTrue(entries, "an empty subfolder is still a manifest entry")
        self.assertFalse(fa.has_files(entries))
        self.assertIsNone(fa.build_archive(root, empty_cf.name))
        with self.assertRaises(frappe.ValidationError):
            fu.download_folder(folder_id=root)

    # ------------------------------------------------------------- the artifact
    def test_a_build_is_idempotent_and_the_artifact_is_private(self):
        first = fa.build_archive(self.root, self.cf.name)
        self.assertTrue(first)
        again = fa.build_archive(self.root, self.cf.name)
        self.assertEqual(first, again, "the same manifest must reuse the artifact")

        row = frappe.db.get_value(
            "File",
            first,
            ["is_private", "attached_to_doctype", "attached_to_name", "file_size"],
            as_dict=True,
        )
        self.assertEqual(row.is_private, 1)
        # The attachment IS the permission rule: hooks.py registers
        # course_folder.has_permission, so a File read resolves through its host
        # folder to user_may_read. Attaching to the folder's File row instead
        # would resolve through File's owner branch -- a second path.
        self.assertEqual(row.attached_to_doctype, "Course Folder")
        self.assertEqual(row.attached_to_name, self.cf.name)
        self.assertTrue(row.file_size)

    def test_the_artifact_holds_the_folder_contents(self):
        # Read through `materialize`, not `get_full_path`: on a site with object
        # storage configured the artifact has no filesystem path at all, and
        # that is the branch most deployments will be on.
        from seminary.storage.files import materialize

        name = fa.build_archive(self.root, self.cf.name)
        with materialize(name) as path:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
        self.assertTrue(any(n.endswith("f17-a.txt") for n in names), names)

    def test_the_archive_works_with_no_object_storage(self):
        """The local-disk branch is not a degraded mode -- it is what a bench
        with no object store configured runs, which includes development
        machines and any site before storage is set up. Forced here because the
        test site *does* have a backend, so this path would otherwise never run.
        """
        from seminary.storage.backend import LocalDiskBackend

        extra = _file("f17-localdisk.txt", b"eta", self.root)
        built = None
        try:
            with patch(
                "seminary.storage.get_storage_backend", return_value=LocalDiskBackend()
            ):
                built = fa.build_archive(self.root, self.cf.name)
                self.assertTrue(built)
                url = frappe.db.get_value("File", built, "file_url")
                self.assertTrue(url.startswith("/private/files/"), url)
                path = frappe.get_site_path("private", "files", url.split("/")[-1])
                self.assertTrue(os.path.exists(path), path)
                with zipfile.ZipFile(path) as zf:
                    names = zf.namelist()
                self.assertTrue(any(n.endswith("f17-localdisk.txt") for n in names))
        finally:
            if built and frappe.db.exists("File", built):
                frappe.delete_doc("File", built, ignore_permissions=True, force=True)
            frappe.delete_doc("File", extra, ignore_permissions=True, force=True)

    def test_a_newer_archive_retires_the_older_one_for_that_folder(self):
        old = fa.build_archive(self.root, self.cf.name)
        extra = _file("f17-retire.txt", b"gamma", self.root)
        try:
            new = fa.build_archive(self.root, self.cf.name)
            self.assertNotEqual(old, new)
            self.assertFalse(frappe.db.exists("File", old), "stale archive kept")
        finally:
            frappe.delete_doc("File", extra, ignore_permissions=True, force=True)

    # -------------------------------------------------------------- the endpoint
    def test_the_endpoint_never_builds_an_archive(self):
        """The whole point of F17a. A miss must queue work, not do it."""
        extra = _file("f17-nobuild.txt", b"delta", self.root)
        try:
            frappe.set_user(self.student)
            with patch.object(
                fa, "build_archive", side_effect=AssertionError("built in-request")
            ):
                with patch.object(frappe, "enqueue") as enqueued:
                    result = fu.download_folder(folder_id=self.root)
            self.assertEqual(result["status"], "preparing")
            self.assertTrue(enqueued.called)
        finally:
            frappe.set_user("Administrator")
            frappe.delete_doc("File", extra, ignore_permissions=True, force=True)

    def test_a_ready_archive_comes_back_as_a_url(self):
        fa.build_archive(self.root, self.cf.name)
        frappe.set_user(self.student)
        result = fu.download_folder(folder_id=self.root)
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["url"])

    def test_a_reader_cannot_queue_build_after_build(self):
        extra = _file("f17-ratelimit.txt", b"epsilon", self.root)
        try:
            frappe.cache.delete_value(f"seminary_folder_archive_user:{self.student}")
            frappe.set_user(self.student)
            with patch.object(frappe, "enqueue"):
                first = fu.download_folder(folder_id=self.root)
                second = fu.download_folder(folder_id=self.root)
            self.assertEqual(first["detail"], "queued")
            self.assertEqual(second["detail"], "rate-limited")
        finally:
            frappe.set_user("Administrator")
            frappe.cache.delete_value(f"seminary_folder_archive_user:{self.student}")
            frappe.delete_doc("File", extra, ignore_permissions=True, force=True)

    def test_a_folder_outside_a_course_folder_has_no_archive(self):
        loose = _subfolder("f17-loose", "Home")
        _file("f17-loose.txt", b"zeta", loose)
        with self.assertRaises(frappe.ValidationError):
            fu.download_folder(folder_id=loose)
