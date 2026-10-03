# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p017: portal colours go through frappe-ui's colour variables.

Dark mode, and any theme an installed app supplies, work by redefining frappe-ui's
variables (`--surface-*`, `--ink-*`, `--outline-*`). A raw Tailwind colour
(`text-red-600`) bypasses them and stays the same in every mode. A class naming a
shade frappe-ui does not have (`text-ink-red-6`) compiles to nothing at all. Both
read like working code, so these tests are the ratchet.

Plain file scans, like test_p008_frontend_sinks: the property is textual.
"""

import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "frontend" / "src"

#: The shades frappe-ui 0.1.261 compiles, per colour group. Taken from a Tailwind
#: build of every candidate; re-derive it on a frappe-ui upgrade.
SHADES = {
    "surface": {
        "white",
        "cards",
        "modal",
        "menu-bar",
        "selected",
        "cyan-1",
        "pink-1",
        "violet-1",
        "orange-1",
        "amber-1",
        "amber-2",
        "amber-3",
        "blue-1",
        "blue-2",
        "blue-3",
        "green-1",
        "green-2",
        "green-3",
        *(f"gray-{n}" for n in range(1, 8)),
        *(f"red-{n}" for n in range(1, 8)),
    },
    "ink": {
        "white",
        "cyan-1",
        "pink-1",
        "violet-1",
        "amber-1",
        "amber-2",
        "amber-3",
        "blue-link",
        "blue-1",
        "blue-2",
        "blue-3",
        "green-1",
        "green-2",
        "green-3",
        *(f"gray-{n}" for n in range(1, 10)),
        *(f"red-{n}" for n in range(1, 5)),
    },
    "outline": {
        "white",
        "gray-modals",
        "amber-1",
        "amber-2",
        "blue-1",
        "green-1",
        "green-2",
        "orange-1",
        "red-1",
        "red-2",
        "red-3",
        *(f"gray-{n}" for n in range(1, 6)),
    },
}

#: Which utilities each group compiles for (`border-surface-white` and
#: `bg-ink-gray-2` compile to nothing).
UTILITIES = {
    "surface": {"bg", "fill"},
    "ink": {"text", "placeholder", "fill", "stroke"},
    "outline": {
        "border",
        "border-t",
        "border-b",
        "border-l",
        "border-r",
        "border-x",
        "border-y",
        "divide",
        "ring",
    },
}

SEMANTIC = re.compile(
    r"(?<![\w\-\[])(?:[a-z\-]+:)*!?"
    r"((?:bg|text|placeholder|fill|stroke|border(?:-[tblrxy])?|divide|ring))"
    r"-(surface|ink|outline)-([a-z0-9\-]*[a-z0-9])(?![\w\-])"
)

PALETTE = (
    "gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|"
    "sky|blue|indigo|violet|purple|fuchsia|pink|rose"
)
RAW = re.compile(
    r"(?<![\w\-\[])(?:[a-z\-]+:)*!?"
    r"(?:bg|text|border(?:-[tblrxy])?|ring|divide|fill|stroke|placeholder|from|to|via|"
    r"decoration|shadow|accent|caret)"
    rf"-((?:{PALETTE})-\d{{2,3}}|white|black)(?:/\d+)?(?![\w\-])"
)

#: Raw colours that must not follow the theme, each with the reason.
RAW_ALLOWED = {
    "components/ProfileModal.vue": "white camera icon on a dark overlay over the photo",
    "components/RecorderPlugin.vue": "black video frame, white timer and red recording dot over it",
    "components/AssignmentViewers/YouTubePlayer.vue": "black letterbox behind the video",
    "pages/CourseForm.vue": "white text on a dark overlay over the course image",
}


def _files():
    for path in sorted(SRC.rglob("*")):
        if path.suffix in {".vue", ".js", ".ts", ".css"} and path.is_file():
            yield str(path.relative_to(SRC)), path.read_text()


class TestP017PortalColours(unittest.TestCase):
    def test_semantic_classes_exist(self):
        offenders = []
        for rel, text in _files():
            for i, line in enumerate(text.splitlines(), 1):
                for m in SEMANTIC.finditer(line):
                    utility, group, shade = m.groups()
                    if utility not in UTILITIES[group] or shade not in SHADES[group]:
                        offenders.append(f"{rel}:{i} {m.group(0)}")
        self.assertEqual(
            offenders, [], "classes frappe-ui does not compile -- they render no colour"
        )

    def test_no_raw_palette_colours(self):
        offenders = []
        for rel, text in _files():
            if rel in RAW_ALLOWED:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                offenders += [f"{rel}:{i} {m.group(0)}" for m in RAW.finditer(line)]
        self.assertEqual(
            offenders,
            [],
            "raw Tailwind colours ignore dark mode and themes -- use surface/ink/outline",
        )

    def test_allowed_files_still_need_it(self):
        stale = [rel for rel in RAW_ALLOWED if not RAW.search((SRC / rel).read_text())]
        self.assertEqual(stale, [], "drop these from RAW_ALLOWED")
