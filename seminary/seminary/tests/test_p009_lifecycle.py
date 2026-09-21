# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p009 S9: SCOs become lessons, and a package's objects go when nothing holds it.

The rule these tests exist to defend: **a lesson is never deleted by a
re-upload.** Deleting one takes its Course Schedule Progress rows with it, and
no instructor's replacement package may silently erase a cohort's work.
"""

import io
import zipfile
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.scorm import lessons, lifecycle
from seminary.seminary.tests.test_p009_explode import FakeBackend

MANIFEST_HEAD = """<?xml version="1.0"?>
<manifest identifier="M" xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
  <metadata><schemaversion>1.2</schemaversion></metadata>
  <organizations default="O"><organization identifier="O"><title>Course</title>
"""
MANIFEST_TAIL = """  </organization></organizations>
  <resources>{resources}</resources>
</manifest>"""


def _manifest(scos):
    """`scos` is [(identifier, title, href)]."""
    items = "".join(
        f'<item identifier="{i}" identifierref="R{i}"><title>{t}</title></item>'
        for i, t, _ in scos
    )
    resources = "".join(
        f'<resource identifier="R{i}" adlcp:scormtype="sco" href="{h}"/>'
        for i, _, h in scos
    )
    return MANIFEST_HEAD + items + MANIFEST_TAIL.format(resources=resources)


def _zip(scos, extra=None, nonce=None):
    """`nonce` makes two otherwise identical packages distinct.

    The unpack job dedups on the zip's SHA-256 and commits as it goes -- it is a
    background job, so it must -- which means packages persist across tests in a
    class. Tests that are not about dedup pass a nonce; the one that is passes
    none, deliberately.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("imsmanifest.xml", _manifest(scos))
        for _, _, href in scos:
            zf.writestr(href, f"<h1>{href}</h1>")
        for name, content in (extra or {}).items():
            zf.writestr(name, content)
        if nonce:
            zf.writestr("nonce.txt", nonce)
    return buf.getvalue()


class _ScormCase(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        # The job commits, so rows survive the per-test rollback. Start clean, or
        # the SHA-256 dedup matches a package a previous test left behind.
        for name in frappe.get_all("SCORM Package", pluck="name"):
            frappe.db.set_value(
                "Course Schedule Chapter",
                {"scorm_package_ref": name},
                "scorm_package_ref",
                None,
            )
            frappe.delete_doc(
                "SCORM Package", name, ignore_permissions=True, force=True
            )
        frappe.db.commit()
        self.backend = FakeBackend()
        patcher = patch(
            "seminary.storage.backend.get_storage_backend", return_value=self.backend
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _chapter(self, title="SCORM chapter"):
        chapter = frappe.new_doc("Course Schedule Chapter")
        chapter.chapter_title = title
        chapter.is_scorm_package = 1
        chapter.flags.ignore_mandatory = True
        chapter.flags.ignore_permissions = True
        chapter.insert()
        return chapter

    def _unpack(self, chapter, payload):
        from seminary.scorm import explode

        f = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": f"pkg-{frappe.generate_hash(length=8)}.zip",
                "content": payload,
                "is_private": 1,
            }
        )
        f.flags.ignore_permissions = True
        f.insert()
        package = frappe.get_doc(
            {"doctype": "SCORM Package", "source_file": f.name, "status": "Pending"}
        )
        package.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Course Schedule Chapter", chapter.name, "scorm_package_ref", package.name
        )
        explode.explode_package(chapter.name, package.name)
        return package.name

    def _lessons(self, chapter):
        return frappe.get_all(
            "Course Lesson",
            filters={"chapter": chapter.name},
            fields=["name", "lesson_title", "scorm_sco_identifier", "scorm_orphaned"],
            order_by="creation asc",
        )


class TestP009Lessons(_ScormCase):
    def test_one_lesson_per_sco_in_manifest_order(self):
        chapter = self._chapter()
        self._unpack(
            chapter,
            _zip([("A", "First", "a.html"), ("B", "Second", "b.html")], nonce="1"),
        )

        rows = self._lessons(chapter)
        self.assertEqual([r.scorm_sco_identifier for r in rows], ["A", "B"])
        self.assertEqual([r.lesson_title for r in rows], ["First", "Second"])

        refs = frappe.get_all(
            "Course Schedule Lesson Reference",
            filters={"parent": chapter.name},
            fields=["lesson", "idx"],
            order_by="idx asc",
        )
        self.assertEqual([r.lesson for r in refs], [rows[0].name, rows[1].name])

    def test_a_single_sco_package_is_an_ordinary_one_lesson_chapter(self):
        chapter = self._chapter()
        self._unpack(chapter, _zip([("ONLY", "The lesson", "index.html")], nonce="1"))
        self.assertEqual(len(self._lessons(chapter)), 1)

    def test_a_reupload_keeps_lessons_and_orphans_the_departed(self):
        chapter = self._chapter()
        self._unpack(
            chapter,
            _zip([("A", "First", "a.html"), ("B", "Second", "b.html")], nonce="1"),
        )
        before = {r.scorm_sco_identifier: r.name for r in self._lessons(chapter)}

        # B is gone, C is new, A is retitled.
        self._unpack(
            chapter,
            _zip(
                [("A", "First, revised", "a.html"), ("C", "Third", "c.html")], nonce="2"
            ),
        )

        rows = {r.scorm_sco_identifier: r for r in self._lessons(chapter)}
        self.assertEqual(set(rows), {"A", "B", "C"})
        # Same row, not a replacement: its progress rows point at this name.
        self.assertEqual(rows["A"].name, before["A"])
        self.assertEqual(rows["A"].lesson_title, "First, revised")
        self.assertEqual(rows["B"].name, before["B"])
        self.assertEqual(
            rows["B"].scorm_orphaned, 1, "a departed SCO must not be deleted"
        )
        self.assertEqual(rows["C"].scorm_orphaned, 0)

    def test_a_restored_sco_un_orphans_its_lesson(self):
        chapter = self._chapter()
        pack = _zip([("A", "First", "a.html")], nonce="1")
        self._unpack(chapter, pack)
        original = self._lessons(chapter)[0].name

        self._unpack(chapter, _zip([("B", "Other", "b.html")], nonce="2"))
        self.assertEqual(
            frappe.db.get_value("Course Lesson", original, "scorm_orphaned"), 1
        )

        self._unpack(chapter, pack)
        self.assertEqual(
            frappe.db.get_value("Course Lesson", original, "scorm_orphaned"), 0
        )

    def test_the_legacy_placeholder_is_claimed_not_duplicated(self):
        # Chapters made between p008 F8 and p009 carry one lesson with no SCO
        # identifier. Claiming it keeps whatever progress it already has.
        chapter = self._chapter()
        placeholder = frappe.new_doc("Course Lesson")
        placeholder.update({"lesson_title": "SCORM chapter", "chapter": chapter.name})
        placeholder.flags.ignore_mandatory = True
        placeholder.flags.ignore_permissions = True
        placeholder.insert()

        self._unpack(chapter, _zip([("A", "First", "a.html")], nonce="1"))

        rows = self._lessons(chapter)
        self.assertEqual(len(rows), 1, "the placeholder was duplicated")
        self.assertEqual(rows[0].name, placeholder.name)
        self.assertEqual(rows[0].scorm_sco_identifier, "A")


class TestP009PackageLifecycle(_ScormCase):
    def test_objects_go_when_the_last_chapter_does(self):
        first = self._chapter("one")
        payload = _zip([("A", "First", "a.html")])  # no nonce: dedup is the point
        package = self._unpack(first, payload)
        self.assertTrue(self.backend.objects)

        # A second chapter adopts the same package: same bytes, same hash.
        second = self._chapter("two")
        self._unpack(second, payload)
        self.assertEqual(
            frappe.db.get_value(
                "Course Schedule Chapter", second.name, "scorm_package_ref"
            ),
            package,
        )

        # One chapter goes: the package stays, because the other still holds it.
        self.assertFalse(lifecycle.release(package, exclude_chapter=first.name))
        self.assertTrue(frappe.db.exists("SCORM Package", package))
        self.assertTrue(self.backend.objects)

        frappe.db.set_value(
            "Course Schedule Chapter", first.name, "scorm_package_ref", None
        )
        frappe.db.set_value(
            "Course Schedule Chapter", second.name, "scorm_package_ref", None
        )
        self.assertTrue(lifecycle.release(package))
        self.assertFalse(frappe.db.exists("SCORM Package", package))
        self.assertEqual(self.backend.objects, {}, "objects outlived their package")

    def test_deleting_the_row_takes_the_objects(self):
        chapter = self._chapter()
        package = self._unpack(chapter, _zip([("A", "First", "a.html")], nonce="1"))
        self.assertTrue(self.backend.objects)
        frappe.delete_doc("SCORM Package", package, ignore_permissions=True, force=True)
        self.assertEqual(self.backend.objects, {})

    def test_only_this_packages_prefix_is_deleted(self):
        keeper = self._chapter("keeper")
        kept = self._unpack(keeper, _zip([("A", "Keep", "a.html")], nonce="1"))
        kept_keys = set(self.backend.objects)

        goer = self._chapter("goer")
        doomed = self._unpack(goer, _zip([("B", "Go", "b.html")], nonce="2"))
        self.assertNotEqual(kept, doomed)

        lifecycle.delete_objects(doomed)
        self.assertEqual(set(self.backend.objects), kept_keys)

    def test_the_sweep_removes_an_unclaimed_prefix_and_nothing_else(self):
        chapter = self._chapter()
        package = self._unpack(chapter, _zip([("A", "First", "a.html")], nonce="1"))
        live = set(self.backend.objects)

        # An unpack that died before its row was committed.
        self.backend.objects["scorm/deadbeef/index.html"] = (b"x", "text/html")

        def list_keys(prefix):
            return [
                {"key": k, "size": 1, "last_modified": "2020-01-01 00:00:00"}
                for k in self.backend.objects
                if k.startswith(prefix)
            ]

        self.backend.list_keys = list_keys
        lifecycle.sweep_orphaned_packages()

        self.assertEqual(set(self.backend.objects), live)
        self.assertTrue(frappe.db.exists("SCORM Package", package))

    def test_the_sweep_spares_a_prefix_that_may_still_be_uploading(self):
        self.backend.objects["scorm/inflight/index.html"] = (b"x", "text/html")
        self.backend.list_keys = lambda prefix: [
            {"key": k, "size": 1, "last_modified": frappe.utils.now_datetime()}
            for k in self.backend.objects
            if k.startswith(prefix)
        ]
        lifecycle.sweep_orphaned_packages()
        self.assertIn("scorm/inflight/index.html", self.backend.objects)
