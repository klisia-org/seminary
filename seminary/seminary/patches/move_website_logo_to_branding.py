"""Copy the public website logo from Seminary Settings to the new Website
Branding singleton on existing sites (ADR 061).

New installs get this via `seminary.install.after_install`; this covers sites
that already had a `Seminary Settings.website_logo` configured before Website
Branding landed. Create-only-if-empty (delegated to `seed_website_branding`),
so a site that has already configured Website Branding is never touched.

Runs post_model_sync so the Website Branding doctype exists; the old
`Seminary Settings.website_logo` column is intentionally kept (deprecated +
hidden), so reading it here is safe.
"""

from seminary.install import seed_website_branding, seed_website_navigation


def execute():
    seed_website_branding()
    seed_website_navigation()
    print("Ensured Website Branding logo + public navigation are seeded (ADR 061).")
