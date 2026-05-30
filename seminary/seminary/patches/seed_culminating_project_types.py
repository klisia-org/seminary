"""Seed the starter Culminating Project Types on existing sites.

`Culminating Project Type` was briefly shipped as a fixture, which re-imported on
every migrate and wiped the per-type milestone rows seminaries configure on the
desk. It is no longer a fixture; the starter types are now seeded once here
(create-only-if-missing, so existing types and their milestones are untouched).
"""

import frappe

from seminary.install import seed_culminating_project_types


def execute():
    seed_culminating_project_types()
    print("Ensured starter Culminating Project Types exist.")
