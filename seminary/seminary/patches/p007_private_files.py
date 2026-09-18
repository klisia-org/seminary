# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Private files, read through the document they hang on (p007 §8.2).

1. Files embedded in lesson content and in exam/quiz answers are attached to
   their host (the lesson's section, the submission). A public one that belongs
   to nobody else is made private and the content is rewritten to its new URL.
2. Public Files attached to a seminary document that is not on the public
   website are made private.
3. Every field in `file_policy.PUBLIC_FILE_FIELDS` is brought in line with its
   predicate: a team photo of a published unit is public, any other portrait is
   private (and still readable by every signed-in user).

Runs as Administrator, so every file is adoptable. Idempotent; a file that
cannot be moved is logged and skipped.
"""

import frappe

from seminary.seminary import file_policy


def _log(title):
    frappe.log_error(frappe.get_traceback(), f"p007_private_files: {title}")


def execute():
    for doctype in file_policy.EMBEDDED_FILE_FIELDS:
        if not frappe.db.exists("DocType", doctype):
            continue
        for name in frappe.get_all(doctype, pluck="name"):
            try:
                file_policy.adopt_embedded(frappe.get_doc(doctype, name))
            except Exception:
                _log(f"adopt {doctype} {name}")

    for row in frappe.get_all(
        "File",
        filters={
            "is_private": 0,
            "is_folder": 0,
            "attached_to_doctype": ["is", "set"],
            "attached_to_name": ["is", "set"],
        },
        fields=["name", "file_url"],
    ):
        try:
            doc = frappe.get_doc("File", row.name)
            if cint_private(doc) or file_policy.may_be_public_for_host(doc):
                continue
            file_policy.set_privacy(
                doc.file_url,
                public=False,
                host=(doc.attached_to_doctype, doc.attached_to_name),
            )
        except Exception:
            _log(f"privatise {row.name}")

    for doctype in sorted({dt for dt, _f in file_policy.PUBLIC_FILE_FIELDS}):
        if not frappe.db.exists("DocType", doctype):
            continue
        if frappe.get_meta(doctype).issingle:
            names = [doctype]
        else:
            names = frappe.get_all(doctype, pluck="name")
        for name in names:
            try:
                file_policy.sync_public_state(doctype, name)
            except Exception:
                _log(f"sync {doctype} {name}")


def cint_private(doc):
    return bool(frappe.utils.cint(doc.is_private))
