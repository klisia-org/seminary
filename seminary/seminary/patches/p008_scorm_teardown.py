# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""SCORM packages are stored, not unpacked (privatedocs p008 F8).

Until p008 an uploaded package was extracted into ``public/scorm/`` -- a
world-readable directory served with no session, reachable through a
caller-controlled path (p005 A01-6 / A02-4, p005a A05-8) -- and nothing ever
played it. This patch removes what that left behind:

1. every SCORM chapter loses its three extracted-path fields, and its package
   File is made private and attached to the chapter, so the section's staff can
   read it and SCORM delivery (p009) has a complete inventory to work from;
2. the ``public/scorm`` tree is deleted.

Idempotent. The directory is resolved and checked against the site's public path
before anything is removed; a chapter whose File is missing is logged and kept.
"""

import os
import shutil

import frappe


def execute():
    from seminary.seminary.api import pin_scorm_package

    if frappe.db.exists("DocType", "Course Schedule Chapter"):
        # p009 S1 dropped these three columns outright. On a site that ran this
        # patch when they existed nothing changes; on one where p009 has already
        # migrated there is nothing to clear, and the patch must not crash
        # trying -- a patch that explodes when invoked is a landmine for
        # whoever rebuilds a site or runs it by hand.
        stale = [
            f
            for f in ("scorm_package_path", "manifest_file", "launch_file")
            if frappe.db.has_column("Course Schedule Chapter", f)
        ]
        for ch in frappe.get_all(
            "Course Schedule Chapter",
            filters={"is_scorm_package": 1},
            fields=["name", "scorm_package"],
        ):
            if stale:
                frappe.db.set_value(
                    "Course Schedule Chapter",
                    ch.name,
                    dict.fromkeys(stale),
                    update_modified=False,
                )
            if ch.scorm_package and frappe.db.exists("File", ch.scorm_package):
                try:
                    pin_scorm_package(ch.name, ch.scorm_package)
                except Exception:
                    frappe.log_error(
                        frappe.get_traceback(),
                        f"p008_scorm_teardown: could not pin the package of {ch.name}",
                    )
            elif ch.scorm_package:
                frappe.log_error(
                    f"Chapter {ch.name} names SCORM package {ch.scorm_package}, "
                    "which no longer exists.",
                    "p008_scorm_teardown: missing package",
                )

    public = os.path.realpath(frappe.get_site_path("public"))
    scorm = os.path.realpath(os.path.join(public, "scorm"))
    if (
        scorm != public
        and os.path.commonpath([scorm, public]) == public
        and os.path.basename(scorm) == "scorm"
        and os.path.isdir(scorm)
        and not os.path.islink(os.path.join(public, "scorm"))
    ):
        shutil.rmtree(scorm, ignore_errors=True)
