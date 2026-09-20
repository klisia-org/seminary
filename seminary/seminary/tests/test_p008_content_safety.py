# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008 F4 / F6 / F7, server side: the HTML policy, the URL policy and the
EditorJS block sanitiser. Pure functions -- no fixtures."""

import json

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import content_safety
from seminary.seminary.content_safety import clean_code, clean_rich
from seminary.seminary.editorjs_safety import sanitize_content
from seminary.seminary.url_policy import is_safe_url, safe_embed_url

HEBREW = "בְּרֵאשִׁית"
GREEK = "Ἐν ἀρχῇ ἦν ὁ λόγος"


class TestCleanRich(IntegrationTestCase):
    def test_attacks_do_not_survive(self):
        cases = {
            "script": ("<script>alert(1)</script>x", ("<script", "alert")),
            "handler": ("<img src=x onerror=alert(1)>", ("onerror",)),
            "p005 pre-parse bypass": (
                "<!--><img src=x onerror=alert(1)>-->",
                ("onerror",),
            ),
            "credential form": (
                '<form action="//evil"><input name=u><button>Login</button></form>',
                ("<form", "<input", "<button"),
            ),
            "fixed overlay": (
                '<div style="position:fixed;top:0;left:0;z-index:9;width:100%">x</div>',
                ("position", "z-index", "top:", "left:"),
            ),
            "inset overlay": (
                '<div style="position:absolute;inset:0">x</div>',
                ("inset", "position"),
            ),
            "style element": ("<style>body{display:none}</style>x", ("<style",)),
            "iframe": ('<iframe src="https://evil"></iframe>', ("<iframe",)),
            "javascript href": (
                '<a href="javascript:alert(1)">x</a>',
                ("javascript:",),
            ),
            "base": ('<base href="https://evil/">x', ("<base",)),
            "meta": (
                '<meta http-equiv="refresh" content="0;url=https://evil">x',
                ("<meta",),
            ),
        }
        for label, (html, banned) in cases.items():
            out = clean_rich(html)
            for needle in banned:
                with self.subTest(case=label, needle=needle):
                    self.assertNotIn(needle, out)

    def test_authored_formatting_survives(self):
        cases = {
            "table": (
                '<table style="width: 80%"><tbody><tr><td colspan="2" style="text-align: center">a</td></tr></tbody></table>',
                ("<table", "width:80%", 'colspan="2"', "text-align:center"),
            ),
            "floated image": (
                '<img src="/files/a.png" alt="a" width="200" style="float: left; margin-right: 8px">',
                (
                    "<img",
                    "float:left",
                    "margin-right:8px",
                    'width="200"',
                    'src="/files/a.png"',
                ),
            ),
            "private image": (
                '<img src="/private/files/a.png?fid=abc">',
                ("/private/files/a.png?fid=abc",),
            ),
            "hebrew rtl": (
                f'<span dir="rtl" lang="he">{HEBREW}</span>',
                ('dir="rtl"', 'lang="he"', HEBREW),
            ),
            "greek": (f"<p>{GREEK}</p>", (GREEK,)),
            "checklist": (
                '<ul><li data-list="checked">done</li></ul>',
                ('data-list="checked"',),
            ),
            "semantics": (
                '<blockquote cite="https://x.y">q</blockquote><abbr title="t">a</abbr><sup>1</sup><sub>2</sub>',
                ("<blockquote", "<abbr", "<sup>", "<sub>"),
            ),
            "links": (
                '<a href="https://ok.example">x</a><a href="mailto:a@b.c">m</a>',
                ("https://ok.example", "mailto:a@b.c"),
            ),
        }
        for label, (html, needles) in cases.items():
            out = clean_rich(html).replace(": ", ":").replace("; ", ";")
            for needle in needles:
                with self.subTest(case=label, needle=needle):
                    self.assertIn(needle, out)

    def test_plain_values_are_never_rewritten(self):
        for value in (
            "Q&A forum-536",
            "ID-101-P0 Assignment-539",
            "",
            None,
            3,
            "a & b",
        ):
            with self.subTest(value=value):
                self.assertEqual(clean_rich(value), value)

    def test_code_profile(self):
        out = clean_code(
            '<span class="hljs-keyword">def</span> f()<br><img src=x onerror=1><div onclick="x">y</div>'
        )
        self.assertIn('class="hljs-keyword"', out)
        self.assertIn("<br>", out)
        for banned in ("<img", "onerror", "onclick"):
            self.assertNotIn(banned, out)


class TestUrlPolicy(IntegrationTestCase):
    def test_truth_table(self):
        nl, tab = chr(10), chr(9)
        good = [
            "https://ok.example/a?b=1",
            "http://ok.example",
            "mailto:a@b.c",
            "tel:+15551234",
            "/files/x.pdf",
            "#frag",
            "?q=1",
            "",
            None,
        ]
        bad = [
            "javascript:alert(1)",
            "JaVaScRiPt:alert(1)",
            f"java{nl}script:alert(1)",
            f"{tab}javascript:alert(1)",
            "data:text/html,x",
            "vbscript:x",
            "//evil.example",
            "\\\\evil",
        ]
        for v in good:
            with self.subTest(good=v):
                self.assertTrue(is_safe_url(v))
        for v in bad:
            with self.subTest(bad=v):
                self.assertFalse(is_safe_url(v))
        self.assertFalse(is_safe_url("/files/x.pdf", allow_relative=False))
        self.assertFalse(is_safe_url("mailto:a@b.c", schemes=("http", "https")))

    def test_embed_url(self):
        self.assertEqual(
            safe_embed_url("https://view.genially.com/x"), "https://view.genially.com/x"
        )
        for v in (
            "/files/evil.html",
            "javascript:alert(1)",
            "//evil.example/x",
            "data:text/html,x",
            "",
            None,
        ):
            with self.subTest(bad=v):
                self.assertEqual(safe_embed_url(v), "")
        site_host = (
            frappe.utils.get_url().split("://", 1)[-1].split("/")[0].split(":")[0]
        )
        self.assertEqual(safe_embed_url(f"https://{site_host}/files/evil.html"), "")


def _doc(blocks):
    return json.dumps({"time": 1, "version": "2.30", "blocks": blocks})


def _blocks(content):
    return json.loads(content)["blocks"]


class TestEditorJsSafety(IntegrationTestCase):
    def test_a_clean_lesson_is_byte_identical(self):
        content = _doc(
            [
                {"type": "paragraph", "data": {"text": "ok <b>bold</b>"}},
                {"type": "markdown", "data": {"text": ""}},
                {
                    "type": "upload",
                    "data": {"file_url": "/private/files/a b.pdf", "file_type": "PDF"},
                },
                {"type": "iframe", "data": {"html": "https://youtu.be/yS2_6mocJ_8"}},
                {"type": "quiz", "data": {"quiz": "theological-method-quiz"}},
                {"type": "discussionActivity", "data": {"discussion": "Q&A forum-536"}},
                {
                    "type": "folder",
                    "data": {
                        "folder_ref": "P0 Section-0546",
                        "folder": "Section files",
                    },
                },
                {"type": "header", "data": {"text": "Title", "level": 2}},
            ]
        )
        out, notes = sanitize_content(content)
        self.assertEqual(notes, [])
        self.assertEqual(out, content)

    def test_non_editorjs_content_is_left_alone(self):
        for value in (
            "",
            None,
            "plain text",
            "[1, 2]",
            '{"no": "blocks"}',
            "<p>html</p>",
        ):
            with self.subTest(value=value):
                self.assertEqual(sanitize_content(value), (value, []))

    def test_handlers_and_the_bypass_are_removed(self):
        out, notes = sanitize_content(
            _doc(
                [
                    {
                        "type": "paragraph",
                        "data": {"text": "ok <img src=x onerror=alert(1)>"},
                    },
                    {
                        "type": "markdown",
                        "data": {"text": "<!--><img src=x onerror=alert(1)>-->"},
                    },
                ]
            )
        )
        self.assertEqual(len(notes), 2)
        self.assertNotIn("onerror", out)

    def test_an_embed_is_reduced_to_its_url(self):
        out, notes = sanitize_content(
            _doc(
                [
                    {
                        "type": "iframe",
                        "data": {
                            "html": "<div onmouseover=x()><iframe src='https://view.genially.com/abc' onload=y()></iframe></div>"
                        },
                    },
                ]
            )
        )
        self.assertEqual(
            _blocks(out)[0]["data"]["html"], "https://view.genially.com/abc"
        )
        self.assertEqual(len(notes), 1)

    def test_an_embed_with_no_usable_url_goes_and_says_so(self):
        for html in (
            "<div><img src=x onerror=alert(1)></div>",
            '<iframe src="javascript:alert(1)"></iframe>',
            '<iframe src="/files/evil.html"></iframe>',
            "<iframe srcdoc='<script>1</script>'></iframe>",
        ):
            with self.subTest(html=html):
                out, notes = sanitize_content(
                    _doc(
                        [
                            {"type": "paragraph", "data": {"text": "kept"}},
                            {"type": "iframe", "data": {"html": html}},
                        ]
                    )
                )
                self.assertEqual([b["type"] for b in _blocks(out)], ["paragraph"])
                self.assertIn("Block 2 (iframe)", notes[0])

    def test_a_bad_url_is_blanked_not_fatal(self):
        out, notes = sanitize_content(
            _doc(
                [
                    {
                        "type": "image",
                        "data": {
                            "url": "javascript:alert(1)",
                            "caption": "<form action=//evil><input></form>cap",
                        },
                    },
                ]
            )
        )
        data = _blocks(out)[0]["data"]
        self.assertEqual(data["url"], "")
        self.assertEqual(data["caption"], "cap")
        self.assertTrue(notes)

    def test_code_keeps_its_highlighting(self):
        out, _notes = sanitize_content(
            _doc(
                [
                    {
                        "type": "codeBox",
                        "data": {
                            "code": '<span class="hljs-keyword">def</span> f()<img src=x onerror=1>',
                            "language": "python",
                        },
                    },
                ]
            )
        )
        code = _blocks(out)[0]["data"]["code"]
        self.assertIn("hljs-keyword", code)
        self.assertNotIn("<img", code)

    def test_an_unknown_block_is_kept_and_cleaned_not_dropped(self):
        out, notes = sanitize_content(
            _doc(
                [
                    {
                        "type": "futureTool",
                        "data": {
                            "anything": "<p style='position:fixed;top:0'>x</p>",
                            "n": 3,
                            "nested": {"deep": ["<script>1</script>t"]},
                        },
                    },
                ]
            )
        )
        data = _blocks(out)[0]["data"]
        self.assertEqual(data["n"], 3)
        self.assertNotIn("position", data["anything"])
        self.assertEqual(data["nested"]["deep"], ["t"])
        self.assertEqual(len(notes), 1)

    def test_nested_lists_are_walked(self):
        out, _notes = sanitize_content(
            _doc(
                [
                    {
                        "type": "list",
                        "data": {
                            "style": "unordered",
                            "items": [
                                {
                                    "content": "a <i>i</i>",
                                    "items": [
                                        {
                                            "content": "<a href='javascript:1'>x</a>",
                                            "items": [],
                                        }
                                    ],
                                }
                            ],
                        },
                    },
                ]
            )
        )
        self.assertNotIn("javascript", out)
        self.assertIn("<i>i</i>", out)

    def test_the_lesson_controller_cleans_both_fields(self):
        lesson = frappe.new_doc("Course Lesson")
        hostile = _doc(
            [{"type": "paragraph", "data": {"text": "<img src=x onerror=alert(1)>"}}]
        )
        lesson.content = hostile
        lesson.instructor_content = hostile
        lesson.sanitize_editor_content()
        self.assertNotIn("onerror", lesson.content)
        self.assertNotIn("onerror", lesson.instructor_content)
        frappe.clear_messages()


class TestP008RichTextHook(IntegrationTestCase):
    """F6: the wildcard `before_validate` sanitiser.

    Measured before it was wired up (p008 §8): of 137 rich values on potestas,
    13 changed, every one of them the same p005a probe losing a smuggled
    `<!---->`. `Program` and `Academic Unit` -- the doctypes that render on the
    public website -- changed nothing.
    """

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_a_script_tag_does_not_survive_a_save(self):
        doc = frappe.get_doc(
            {
                "doctype": "Note",
                "title": f"p008-f6-{frappe.generate_hash(length=6)}",
                "content": "<p>hello</p><script>alert(1)</script>",
            }
        )
        doc.insert(ignore_permissions=True)
        self.assertNotIn("<script", doc.content)
        self.assertIn("hello", doc.content)

    def test_an_event_handler_does_not_survive_a_save(self):
        doc = frappe.get_doc(
            {
                "doctype": "Note",
                "title": f"p008-f6-{frappe.generate_hash(length=6)}",
                "content": '<img src="x" onerror="alert(1)">',
            }
        )
        doc.insert(ignore_permissions=True)
        self.assertNotIn("onerror", doc.content)

    def test_prose_with_a_bare_angle_bracket_is_left_alone(self):
        """The dry run caught this: `has_markup` fired on any `<` or `>`, so
        'fixed deposits >3 months' was escaped to '&gt;3', and because the
        escape is itself markup-free the damage compounded on every save."""
        for text in ("fixed deposits >3 months", "a < b and b > c", "5 > 4"):
            with self.subTest(text=text):
                self.assertFalse(content_safety.has_markup(text))

    def test_json_in_a_text_field_is_not_sanitised(self):
        r"""`Workspace.content` and `Course Lesson.content` are EditorJS JSON.
        Sanitising them turned `class=\"h4\"` into `class="\&quot;h4\&quot;"`
        on twenty Desk workspaces."""
        # Raw string: the stored value really does contain backslash-quote, and
        # without `r` Python collapses it to a bare quote -- which is not valid
        # JSON, so the guard was being tested against the wrong input.
        payload = r'[{"type":"header","data":{"text":"<span class=\"h4\">Hi</span>"}}]'
        self.assertTrue(content_safety._is_json_payload(payload))
        self.assertFalse(content_safety._is_json_payload("<p>not json</p>"))

    def test_the_hook_is_registered_on_the_wildcard(self):
        hooks = frappe.get_hooks("doc_events") or {}
        wildcard = hooks.get("*", {})
        before = wildcard.get("before_validate") or []
        if isinstance(before, str):
            before = [before]
        self.assertIn(
            "seminary.seminary.content_safety.sanitize_rich_text",
            before,
            "F6 must stay on the wildcard: a new doctype is covered without opting in",
        )


class TestP008UrlHook(IntegrationTestCase):
    """F7: the wildcard URL validator."""

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_a_javascript_url_is_refused_on_a_named_field(self):
        cs = frappe.get_all("Course Schedule", pluck="name", limit=1)
        if not cs:
            self.skipTest("no Course Schedule on this site")
        doc = frappe.get_doc("Course Schedule", cs[0])
        doc.web_meeting = "javascript:alert(1)"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_an_https_url_is_accepted(self):
        cs = frappe.get_all("Course Schedule", pluck="name", limit=1)
        if not cs:
            self.skipTest("no Course Schedule on this site")
        doc = frappe.get_doc("Course Schedule", cs[0])
        doc.web_meeting = "https://meet.example.org/abc"
        doc.save(ignore_permissions=True)
        self.assertEqual(doc.web_meeting, "https://meet.example.org/abc")

    def test_the_hook_is_registered(self):
        hooks = frappe.get_hooks("doc_events") or {}
        validate = (hooks.get("*", {}) or {}).get("validate") or []
        if isinstance(validate, str):
            validate = [validate]
        self.assertIn("seminary.seminary.url_policy.validate_urls", validate)

    def test_an_unchanged_legacy_value_does_not_block_an_unrelated_edit(self):
        """A value stored before this rule existed must not make the record
        unsaveable -- it is refused when someone next touches *that* field.

        Exercised through a real `save()` deliberately: `has_value_changed`
        answers against `_doc_before_save`, which only a save populates, so
        calling the hook directly would report everything as changed and prove
        nothing about the path that actually runs.
        """
        cs = frappe.get_all("Course Schedule", pluck="name", limit=1)
        if not cs:
            self.skipTest("no Course Schedule on this site")
        frappe.db.set_value(
            "Course Schedule",
            cs[0],
            "web_meeting",
            "javascript:legacy",
            update_modified=False,
        )
        doc = frappe.get_doc("Course Schedule", cs[0])
        # touch something else entirely
        doc.run_method("set_title") if hasattr(doc, "set_title") else None
        doc.flags.ignore_mandatory = True
        doc.save(ignore_permissions=True)  # must not raise
        self.assertEqual(
            frappe.db.get_value("Course Schedule", cs[0], "web_meeting"),
            "javascript:legacy",
            "the legacy value is left as it was until someone edits that field",
        )

    def test_touching_the_field_does_refuse_the_legacy_value(self):
        """The other half: the rule bites when that field is actually edited."""
        cs = frappe.get_all("Course Schedule", pluck="name", limit=1)
        if not cs:
            self.skipTest("no Course Schedule on this site")
        frappe.db.set_value(
            "Course Schedule", cs[0], "web_meeting", "", update_modified=False
        )
        doc = frappe.get_doc("Course Schedule", cs[0])
        doc.web_meeting = "javascript:alert(1)"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)
