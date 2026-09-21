# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p009 S2/S3: a package is unpacked into object storage, or refused (§2.4-2.5).

The inventory these tests assert on is the security control of the whole
feature: delivery answers only for a path that is a key of it. So the refusals
below are not edge cases, they are the contract -- a member path that reaches
the inventory is a path delivery will serve.
"""

import hashlib
import io
import zipfile
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.scorm import archive, explode
from seminary.scorm.archive import PackageError

MANIFEST = """<?xml version="1.0"?>
<manifest identifier="M" xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
  <metadata><schemaversion>1.2</schemaversion></metadata>
  <organizations default="O"><organization identifier="O">
    <title>Course</title>
    <item identifier="I1" identifierref="R1"><title>First</title></item>
  </organization></organizations>
  <resources>
    <resource identifier="R1" adlcp:scormtype="sco" href="index.html"/>
  </resources>
</manifest>"""


class FakeBackend:
    """An object store in a dict. Only the methods explode actually uses."""

    def __init__(self):
        self.objects = {}

    def is_configured(self):
        return True

    def put_fileobj(self, key, fileobj, content_type=None):
        self.objects[key] = (fileobj.read(), content_type)

    def delete(self, key):
        self.objects.pop(key, None)

    def stream(self, key, chunk_size=1024 * 1024):
        blob = self.objects[key][0]
        for i in range(0, len(blob), chunk_size):
            yield blob[i : i + chunk_size]

    def presigned_get(
        self, key, ttl=None, file_name=None, content_type=None, as_attachment=False
    ):
        return f"https://objectstore.invalid/{key}?sig=fake&ttl={ttl}"

    def list_keys(self, prefix):
        return [
            {"key": k, "size": len(v[0]), "last_modified": "2020-01-01 00:00:00"}
            for k, v in self.objects.items()
            if k.startswith(prefix)
        ]


def _zip(members, prefix="", manifest=MANIFEST):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if manifest is not None:
            zf.writestr(f"{prefix}imsmanifest.xml", manifest)
        for name, content in members.items():
            zf.writestr(f"{prefix}{name}", content)
    return buf.getvalue()


class TestP009Explode(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.backend = FakeBackend()
        self.patcher = patch(
            "seminary.storage.backend.get_storage_backend", return_value=self.backend
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    # ------------------------------------------------------------- helpers

    def _package(self, payload):
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
        return package

    def _explode(self, payload, chapter="ZZT-chapter"):
        package = self._package(payload)
        explode.explode_package(chapter, package.name)
        return frappe.get_doc("SCORM Package", package.name)

    def _refuses(self, payload, because=""):
        package = self._explode(payload)
        self.assertEqual(package.status, "Failed", package.failure_reason)
        if because:
            self.assertIn(because, (package.failure_reason or "").lower())
        self.assertEqual(self.backend.objects, {}, "objects survived a refusal")
        return package

    # ------------------------------------------------------- the happy path

    def test_a_package_is_unpacked_and_inventoried(self):
        package = self._explode(
            _zip({"index.html": "<h1>hi</h1>", "img/logo.png": b"\x89PNG"})
        )
        self.assertEqual(package.status, "Ready", package.failure_reason)
        self.assertEqual(package.scorm_version, "1.2")
        self.assertEqual(package.default_organization, "O")

        inventory = package.get_inventory()
        self.assertEqual(
            sorted(inventory), ["img/logo.png", "imsmanifest.xml", "index.html"]
        )
        self.assertEqual(
            inventory["index.html"]["content_type"], "text/html; charset=utf-8"
        )
        self.assertEqual(inventory["img/logo.png"]["content_type"], "image/png")
        self.assertEqual(
            inventory["index.html"]["sha256"],
            hashlib.sha256(b"<h1>hi</h1>").hexdigest(),
        )

        # Every key is inside this package's own prefix, and the prefix is the
        # random id -- never anything derived from the content.
        for key in self.backend.objects:
            self.assertTrue(key.startswith(f"scorm/{package.package_id}/"), key)

        self.assertEqual([i.sco_identifier for i in package.items], ["I1"])
        self.assertEqual(package.items[0].href, "index.html")

    def test_a_nested_manifest_defines_the_package_root(self):
        # Zipping the containing folder is a common mistake; the inventory is
        # keyed relative to the manifest so the package addresses itself the
        # same way either way.
        package = self._explode(_zip({"index.html": "x"}, prefix="MyCourse/"))
        self.assertEqual(package.status, "Ready", package.failure_reason)
        self.assertEqual(
            sorted(package.get_inventory()), ["imsmanifest.xml", "index.html"]
        )

    def test_desktop_junk_is_skipped_not_refused(self):
        package = self._explode(
            _zip({"index.html": "x", "__MACOSX/._index.html": "junk"})
        )
        self.assertEqual(package.status, "Ready", package.failure_reason)
        self.assertNotIn("__MACOSX/._index.html", package.get_inventory())

    # ------------------------------------------------------------ refusals

    def test_a_traversing_member_is_refused(self):
        self._refuses(_zip({"index.html": "x", "../escape.html": "x"}), "climbs out")

    def test_an_absolute_member_is_refused(self):
        self._refuses(_zip({"index.html": "x", "/etc/passwd": "x"}), "absolute")

    def test_a_drive_letter_is_refused(self):
        self._refuses(_zip({"index.html": "x", "C:/windows/x.dll": "x"}), "absolute")

    def test_a_backslash_member_is_normalised_not_escaped(self):
        # Frappe strips `/` from a file name but not `\`, and several Windows
        # extractors treat `..\` as traversal (p008 F17d, the export-side twin).
        self._refuses(_zip({"index.html": "x", "..\\escape.html": "x"}), "climbs out")

    def test_a_control_character_is_refused(self):
        self._refuses(
            _zip({"index.html": "x", "a\x01b.html": "x"}), "control characters"
        )

    def test_a_trailing_dot_is_refused(self):
        # Windows trims these silently, so `a.html.` and `a.html` collide on
        # extraction -- a collision the archive does not admit to.
        self._refuses(_zip({"index.html": "x", "a.html.": "x"}), "dot or space")

    def test_a_case_collision_is_refused(self):
        self._refuses(_zip({"index.html": "x", "Index.HTML": "y"}), "differ only")

    def test_a_unicode_normalisation_collision_is_refused(self):
        self._refuses(
            _zip({"index.html": "x", "caf\u00e9.html": "a", "cafe\u0301.html": "b"}),
            "differ only",
        )

    def test_a_symlink_is_refused(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("imsmanifest.xml", MANIFEST)
            zf.writestr("index.html", "x")
            info = zipfile.ZipInfo("link.html")
            info.external_attr = 0o120777 << 16
            zf.writestr(info, "/etc/passwd")
        self._refuses(buf.getvalue(), "symbolic link")

    def test_a_bomb_trips_the_ratio(self):
        self._refuses(
            _zip({"index.html": "x", "bomb.bin": b"\0" * (200 * 1024 * 1024)}),
            "does not look like",
        )

    def test_an_oversize_member_trips_the_cap(self):
        with patch.dict(frappe.conf, {"scorm_max_member_bytes": 16}):
            self._refuses(_zip({"index.html": "x" * 64}), "too large")

    def test_an_oversize_text_member_is_refused_at_unpack(self):
        # Refused here rather than at serve time: a proxied member is streamed
        # through a worker, and the instructor is who can fix it.
        with patch.dict(frappe.conf, {"scorm_proxy_member_max_bytes": 16}):
            self._refuses(_zip({"index.html": "x" * 64}), "text file that is too large")

    def test_a_non_zip_is_refused(self):
        self._refuses(b"not a zip at all", "not a zip archive")

    def test_a_zip_without_a_manifest_is_refused(self):
        self._refuses(_zip({"index.html": "x"}, manifest=None), "imsmanifest")

    def test_a_manifest_naming_a_missing_file_is_refused(self):
        self._refuses(_zip({"other.html": "x"}), "does not contain")

    def test_an_xxe_manifest_is_refused(self):
        hostile = (
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE m [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>\n'
            "<manifest><organizations><organization><title>&xxe;</title>"
            "</organization></organizations></manifest>"
        )
        self._refuses(_zip({"index.html": "x"}, manifest=hostile), "not allowed")

    def test_a_failed_unpack_leaves_no_objects_and_no_ready_row(self):
        package = self._refuses(_zip({"index.html": "x", "../escape.html": "x"}))
        self.assertEqual(package.status, "Failed")
        self.assertFalse(package.inventory)
        self.assertEqual(self.backend.objects, {})

    def test_no_object_storage_means_no_unpack_and_no_disk_tree(self):
        class Unconfigured(FakeBackend):
            def is_configured(self):
                return False

        self.backend = Unconfigured()
        self.patcher.stop()
        with patch(
            "seminary.storage.backend.get_storage_backend", return_value=self.backend
        ):
            package = self._explode(_zip({"index.html": "x"}))
        self.patcher.start()
        self.assertEqual(package.status, "Failed")
        self.assertIn("object storage", package.failure_reason)

    # --------------------------------------------------------------- dedup

    def test_the_same_bytes_explode_once(self):
        payload = _zip({"index.html": "x"})
        first = self._explode(payload)
        self.assertEqual(first.status, "Ready", first.failure_reason)

        chapter = frappe.new_doc("Course Schedule Chapter")
        chapter.chapter_title = "shared"
        chapter.flags.ignore_mandatory = True
        chapter.insert(ignore_permissions=True)

        second = self._package(payload)
        explode.explode_package(chapter.name, second.name)

        self.assertFalse(frappe.db.exists("SCORM Package", second.name))
        self.assertEqual(
            frappe.db.get_value(
                "Course Schedule Chapter", chapter.name, "scorm_package_ref"
            ),
            first.name,
        )


class TestP009MemberPaths(IntegrationTestCase):
    """The path rules on their own, where the failure message is the assertion."""

    def test_normalisation_spells_one_path_one_way(self):
        self.assertEqual(archive.normalise_member_path("a\\b//c.html"), "a/b/c.html")
        self.assertEqual(archive.normalise_member_path("./a/./b.html"), "a/b.html")

    def test_dot_dot_is_rejected_not_resolved(self):
        # Rejected, never resolved away: a package that needs its paths repaired
        # is a package we do not understand.
        for bad in ("../x", "a/../../x", "..", "a/.."):
            with self.subTest(bad=bad), self.assertRaises(PackageError):
                archive.normalise_member_path(bad)

    def test_an_over_long_path_is_rejected(self):
        with self.assertRaises(PackageError):
            archive.normalise_member_path("a/" * 600 + "x.html")  # > 1000 bytes

    def test_content_types_come_from_the_table_not_the_host(self):
        self.assertEqual(
            archive.content_type_for("a/b.HTML"), "text/html; charset=utf-8"
        )
        self.assertEqual(
            archive.content_type_for("a/b.unknown"), "application/octet-stream"
        )
        self.assertEqual(
            archive.content_type_for("noextension"), "application/octet-stream"
        )

    def test_reference_carrying_types_are_proxied(self):
        for proxied in ("a.html", "a.css", "a.js", "a.svg", "a.json"):
            self.assertTrue(archive.is_proxied(proxied), proxied)
        for redirected in ("a.mp4", "a.png", "a.pdf", "a.bin"):
            self.assertFalse(archive.is_proxied(redirected), redirected)

    def test_fonts_are_proxied_even_though_they_reference_nothing(self):
        """The one entry that is not about relative references. A cross-origin
        `@font-face` is a CORS-checked fetch and a presigned URL carries no
        CORS headers, so a redirected font is refused unless the bucket has a
        policy naming the delivery host -- infrastructure per deployment, which
        §3 refused to depend on. Fonts are small and few; the redirect exists to
        keep lecture video off the worker pool, not these."""
        for font in ("a.woff", "a.woff2", "a.ttf", "a.otf", "a.eot"):
            self.assertTrue(archive.is_proxied(font), font)


#: One resource, three items, differing only by `parameters`. This is the ADL
#: Golf sample's shape for its four tests, and the shape that broke on the first
#: browser pass.
SHARED_RESOURCE_MANIFEST = """<?xml version="1.0"?>
<manifest identifier="M" xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
  <metadata><schemaversion>1.2</schemaversion></metadata>
  <organizations default="O"><organization identifier="O">
    <title>Course</title>
    <item identifier="plain" identifierref="R1"><title>Plain</title></item>
    <item identifier="t1" identifierref="R1" parameters="?content=one">
      <title>Test One</title></item>
    <item identifier="t2" identifierref="R1" parameters="?content=two">
      <title>Test Two</title></item>
    <item identifier="frag" identifierref="R2" parameters="#section3">
      <title>Fragment</title></item>
    <item identifier="both" identifierref="R2" parameters="?b=2">
      <title>Both queries</title></item>
  </organization></organizations>
  <resources>
    <resource identifier="R1" adlcp:scormtype="sco" href="shared/page.html"/>
    <resource identifier="R2" adlcp:scormtype="sco" href="shared/page.html?a=1"/>
  </resources>
</manifest>"""


class TestP009ItemParameters(IntegrationTestCase):
    """`<item parameters>` is how one resource serves several SCOs.

    SCORM puts `href` on the `<resource>` and `parameters` on the `<item>`, and
    requires the LMS to append the second to the first. Ignoring it launches
    one page for every test in the ADL Golf sample, and the package's own
    script then cannot tell which test it is showing -- it throws on an
    undefined `pageArray`. Found in a browser, because a manifest that parses
    cleanly and a package that cannot run look identical from the server.
    """

    def _scos(self, manifest=SHARED_RESOURCE_MANIFEST):
        from seminary.scorm import manifest as manifest_module

        inventory = {"shared/page.html": {}, "imsmanifest.xml": {}}
        parsed = manifest_module.parse(manifest.encode(), inventory, max_scos=50)
        return {sco.identifier: sco for sco in parsed.scos}

    def test_items_sharing_a_resource_get_distinct_launch_urls(self):
        scos = self._scos()
        self.assertEqual(scos["t1"].href, "shared/page.html")
        self.assertEqual(scos["t2"].href, "shared/page.html")
        self.assertNotEqual(scos["t1"].suffix, scos["t2"].suffix)
        self.assertEqual(scos["t1"].suffix, "?content=one")
        self.assertEqual(scos["t2"].suffix, "?content=two")

    def test_an_item_without_parameters_is_unchanged(self):
        self.assertEqual(self._scos()["plain"].suffix, "")

    def test_the_inventory_path_never_carries_the_parameters(self):
        """The suffix is for the launch URL only. If it reached the inventory
        lookup, a package could address a member that does not exist."""
        for sco in self._scos().values():
            self.assertNotIn("?", sco.href)
            self.assertNotIn("#", sco.href)

    def test_two_queries_are_joined_with_an_ampersand(self):
        # The resource already has `?a=1`; a second `?` would be a broken URL.
        self.assertEqual(self._scos()["both"].suffix, "?a=1&b=2")

    def test_a_fragment_parameter_keeps_the_resource_query(self):
        self.assertEqual(self._scos()["frag"].suffix, "?a=1#section3")

    def test_an_over_long_parameters_value_is_refused(self):
        from seminary.scorm.manifest import ManifestError

        manifest = SHARED_RESOURCE_MANIFEST.replace(
            'parameters="?content=one"', 'parameters="?%s"' % ("x" * 500)
        )
        with self.assertRaises(ManifestError):
            self._scos(manifest)
