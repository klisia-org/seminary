# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Seminary installs without ERPNext, so none of its doctypes may link a doctype
another app owns. Sync never checks link targets; the first Custom Field another
app adds to the doctype does, and the install fails there (ADR 039 addendum)."""

import glob
import json
import os

import frappe
from frappe.tests import IntegrationTestCase

LINK_TYPES = ("Link", "Table", "Table MultiSelect")


class TestNoForeignLinks(IntegrationTestCase):
    def test_every_link_targets_frappe_or_seminary(self):
        root = frappe.get_app_path("seminary")
        owner = {}
        for name, module in frappe.get_all(
            "DocType", fields=["name", "module"], as_list=1
        ):
            owner[name] = frappe.db.get_value("Module Def", module, "app_name")
        foreign = []
        for path in glob.glob(
            os.path.join(root, "**", "doctype", "*", "*.json"), recursive=True
        ):
            with open(path) as f:
                doc = json.load(f)
            if not isinstance(doc, dict) or doc.get("doctype") != "DocType":
                continue
            for df in doc.get("fields", []):
                if (
                    df.get("fieldtype") in LINK_TYPES
                    and df.get("options")
                    and owner.get(df["options"]) not in ("frappe", "seminary")
                ):
                    foreign.append(f"{doc['name']}.{df['fieldname']} → {df['options']}")
        self.assertEqual(foreign, [])
