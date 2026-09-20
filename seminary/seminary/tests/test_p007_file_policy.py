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
        fields.setdefault("file_name", f"zzt-p007-{frappe.generate_hash(length=6)}.txt")
        doc = frappe.get_doc(
            {
                "doctype": "File",
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
            "File", {"file_name": ["like", "zzt-p007%"]}, pluck="name"
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

            # p008 F15: claiming `attached_to_field` is no longer enough. The
            # claim is client-supplied and Frappe never checks it against the
            # host, so a File whose host does not actually carry the URL has no
            # registered field and cannot be public. This assertion used to be
            # `assertTrue` on the strength of the claim alone -- which was the
            # publish primitive.
            self.assertFalse(
                file_policy.may_be_public(doc),
                "an unconfirmed attached_to_field must not publish",
            )

            # Once the host really holds the URL, the predicate decides.
            hero_was = frappe.db.get_value("Program", program, "hero_image")
            frappe.db.set_value("Program", program, "hero_image", doc.file_url)
            try:
                self.assertTrue(file_policy.may_be_public(doc))
                frappe.db.set_value("Program", program, "published", 0)
                self.assertFalse(file_policy.may_be_public(doc))
                frappe.db.set_value("Program", program, "published", 1)
            finally:
                frappe.db.set_value("Program", program, "hero_image", hero_was)

            key = ("Course", "hero_image")
            self.assertFalse(file_policy._registered(*key)[0])
            file_policy.PUBLIC_FILE_FIELDS[key] = None
            try:
                self.assertEqual(file_policy._registered(*key), (True, None))
            finally:
                file_policy.PUBLIC_FILE_FIELDS.pop(key)
        finally:
            frappe.db.set_value("Program", program, "published", was)

    def test_a_named_fieldname_on_a_wildcard_host_cannot_publish(self):
        """p008 F15 / p005a A02-6.

        `PUBLIC_FILE_FIELDS` used to carry `(doctype, "*")` rows for Website
        Branding, Seminary Settings and Letter Head. Combined with
        `_attached_field` trusting the uploader's `attached_to_field`, that made
        `upload_file(is_private=0, doctype="Seminary Settings", fieldname=<anything>)`
        a publish primitive: the wildcard matched and the file landed
        world-readable in /files/. nginx forces an attachment for .html and .svg,
        so the sharp edge was .xhtml, .svgz and .mhtml.
        """
        for doctype in ("Seminary Settings", "Website Branding", "Letter Head"):
            with self.subTest(doctype=doctype):
                self.assertFalse(
                    file_policy._registered(doctype, "anything_i_name")[0],
                    "a fieldname nobody registered must not match",
                )
        self.assertEqual(
            [k for k in file_policy.PUBLIC_FILE_FIELDS if k[1] == "*"],
            [],
            "no wildcard rows may remain in the registry",
        )

    def test_a_registered_field_still_publishes_once_the_host_holds_it(self):
        """The other half: F15 must not cost the feature. A logo really set on
        Seminary Settings is still public."""
        self.assertTrue(file_policy._registered("Seminary Settings", "logo_portal")[0])
        self.assertTrue(file_policy._registered("Website Branding", "favicon")[0])
        self.assertTrue(file_policy._registered("Letter Head", "image")[0])

    def test_naming_someone_elses_private_file_in_an_attach_field_is_refused(self):
        """p008 F16 / p005a A02-8.

        Frappe's `attach_files_to_document` binds any *unattached* File matching
        the URL to the caller's document with no permission check. Since p007
        made loose private uploads the norm, guessing one and putting it in an
        Attach field was a way to gain read on it -- the file policy reads
        through the host, so attaching it to your own submission is enough.
        """
        from seminary.seminary import file_policy as fp

        owner, stranger = self.web_user, self.other_user

        theirs = _file(owner, is_private=1)  # loose: attached to nothing
        self.assertFalse(theirs.attached_to_doctype)

        frappe.set_user(stranger)
        try:
            rows = fp._rows_for(theirs.file_url)
            self.assertTrue(rows)
            self.assertFalse(
                fp._may_adopt(rows, None),
                "a stranger must not be allowed to adopt a loose private file",
            )
        finally:
            frappe.set_user("Administrator")

        # ...and the owner still may.
        frappe.set_user(owner)
        try:
            self.assertTrue(fp._may_adopt(fp._rows_for(theirs.file_url), None))
        finally:
            frappe.set_user("Administrator")

    def test_the_attach_guard_actually_throws(self):
        """Not just that the rule says no -- that the hook refuses the save."""
        from seminary.seminary import file_policy as fp

        owner, stranger = self.web_user, self.other_user
        theirs = _file(owner, is_private=1)

        doc = frappe.new_doc("Withdrawal Request")
        doc.student_documentation = theirs.file_url

        frappe.set_user(stranger)
        try:
            with self.assertRaises(frappe.PermissionError):
                fp.guard_attach_fields(doc)
        finally:
            frappe.set_user("Administrator")

        # The owner of the file is not obstructed.
        frappe.set_user(owner)
        try:
            fp.guard_attach_fields(doc)  # must not raise
        finally:
            frappe.set_user("Administrator")

    def test_the_attach_guard_ignores_a_value_that_names_no_file(self):
        """A URL with no File row is left to Frappe, which creates one."""
        from seminary.seminary import file_policy as fp

        doc = frappe.new_doc("Withdrawal Request")
        doc.student_documentation = "/private/files/zzz-no-such-file-f16.pdf"
        frappe.set_user(self.other_user)
        try:
            fp.guard_attach_fields(doc)  # must not raise
        finally:
            frappe.set_user("Administrator")

    def test_the_attach_guard_is_registered_before_frappes_attach_step(self):
        hooks = frappe.get_hooks("doc_events") or {}
        validate = (hooks.get("*", {}) or {}).get("validate") or []
        if isinstance(validate, str):
            validate = [validate]
        self.assertIn(
            "seminary.seminary.file_policy.guard_attach_fields",
            validate,
            "must run at validate: on_update is too late to refuse the binding",
        )

    def test_an_offloaded_attach_value_is_recognised_as_a_file_url(self):
        """Frappe's attach step tests `startswith(('/files', '/private/files'))`,
        so an offloaded URL never matched and the file was never attached --
        owner-only, and the grader got a 403."""
        from seminary.seminary import file_policy as fp
        from seminary.storage.backend import url_for_key, object_key

        url = url_for_key(object_key("a" * 32))
        self.assertTrue(fp._is_file_url(url))
        self.assertFalse(url.startswith(("/files", "/private/files")))

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

    def test_images_pasted_into_a_registered_rich_text_field_follow_the_host(self):
        program = frappe.get_all("Program", pluck="name", limit=1)
        if not program:
            self.skipTest("no Program on the test site")
        program = program[0]
        was = frappe.db.get_value(
            "Program", program, ["published", "program_description"], as_dict=True
        )
        mine = _file(
            is_private=1, attached_to_doctype="Program", attached_to_name=program
        )
        foreign = _file(
            is_private=1, attached_to_doctype="Student", attached_to_name=self.stu
        )
        html = (
            f'<p><img src="{mine.file_url}?fid={mine.name}">'
            f'<img src="{foreign.file_url}"></p>'
        )
        try:
            frappe.db.set_value(
                "Program", program, {"program_description": html, "published": 1}
            )
            file_policy.sync_public_state("Program", program)
            frappe.db.commit()
            stored = frappe.db.get_value("Program", program, "program_description")
            public_url = mine.file_url.replace("/private/files/", "/files/")
            self.assertIn(f'src="{public_url}"', stored)
            # a private file that hangs elsewhere is not published by mention
            self.assertIn(foreign.file_url, stored)
            self.assertEqual(frappe.db.get_value("File", foreign.name, "is_private"), 1)

            frappe.db.set_value("Program", program, "published", 0)
            file_policy.sync_public_state("Program", program)
            frappe.db.commit()
            stored = frappe.db.get_value("Program", program, "program_description")
            self.assertIn(mine.file_url, stored)
        finally:
            frappe.db.set_value(
                "Program",
                program,
                {
                    "published": was.published,
                    "program_description": was.program_description,
                },
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

    def test_find_urls_reads_names_with_spaces(self):
        name = "/private/files/philosophical foundations research ethics.pdf"
        blocks = '{"blocks":[{"type":"upload","data":{"file_url":"%s"}}]}' % name
        self.assertEqual(file_policy.find_urls(blocks), {name})
        html_ = '<p><img src="/files/Team Photo 2026.jpg?x=1"> and <a href="/private/files/a%20b.pdf">x</a></p>'
        self.assertEqual(
            file_policy.find_urls(html_),
            {"/files/Team Photo 2026.jpg?x=1", "/private/files/a%20b.pdf"},
        )
        self.assertEqual(
            file_policy._lookup_url("/private/files/a%20b.pdf?fid=abc"),
            "/private/files/a b.pdf",
        )
        self.assertEqual(
            file_policy.find_urls("{{ Video('/files/My Lecture 1.mp4') }}"),
            {"/files/My Lecture 1.mp4"},
        )

    def test_lesson_content_adopts_a_file_whose_name_has_spaces(self):
        doc = _file(
            is_private=1,
            file_name=f"zzt-p007 with spaces {frappe.generate_hash(length=5)}.txt",
        )
        self.assertIn(" ", doc.file_url)
        file_policy.adopt_embedded(self._lesson_like(doc.file_url, self.cs.name))
        self.assertEqual(
            frappe.db.get_value("File", doc.name, "attached_to_name"), self.cs.name
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
