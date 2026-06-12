"""Seed the default Portal Messaging Rules on existing sites (ADR 043).

New installs get these via ``seminary.install.after_install``; this covers
sites already running before configurable portal messaging landed. Create-only-
if-empty, so a seminary that has already configured rules is never touched.
"""

from seminary.install import seed_portal_messaging_rules


def execute():
    seed_portal_messaging_rules()
    print("Ensured default Portal Messaging Rules exist.")
