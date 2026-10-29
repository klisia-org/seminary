"""The seminary's public pages and their switch (decisions/093).

Seminary Settings > Public Website turns off the home, Programs, Our Team and
What We Believe pages and the Program / Academic Unit web pages, for schools
whose website lives elsewhere and for apps that own the site's public pages.
Website Branding, the navbar and the footer keep serving every page.
"""

import frappe

# What the install seeds into Website Settings (061). Turning the switch off
# removes these rows only while they are still exactly as seeded.
TOP_BAR_ITEMS = (
    ("Home", "/"),
    ("Our Programs", "/programs"),
    ("Who We Are", "/our-team"),
    ("What We Believe", "/what-we-believe"),
    ("Contact", "/contact"),
)
FOOTER_ITEMS = (("Privacy", "/privacy"),)
HOME_PAGE = "home"


def enabled():
    # Uncached: a save in the same process must take effect at once.
    return bool(
        frappe.db.get_single_value("Seminary Settings", "public_website", cache=False)
    )


def require():
    """Raise a 404 from a public page's controller while the switch is off."""
    if not enabled():
        raise frappe.PageDoesNotExistError


def switched(settings):
    """Seminary Settings.on_update: act when the switch changes."""
    before = settings.get_doc_before_save()
    if not before or bool(before.public_website) == bool(settings.public_website):
        return
    if settings.public_website:
        from seminary.install import seed_website_navigation, seed_website_pages

        # Inside the settings save: no commits of their own.
        seed_website_navigation(commit=False)
        seed_website_pages(commit=False)
        _publish_starter_pages(1)
    else:
        tidy()


def tidy():
    """Undo what the install seeded and nobody has changed since."""
    ws = frappe.get_single("Website Settings")
    changed = False
    if ws.home_page == HOME_PAGE:
        ws.home_page = ""
        changed = True
    for table, seeded in (
        ("top_bar_items", TOP_BAR_ITEMS),
        ("footer_items", FOOTER_ITEMS),
    ):
        keep = [
            row
            for row in ws.get(table)
            if (row.label, row.url) not in seeded
            or row.parent_label
            or row.open_in_new_tab
        ]
        if len(keep) != len(ws.get(table)):
            ws.set(table, keep)
            changed = True
    if changed:
        ws.flags.ignore_permissions = True
        ws.save()

    _publish_starter_pages(0)


def _publish_starter_pages(published):
    """Publish or unpublish the starter Web Pages still exactly as seeded."""
    from seminary.install import STARTER_WEB_PAGES

    for page in STARTER_WEB_PAGES:
        name = frappe.db.get_value(
            "Web Page",
            {
                "route": page["route"],
                "published": 1 - published,
                "main_section": page["main_section"],
            },
        )
        if name:
            frappe.db.set_value("Web Page", name, "published", published)
