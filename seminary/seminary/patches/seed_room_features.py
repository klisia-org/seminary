"""Seed the starter Room Features on existing sites (ADR 035).

New installs get these via ``seminary.install.after_install``; this covers
sites already running before Room Features landed. Create-only-if-missing, so
a seminary's curated catalog is never touched.
"""

from seminary.install import seed_room_features


def execute():
    seed_room_features()
    print("Ensured starter Room Features exist.")
