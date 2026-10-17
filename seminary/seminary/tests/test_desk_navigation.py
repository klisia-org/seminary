# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Desk navigation (decision 088).

The dock and the sidebars are shipped files, so these tests read the files and need no site data.
What they hold: every dock entry opens a sidebar or workspace we ship, every sidebar link points
at something Seminary owns, and no top-level doctype or report is left out of every sidebar.
"""

import json
from pathlib import Path

from frappe.tests import UnitTestCase

PACKAGE = Path(__file__).resolve().parents[2]
MODULE = PACKAGE / "seminary"
# Per-user bookkeeping rows with no screen of their own.
INTERNAL = {"Cohort Feed Read State", "Cohort Thread Read State"}
# Frappe's own doctypes that a sidebar may open, because every site has them.
FRAMEWORK_DOCTYPES = set()


def _load(path):
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _names(doctype, folder):
    return {
        doc["name"]
        for path in PACKAGE.glob(f"*/{folder}/*/*.json")
        if (doc := _load(path)).get("doctype") == doctype
    }


def _sidebars():
    return [_load(p) for p in sorted((MODULE / "sidebar").glob("*/*.json"))]


def _links(sidebar):
    return [
        i for i in sidebar["items"] if i["type"] == "Link" and i["link_type"] != "URL"
    ]


class UnitTestDeskNavigation(UnitTestCase):
    def test_dock_entries_open_something_we_ship(self):
        dock = _load(PACKAGE / "dock" / "seminary" / "seminary.json")
        sidebars = {s["name"] for s in _sidebars()}
        workspaces = _names("Workspace", "workspace")
        self.assertTrue(dock["items"])
        for row in dock["items"]:
            shipped = sidebars if row["link_type"] == "Sidebar" else workspaces
            self.assertIn(row["link_to"], shipped, row["title"])

    def test_sidebars_open_only_seminary_objects(self):
        known = {
            "DocType": _names("DocType", "doctype") | FRAMEWORK_DOCTYPES,
            "Report": _names("Report", "report"),
            "Workspace": _names("Workspace", "workspace"),
        }
        for sidebar in _sidebars():
            for item in _links(sidebar):
                where = f"{sidebar['name']}: {item['label']}"
                self.assertIn(item["link_type"], known, where)
                self.assertIn(item["link_to"], known[item["link_type"]], where)

    def test_no_doctype_or_report_is_left_out(self):
        linked = {i["link_to"] for s in _sidebars() for i in _links(s)}
        top_level = {
            doc["name"]
            for path in PACKAGE.glob("*/doctype/*/*.json")
            if (doc := _load(path)).get("doctype") == "DocType"
            and not doc.get("istable")
        }
        left_out = (top_level | _names("Report", "report")) - linked - INTERNAL
        self.assertEqual(sorted(left_out), [])

    def test_sidebar_titles_are_prefixed_and_unique(self):
        titles = [s["title"] for s in _sidebars()]
        self.assertEqual(len(titles), len(set(titles)))
        for title in titles:
            self.assertTrue(title.startswith("Seminary "), title)

    def test_reports_are_permissioned_on_a_parent_doctype(self):
        # Frappe checks report access on ref_doctype; a child table has no permissions, so the
        # report opens for Administrator only.
        import frappe

        for path in PACKAGE.glob("*/report/*/*.json"):
            report = _load(path)
            if report.get("doctype") == "Report":
                ref = report["ref_doctype"]
                self.assertFalse(
                    frappe.db.get_value("DocType", ref, "istable"),
                    f"{report['name']} -> {ref}",
                )
