# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""aretenic decision 051: Desk stays tidy whichever apps a site has.

The guard test reads every shipped workspace, sidebar and desktop icon of our
apps installed on this site and fails when one targets an app outside its
owner's `required_apps`. Run on a site without oikonomos (testable.localhost),
it also proves seminary's own Desk ships nothing that needs it.
"""

import json
import pathlib
import re
from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase

from seminary import desk_nav
from seminary.seminary.financial import desk as billing_desk
from seminary.seminary.financial.backend import NullFinancialBackend

OUR_APPS = ("seminary", "aretenic", "oikonomos", "tamias", "logistes", "koinonia")
TARGET_MODULE_DOCTYPES = (
    "DocType",
    "Report",
    "Page",
    "Dashboard",
    "Workspace",
    "Dashboard Chart",
    "Number Card",
)


def _owner(link_type, name):
    """The app that owns a Desk target, or None when this site doesn't have it."""
    if link_type not in TARGET_MODULE_DOCTYPES:
        return "frappe"  # URL and the like: no app to depend on
    module = frappe.db.get_value(link_type, name, "module")
    if module is None:
        return None
    return frappe.db.get_value("Module Def", module, "app_name")


def _targets(path):
    """(gate key or None, link type, target) for every target in a Desk JSON file."""
    d = json.loads(path.read_text())
    kind = d.get("doctype")
    if kind == "Workspace":
        card = None
        for row in d.get("links") or []:
            if row.get("type") == "Card Break":
                card = row.get("label")
            else:
                yield f"card:{card}", row.get("link_type"), row.get("link_to")
        for row in d.get("shortcuts") or []:
            yield f"shortcut:{row.get('label')}", row.get("type"), row.get("link_to")
        for row in d.get("charts") or []:
            yield f"chart:{row.get('label') or row.get('chart_name')}", "Dashboard Chart", row.get(
                "chart_name"
            )
        for row in d.get("number_cards") or []:
            yield f"number_card:{row.get('label')}", "Number Card", row.get(
                "number_card_name"
            )
        for row in d.get("quick_lists") or []:
            yield f"quick_list:{row.get('label')}", "DocType", row.get("document_type")
    elif kind == "Workspace Sidebar":
        for row in d.get("items") or []:
            if row.get("type") != "Section Break":
                yield None, row.get("link_type"), row.get("link_to")
    elif kind == "Desktop Icon" and d.get("link_type") not in (None, "External"):
        yield None, d.get("link_type"), d.get("link_to")


class TestShippedDeskStaysInItsApp(IntegrationTestCase):
    def test_no_workspace_targets_an_app_it_does_not_require(self):
        gates = frappe.get_hooks("desk_block_gates") or {}
        installed = set(frappe.get_installed_apps())
        problems = []
        for app in (a for a in OUR_APPS if a in installed):
            allowed = {app, "frappe", *frappe.get_hooks("required_apps", app_name=app)}
            root = pathlib.Path(frappe.get_app_path(app))
            files = [
                *root.glob("*/workspace/*/*.json"),
                *root.glob("workspace_sidebar/*.json"),
                *root.glob("desktop_icon/*.json"),
            ]
            for path in files:
                workspace = json.loads(path.read_text()).get("name")
                for gate, link_type, target in _targets(path):
                    owner = _owner(link_type, target)
                    if owner in allowed:
                        continue
                    if gate and gate in (gates.get(workspace) or {}):
                        continue  # shown only while its app is in use
                    problems.append(
                        f"{path.relative_to(root.parent)}: {link_type} {target!r} "
                        f"belongs to {owner or 'an app not installed here'}"
                    )
        self.assertEqual(problems, [], "\n".join(problems))

    def test_registrar_tools_call_seminary_not_a_billing_app(self):
        from seminary.seminary.workspaces_bootstrap import REGISTRAR_TOOLS

        for tool in REGISTRAR_TOOLS:
            for method in re.findall(r"method:\s*'([\w.]+)'", tool["script"]):
                self.assertTrue(
                    method.startswith("seminary."), f"{tool['name']} calls {method}"
                )


class TestDeskPruning(IntegrationTestCase):
    WS = "_Test ADR051 Workspace"

    # Saving a Workspace commits (Frappe builds its sidebar), so the fixture is
    # made once and removed by hand rather than left to the test rollback.
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._drop()
        content = [
            {"id": "h1", "type": "header", "data": {"text": "Top", "col": 12}},
            {"id": "c1", "type": "card", "data": {"card_name": "Kept", "col": 4}},
            {"id": "s1", "type": "spacer", "data": {"col": 12}},
            {"id": "h2", "type": "header", "data": {"text": "Gone", "col": 12}},
            {"id": "c2", "type": "card", "data": {"card_name": "Missing", "col": 4}},
            {"id": "c3", "type": "card", "data": {"card_name": "Nowhere", "col": 4}},
            {"id": "s2", "type": "spacer", "data": {"col": 12}},
        ]
        doc = frappe.get_doc(
            {
                "doctype": "Workspace",
                "label": cls.WS,
                "title": cls.WS,
                "module": "Seminary",
                "public": 1,
                "content": json.dumps(content),
                "links": [
                    {"type": "Card Break", "label": "Kept"},
                    {
                        "type": "Link",
                        "label": "Users",
                        "link_type": "DocType",
                        "link_to": "User",
                    },
                    {
                        "type": "Link",
                        "label": "Ghost",
                        "link_type": "DocType",
                        "link_to": "_No Such DocType",
                    },
                    {"type": "Card Break", "label": "Missing"},
                    {
                        "type": "Link",
                        "label": "Ghost 2",
                        "link_type": "DocType",
                        "link_to": "_No Such DocType",
                    },
                ],
            }
        )
        doc.flags.ignore_links = True
        doc.insert(ignore_permissions=True)
        cls.content = content

    @classmethod
    def tearDownClass(cls):
        cls._drop()
        super().tearDownClass()

    @classmethod
    def _drop(cls):
        for doctype in ("Desktop Icon", "Workspace Sidebar", "Workspace"):
            if frappe.db.exists(doctype, cls.WS):
                frappe.delete_doc(doctype, cls.WS, ignore_permissions=True, force=True)
        frappe.db.commit()  # nosemgrep -- the insert above committed too

    def setUp(self):
        frappe.local.desk_nav_names = None
        frappe.clear_document_cache("Workspace", self.WS)

    def test_drops_missing_items_and_the_section_they_empty(self):
        out = desk_nav.prune_content(self.WS, self.content)
        self.assertEqual([b["id"] for b in out], ["h1", "c1"])

    def test_keeps_a_card_with_one_link_left(self):
        doc = desk_nav.pruned_workspace(frappe.get_doc("Workspace", self.WS))
        self.assertEqual([r.label for r in doc.links], ["Kept", "Users"])
        # the stored workspace is untouched
        self.assertEqual(len(frappe.get_doc("Workspace", self.WS).links), 5)

    def test_untouched_page_is_returned_as_is(self):
        blocks = self.content[:2]
        self.assertIs(desk_nav.prune_content(self.WS, blocks), blocks)

    def test_gate_hides_a_card_whose_app_is_installed(self):
        with mock.patch.object(
            desk_nav, "gate_open", lambda ws, kind, label: label != "Kept"
        ):
            out = desk_nav.prune_content(self.WS, self.content)
        self.assertEqual(out, [])

    def test_administrator_still_gets_the_other_cards(self):
        frappe.set_user("Administrator")
        page = desk_nav.get_desktop_page(
            json.dumps({"name": self.WS, "title": self.WS, "public": 1})
        )
        self.assertEqual([c["label"] for c in page["cards"]["items"]], ["Kept"])

    def test_sidebar_drops_dead_links_and_empty_sections(self):
        sidebars = {
            "x": {
                "items": [
                    {"type": "Section Break", "label": "A"},
                    {
                        "type": "Link",
                        "link_type": "DocType",
                        "link_to": "_No Such DocType",
                    },
                    {"type": "Section Break", "label": "B"},
                    {"type": "Link", "link_type": "DocType", "link_to": "User"},
                ]
            }
        }
        desk_nav.prune_sidebar_items(sidebars)
        self.assertEqual(
            [
                i["label"] if i["type"] == "Section Break" else i["link_to"]
                for i in sidebars["x"]["items"]
            ],
            ["B", "User"],
        )


class TestBillingEntry(IntegrationTestCase):
    def test_regenerate_button_hidden_without_a_backend_that_can(self):
        from seminary.seminary.financial import actions

        with mock.patch.object(actions, "get_financial_backend", NullFinancialBackend):
            self.assertFalse(actions.can_regenerate_current_term_charges())

    def _boot(self, active):
        bootinfo = frappe._dict(
            dock={
                "seminary": [
                    {"link_type": "Sidebar", "link_to": "Billing", "hidden": 0}
                ]
            },
            module_sidebars={
                "Billing": {"items": []},
                "Student Billing": {"items": []},
            },
        )
        sidebars = {"oikonomos": ["Student Billing"], "tamias": ["Billing"]}
        workspaces = {"oikonomos": ["Student Billing"], "tamias": ["Billing"]}
        with (
            mock.patch.object(billing_desk, "billing_sidebars", return_value=sidebars),
            mock.patch.object(
                billing_desk, "billing_workspaces", return_value=workspaces
            ),
            mock.patch.object(
                billing_desk, "active_financial_app", return_value=active
            ),
        ):
            billing_desk.boot_session(bootinfo)
        return bootinfo

    def test_previous_billing_link_goes_on_the_active_sidebar(self):
        bootinfo = self._boot("tamias")
        self.assertEqual(
            [i["link_to"] for i in bootinfo.module_sidebars["Billing"]["items"]],
            ["Student Billing"],
        )
        self.assertEqual(bootinfo.module_sidebars["Student Billing"]["items"], [])

    def test_only_the_active_apps_rail_entry_shows(self):
        rail = {
            r["link_to"]: r["hidden"] for r in self._boot("tamias").dock["seminary"]
        }
        # The retired entry had no row, so a hidden one is added; the active one is untouched.
        self.assertEqual(rail, {"Billing": 0, "Student Billing": 1})
        # An existing row for the retired entry is flagged rather than duplicated.
        rail = {
            r["link_to"]: r["hidden"] for r in self._boot("oikonomos").dock["seminary"]
        }
        self.assertEqual(rail, {"Billing": 1})


class TestSetupSections(IntegrationTestCase):
    """Companion apps' rows in the Setup sidebar (decision 088a §4)."""

    def _section(self, label, *links):
        return [{"type": "Section Break", "label": label, "child": 0}] + [
            {"type": "Link", "label": name, "link_to": name, "child": 1}
            for name in links
        ]

    def test_rows_land_in_their_section_or_after_the_named_one(self):
        items = (
            self._section("Community setup", "Cohort Type")
            + self._section("Web and communications", "Website Branding")
            + self._section("Integrations", "Pexels Settings")
        )
        bootinfo = frappe._dict(module_sidebars={"Seminary Setup": {"items": items}})
        specs = [
            (
                "oikonomos",
                {
                    "section": "Fees setup",
                    "after": "Community setup",
                    "links": [{"label": "Fee Category", "link_to": "Fee Category"}],
                },
            ),
            (
                "aretenic",
                {
                    "section": "Web and communications",
                    "links": [
                        {"label": "Portal Theme", "link_to": "Portal Theme"},
                        {"label": "Website Branding", "link_to": "Website Branding"},
                    ],
                },
            ),
        ]
        frappe.set_user("Administrator")
        with mock.patch.object(billing_desk, "setup_sections", return_value=specs):
            billing_desk.add_setup_sections(bootinfo)
        self.assertEqual(
            [i["label"] for i in bootinfo.module_sidebars["Seminary Setup"]["items"]],
            [
                "Community setup",
                "Cohort Type",
                "Fees setup",
                "Fee Category",
                "Web and communications",
                "Website Branding",
                "Portal Theme",
                "Integrations",
                "Pexels Settings",
            ],
        )

    def test_a_retired_billing_app_adds_nothing(self):
        hooks = {
            "oikonomos": [{"section": "Fees setup", "links": []}],
            "tamias": [{"section": "Fees setup", "links": []}],
            "aretenic": [{"section": "Web and communications", "links": []}],
        }
        with (
            mock.patch.object(
                billing_desk,
                "registered_financial_backends",
                return_value={"oikonomos": "", "tamias": ""},
            ),
            mock.patch.object(
                billing_desk, "active_financial_app", return_value="tamias"
            ),
            mock.patch.object(frappe, "get_installed_apps", return_value=list(hooks)),
            mock.patch.object(
                frappe,
                "get_hooks",
                side_effect=lambda name, app_name: hooks[app_name],
            ),
        ):
            self.assertEqual(
                [app for app, _spec in billing_desk.setup_sections()],
                ["tamias", "aretenic"],
            )


class TestSidebarWorkspaces(IntegrationTestCase):
    """A workspace opens in the sidebar that links it, not the first of its module (088a §1)."""

    def test_each_workspace_keeps_only_the_sidebars_that_link_it(self):
        from seminary.seminary import sidebar_workspaces

        module_ws = ["Seminary", "Academics", "Registrar"]

        def sidebar(*linked):
            return {
                "module": "Seminary",
                "workspaces": list(module_ws),
                "items": [
                    {"type": "Link", "link_type": "Workspace", "link_to": ws}
                    for ws in linked
                ],
            }

        bootinfo = frappe._dict(
            module_sidebars={
                "Seminary Chapel": sidebar(),
                "Seminary Registrar": sidebar("Registrar"),
                "Seminary Setup": sidebar("Seminary"),
                "Other": {"module": "Other", "workspaces": ["X"], "items": []},
            }
        )
        sidebar_workspaces.boot_session(bootinfo)
        self.assertEqual(
            {name: s["workspaces"] for name, s in bootinfo.module_sidebars.items()},
            {
                "Seminary Chapel": [],
                "Seminary Registrar": ["Registrar"],
                # Academics is linked nowhere, so it stays on the fallback.
                "Seminary Setup": ["Seminary", "Academics"],
                "Other": ["X"],
            },
        )
