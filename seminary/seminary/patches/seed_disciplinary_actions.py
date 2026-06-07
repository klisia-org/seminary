"""Seed the starter Disciplinary Actions on existing sites.

The disciplinary subsystem (ADR 032) ships a controlled catalog of sanction
types. These are not fixtures (the catalog is desk-configurable); they are
seeded once here, create-only-if-missing, so existing rows are untouched.
"""

import frappe

from seminary.install import seed_disciplinary_actions


def execute():
    seed_disciplinary_actions()
    print("Ensured starter Disciplinary Actions exist.")
