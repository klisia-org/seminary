# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008 F13: the frontend HTML-sink contract.

F1-F5 removed every unguarded way for stored HTML to reach the DOM. Nothing stops
the next one being added -- `v-html` is one word, and `el.innerHTML = x` reads
like an assignment rather than an execution. These tests are the ratchet.

They are plain file scans, deliberately: a Vue test runner is not installed here,
and the property under test is textual ("this token appears only where we said").
Every exception is listed with the reason it is safe, so adding one is a decision
somebody writes down rather than a line that slips through review.
"""

import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "frontend" / "src"

#: `v-html` is allowed in exactly one component, which sanitises first.
VHTML_ALLOWED = {"components/SafeHtml.vue"}

#: `X.innerHTML = ...` sites that are safe, each with the reason.
INNERHTML_ALLOWED = {
    # Sanitised at the sink.
    "utils/markdownParser.js": "sanitize() -- EditorJS JSON is not server-sanitised (F4)",
    "utils/code.ts": "sanitize(_, 'code') -- data.code holds highlight.js markup (F4)",
    "components/LightEditor.vue": "sanitize() -- stored rich text into a contenteditable (F13)",
    # Clearing only: assigning '' parses nothing.
    "utils/videorecord.js": "innerHTML = '' (clear)",
    "utils/foldertool.js": "innerHTML = '' (clear)",
    "pages/Lesson.vue": "innerHTML = '' (clear)",
    "pages/LessonForm.vue": "innerHTML = '' (clear)",
}

#: A detached node is NOT inert: `<img onerror>` fires while it is off-document.
#: `utils/index.js` holds `htmlToText`, the DOMParser replacement (F3).
STRIPPER = re.compile(r"createElement\(['\"]div['\"]\)[\s\S]{0,200}?\.innerHTML\s*=")

#: A *write*. Deliberately receiver-agnostic -- an earlier version anchored on an
#: identifier and so missed `document.getElementById(h).innerHTML = ''`. Reads
#: (`x = el.innerHTML`, `{code: el.innerHTML}`) have no `=` after the property.
WRITE = re.compile(r"\.innerHTML\s*=(?!=)")
CLEARS = re.compile(r"\.innerHTML\s*=\s*['\"]{2}\s*(?://.*)?$")


def _still_writes(rel) -> bool:
    path = SRC / rel
    return path.exists() and bool(WRITE.search(path.read_text()))


def _files():
    for path in sorted(SRC.rglob("*")):
        if path.suffix in {".vue", ".js", ".ts"} and path.is_file():
            yield path, str(path.relative_to(SRC)), path.read_text()


class TestP008FrontendSinks(unittest.TestCase):
    def test_v_html_lives_only_in_safehtml(self):
        offenders = []
        for _p, rel, text in _files():
            if rel in VHTML_ALLOWED:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if "v-html" in line and not line.lstrip().startswith(
                    ("*", "//", "<!--")
                ):
                    offenders.append(f"{rel}:{i}")
        self.assertEqual(
            offenders, [], "v-html outside SafeHtml.vue -- use <SafeHtml :html=... />"
        )

    def test_innerhtml_writes_are_declared(self):
        offenders = []
        for _p, rel, text in _files():
            for i, line in enumerate(text.splitlines(), 1):
                if not WRITE.search(line) or line.lstrip().startswith(("*", "//")):
                    continue
                if CLEARS.search(line.rstrip()) or rel in INNERHTML_ALLOWED:
                    continue
                offenders.append(f"{rel}:{i}: {line.strip()[:70]}")
        self.assertEqual(
            offenders,
            [],
            "undeclared innerHTML write -- sanitise it, build the node, or add it "
            "to INNERHTML_ALLOWED with a reason",
        )

    def test_no_detached_div_strippers(self):
        """The F3 class: build a div, assign innerHTML, read textContent."""
        offenders = []
        for _p, rel, text in _files():
            if rel == "utils/index.js":
                continue
            if STRIPPER.search(text):
                offenders.append(rel)
        self.assertEqual(
            offenders, [], "detached-div HTML stripper -- use htmlToText() from @/utils"
        )

    def test_htmltotext_uses_domparser(self):
        text = (SRC / "utils" / "index.js").read_text()
        self.assertIn(
            "DOMParser", text, "htmlToText must not parse through a live node"
        )

    def test_markdown_renders_with_html_disabled(self):
        text = (SRC / "components" / "LessonContent.vue").read_text()
        self.assertRegex(text, r"html:\s*false", "MarkdownIt must not pass raw HTML")

    def test_the_allow_lists_have_no_stale_entries(self):
        """A removed exception must not linger and quietly re-permit a sink."""
        for rel in VHTML_ALLOWED:
            self.assertTrue((SRC / rel).exists(), f"{rel} is gone from VHTML_ALLOWED")
        # `_still_writes` keeps the file body out of this frame: frappe's runner
        # dumps every local on failure, and a whole .vue file buries the message.
        stale = [rel for rel in sorted(INNERHTML_ALLOWED) if not _still_writes(rel)]
        self.assertEqual(
            stale, [], "no longer writes innerHTML -- drop from INNERHTML_ALLOWED"
        )
