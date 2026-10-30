"""The Public Website switch (093): the seminary's public pages go, the
branding and the portal stay, and Website Settings is tidied."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response
from frappe.website.utils import clear_website_cache

from seminary.install import STARTER_WEB_PAGES
from seminary.overrides import apply_branding, bar_ink, website_languages
from seminary.seminary import public_website


def _status(path):
    had_request = hasattr(frappe.local, "request")
    clear_website_cache()
    set_request(method="GET", path=path)
    try:
        return get_response(path).status_code
    finally:
        # Frappe reads `frappe.local.request.environ` whenever the attribute
        # exists, so leave it as absent as it was.
        if not had_request:
            del frappe.local.request


def _switch(on):
    settings = frappe.get_single("Seminary Settings")
    settings.public_website = on
    settings.save(ignore_permissions=True)


def _seeded_website_settings():
    ws = frappe.get_single("Website Settings")
    ws.home_page = public_website.HOME_PAGE
    ws.set("top_bar_items", [])
    ws.set("footer_items", [])
    for label, url in public_website.TOP_BAR_ITEMS:
        ws.append("top_bar_items", {"label": label, "url": url})
    ws.append("top_bar_items", {"label": "Library", "url": "/library"})
    ws.append("top_bar_items", {"label": "Who We Are", "url": "/about-us"})
    for label, url in public_website.FOOTER_ITEMS:
        ws.append("footer_items", {"label": label, "url": url})
    ws.save(ignore_permissions=True)


def _starter_page(route, edited=False):
    seed = next(p for p in STARTER_WEB_PAGES if p["route"] == route)
    name = frappe.db.get_value("Web Page", {"route": route})
    doc = frappe.get_doc("Web Page", name) if name else frappe.new_doc("Web Page")
    doc.update(
        {
            "title": seed["title"],
            "route": route,
            "published": 1,
            "content_type": "Rich Text",
            "main_section": "<p>Our own words.</p>" if edited else seed["main_section"],
        }
    )
    doc.save(ignore_permissions=True)
    return doc.name


class TestPublicWebsite(IntegrationTestCase):
    def setUp(self):
        _switch(1)

    def tearDown(self):
        frappe.clear_cache()

    def test_pages_404_while_off(self):
        self.assertEqual(_status("our-team"), 200)
        _switch(0)
        for path in ("home", "programs", "our-team", "what-we-believe", "program"):
            self.assertEqual(_status(path), 404, path)

    def test_portal_and_login_stay(self):
        _switch(0)
        frappe.set_user("Guest")
        try:
            self.assertEqual(_status("login"), 200)
        finally:
            frappe.set_user("Administrator")

    def test_off_tidies_only_what_is_unchanged(self):
        _seeded_website_settings()
        placeholder = _starter_page("our-history")
        edited = _starter_page("privacy", edited=True)

        _switch(0)

        ws = frappe.get_single("Website Settings")
        self.assertFalse(ws.home_page)
        self.assertEqual(
            [(r.label, r.url) for r in ws.top_bar_items],
            [("Library", "/library"), ("Who We Are", "/about-us")],
        )
        self.assertFalse(ws.footer_items)
        self.assertEqual(frappe.db.get_value("Web Page", placeholder, "published"), 0)
        self.assertEqual(frappe.db.get_value("Web Page", edited, "published"), 1)

    def test_on_again_seeds_what_is_empty(self):
        _seeded_website_settings()
        placeholder = _starter_page("our-history")
        _switch(0)
        _switch(1)

        ws = frappe.get_single("Website Settings")
        self.assertEqual(ws.home_page, public_website.HOME_PAGE)
        # The top bar kept staff rows, so it is not empty and is not re-seeded.
        self.assertEqual(len(ws.top_bar_items), 2)
        self.assertEqual(
            [(r.label, r.url) for r in ws.footer_items],
            list(public_website.FOOTER_ITEMS),
        )
        self.assertEqual(frappe.db.get_value("Web Page", placeholder, "published"), 1)

    def test_off_keeps_a_home_page_staff_chose(self):
        ws = frappe.get_single("Website Settings")
        ws.home_page = "about"
        ws.save(ignore_permissions=True)
        _switch(0)
        self.assertEqual(
            frappe.db.get_single_value("Website Settings", "home_page"), "about"
        )


class TestPortalLink(IntegrationTestCase):
    def _navbar(self, link):
        branding = frappe.get_single("Website Branding")
        branding.portal_link = link
        return frappe.render_template(
            "templates/includes/seminary_chrome/navbar.html", {"branding": branding}
        )

    def test_link_follows_branding(self):
        self.assertIn(
            'href="/klisia"',
            self._navbar("/klisia").replace(frappe.utils.get_url(), ""),
        )

    def test_empty_link_hides_it(self):
        self.assertNotIn(
            ">Portal<", self._navbar("").replace(" ", "").replace("\n", "")
        )


class TestBarColours(IntegrationTestCase):
    """061a: the navbar and footer take their own background and a derived ink."""

    def _head(self, **fields):
        branding = frappe.get_single("Website Branding")
        branding.update(fields)
        branding.save(ignore_permissions=True)
        context = frappe._dict()
        apply_branding(context)
        return context.get("head_html") or ""

    def test_ink_follows_contrast(self):
        self.assertEqual(bar_ink("#0d3049"), "#ffffff")
        self.assertEqual(bar_ink("#fff"), "#1a2330")
        self.assertEqual(bar_ink("#ffffff", "#000000"), "#000000")
        # A light Text colour would vanish on a white bar.
        self.assertEqual(bar_ink("#ffffff", "#eeeeee"), "#1a2330")
        self.assertIsNone(bar_ink(""))
        self.assertIsNone(bar_ink("not-a-colour"))

    def test_blank_bars_follow_primary(self):
        head = self._head(
            primary_color="#0d3049", navbar_background="", footer_background=""
        )
        self.assertNotIn("--brand-navbar-bg", head)
        self.assertNotIn("--brand-footer-bg", head)
        self.assertIn("--brand-navbar-ink: #ffffff;", head)
        self.assertIn("--brand-footer-ink: #ffffff;", head)

    def test_light_navbar_gets_dark_ink(self):
        head = self._head(
            primary_color="#0d3049",
            text_color="",
            navbar_background="#ffffff",
            footer_background="",
        )
        self.assertIn("--brand-navbar-bg: #ffffff;", head)
        self.assertIn("--brand-navbar-ink: #1a2330;", head)
        self.assertIn("--brand-footer-ink: #ffffff;", head)


class TestLanguagePicker(IntegrationTestCase):
    """061b: guests choose among the languages Website Branding lists."""

    def _branding(self, *codes):
        branding = frappe.get_single("Website Branding")
        branding.set("website_languages", [{"language": c} for c in codes])
        return branding

    def test_choices_keep_the_listed_order(self):
        frappe.db.set_value("Language", "pt-BR", "enabled", 1)
        choices = website_languages(self._branding("pt-BR", "en"))
        self.assertEqual([code for code, _ in choices], ["pt-BR", "en"])

    def test_one_language_or_a_disabled_one_leaves_no_choice(self):
        self.assertEqual(website_languages(self._branding("en")), [])
        frappe.db.set_value("Language", "pt-BR", "enabled", 0)
        self.assertEqual(website_languages(self._branding("en", "pt-BR")), [])

    def test_navbar_marks_the_current_language(self):
        render = lambda choices: frappe.render_template(  # noqa: E731
            "templates/includes/seminary_chrome/navbar.html",
            {
                "branding": self._branding(),
                "website_languages": choices,
                "current_language": "es",
            },
        )
        html = render([("en", "English"), ("es", "Español")])
        self.assertIn('<option value="es" selected>Español</option>', html)
        self.assertIn("preferred_language=", html)
        # Frappe moves page scripts to the end of <body>, so the script must not
        # hide its own parent: for a logged-in user that blanked the whole page.
        self.assertNotIn("currentScript", html)
        self.assertNotIn("sem-navbar__lang", render([]))


class TestRootForLoggedInUsers(IntegrationTestCase):
    """093a: the site's public home page wins over the role portals."""

    def _home_for_student(self, home_page):
        from frappe.website.utils import get_home_page

        frappe.db.set_single_value("Website Settings", "home_page", home_page)
        user = "zz-093a-student@example.com"
        if not frappe.db.exists("User", user):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": user,
                    "first_name": "Student",
                    "user_type": "Website User",
                    "send_welcome_email": 0,
                    "roles": [{"role": "Student"}],
                }
            ).insert(ignore_permissions=True)
        frappe.set_user(user)
        frappe.cache.hdel("home_page", user)
        try:
            return get_home_page()
        finally:
            frappe.set_user("Administrator")

    def test_public_home_page_for_everyone(self):
        self.assertEqual(self._home_for_student("welcome"), "welcome")

    def test_role_portal_without_one(self):
        self.assertEqual(self._home_for_student(""), "seminary/courses")
