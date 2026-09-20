# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p010 Block F, A07-4: one reader for the CSRF token.

The register called the ten hand-rolled copies a "hole generator". Measured,
that is overstated: a forgotten header fails **closed** -- `frappe/auth.py`
throws `CSRFTokenError` and the request 400s, so the feature breaks rather than
opening. What was real is that `getCsrfToken` had been pasted into **eight**
files and they had already drifted: three guarded `typeof window` and five did
not, three returned `null` and five `''`. There was no canonical copy left to
model a ninth on.

So the token now has exactly one reader, and these scans are the ratchet. They
are plain file scans, matching `test_p008_frontend_sinks`: no Vue test runner is
installed, and the property is textual ("this token is read in one place").

Deliberately NOT enforced here: how each request is sent. Two sites use
`XMLHttpRequest` because they need upload progress, which `fetch` cannot report,
and the `credentials` modes still differ. Consolidating the plumbing is a larger
change with a browser pass; this covers the part that was duplicated.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "frontend" / "src"
PORTAL = ROOT / "portal-shell" / "src"

#: One reader PER PACKAGE. portal-shell is built on its own and consumed
#: through `link:../portal-shell`, so it cannot import from `frontend/src`.
PACKAGES = {
    "frontend": (SRC, "utils/csrf.js"),
    "portal-shell": (PORTAL, "csrf.js"),
}

#: Ways the token has been read. Any of these outside HELPER is a new copy.
READS = (
    re.compile(r"window\.csrf_token"),
    re.compile(r"window\.frappe\?\.csrf_token"),
    re.compile(r"""meta\[name=["']csrf-token["']\]"""),
)

DEFINITION = re.compile(r"(?:const|function)\s+getCsrfToken\s*(?:=|\()")

#: Sites that send the header, each keeping its own transport. Listed so that
#: adding one is a decision somebody writes down.
SENDERS = {
    "components/FolderPlugin.vue": "XHR upload_file (progress) + fetch delete_file",
    "components/SmartFileUploader.vue": "XHR upload_file (progress)",
    "components/Modals/CourseAssessmentModal.vue": "fetch insert_cs_assessment",
    "utils/directUpload.js": "fetch, direct-to-object-storage handshake",
    "utils/foldertool.js": "fetch Course Folder + create_subfolder",
    "pages/RecommenderForm.vue": "fetch upload_attachment -- GUEST flow",
    "pages/CourseAssessment.vue": "fetch save_course_assessment",
    "pages/StudentAttendanceCS.vue": "fetch self check-in",
    "pages/CourseForm.vue": "fetch course save",
}

HEADER = "X-Frappe-CSRF-Token"


def _sources(base):
    if not base.exists():
        return []
    return [p for p in base.rglob("*") if p.suffix in (".js", ".ts", ".vue")]


class TestP010CsrfContract(unittest.TestCase):
    def test_each_package_has_exactly_one_definition(self):
        for label, (base, rel) in PACKAGES.items():
            helper = base / rel
            self.assertTrue(helper.exists(), f"{label}: {rel} is the single reader")
            offenders = [
                str(p.relative_to(base))
                for p in _sources(base)
                if p != helper and DEFINITION.search(p.read_text())
            ]
            self.assertEqual(
                offenders, [], f"{label}: import getCsrfToken, do not redefine it"
            )

    def test_nothing_else_reads_the_token_out_of_the_page(self):
        helpers = {base / rel for base, rel in PACKAGES.values()}
        offenders = []
        for base, _rel in PACKAGES.values():
            for p in _sources(base):
                if p in helpers:
                    continue
                if any(r.search(p.read_text()) for r in READS):
                    offenders.append(str(p))
        self.assertEqual(offenders, [], "read the token via getCsrfToken()")

    def test_every_sender_is_declared_and_imports_the_helper(self):
        found = {
            str(p.relative_to(SRC))
            for p in _sources(SRC)
            if HEADER in p.read_text() and p != SRC / PACKAGES["frontend"][1]
        }
        self.assertEqual(
            found,
            set(SENDERS),
            "a new site sending the CSRF header must be listed in SENDERS",
        )
        for rel in sorted(found):
            self.assertIn(
                "getCsrfToken",
                (SRC / rel).read_text(),
                f"{rel} sends the header without the shared reader",
            )

    def test_portal_shell_sends_through_its_own_reader(self):
        cfg = PORTAL / "config.js"
        self.assertIn(HEADER, cfg.read_text())
        self.assertIn("getCsrfToken", cfg.read_text())

    def test_the_declared_senders_all_still_exist(self):
        missing = [rel for rel in SENDERS if not (SRC / rel).exists()]
        self.assertEqual(missing, [], "stale SENDERS entries")
