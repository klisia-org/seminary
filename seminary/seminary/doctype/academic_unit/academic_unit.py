# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.website.website_generator import WebsiteGenerator

from seminary.seminary.utils import slugify


class AcademicUnit(WebsiteGenerator):
    def validate(self):
        self._validate_member_units()
        self._validate_parent_unit()
        self._set_web_route()

    def _validate_parent_unit(self):
        """Parent Unit forms the org hierarchy and must not create a cycle (a unit
        cannot be its own ancestor). Walks the ancestor chain defensively (ADR 062)."""
        if not self.parent_unit:
            return
        if self.parent_unit == self.name:
            frappe.throw(_("A unit cannot be its own Parent Unit."))
        seen = {self.name}
        cur = self.parent_unit
        while cur:
            if cur in seen:
                frappe.throw(
                    _(
                        "Parent Unit {0} would create a cycle in the unit hierarchy."
                    ).format(self.parent_unit)
                )
            seen.add(cur)
            cur = frappe.db.get_value("Academic Unit", cur, "parent_unit")

    def _set_web_route(self):
        """Publishable units get a stable /team/<slug> route. The `team/` prefix
        is deliberately distinct from the /our-team listing page (a static www
        page would otherwise shadow the dynamic unit routes nested under it).
        Built from the unit name so it stays readable; only generated when
        missing, never clobbered if an admin set one."""
        if self.publish_on_web and not self.route:
            self.route = "team/" + slugify(self.unit_name)

    def get_context(self, context):
        from seminary.seminary import faculty
        from seminary.seminary.seo import page_metatags

        context.no_cache = 1
        context.roster = faculty.get_unit_roster(self.name, public=True)
        context.show_salutations = bool(
            frappe.db.get_single_value("Website Branding", "show_team_salutations")
        )
        context.parents = [{"name": _("Our Team"), "route": "/our-team"}]
        context.title = self.unit_name
        context.metatags = page_metatags(
            self.unit_name,
            self.description or _("Faculty and members of {0}.").format(self.unit_name),
        )

    def _validate_member_units(self):
        """Member units belong only to an Academic Interdepartment, and must be
        real, distinct departments — not the unit itself and not another
        interdepartment (transitive resolution unions one level; nesting would
        recurse)."""
        if self.unit_type != "Academic Interdepartment":
            if self.member_units:
                frappe.throw(
                    _("Member Units apply only to an Academic Interdepartment.")
                )
            return

        seen = set()
        for row in self.member_units:
            if row.member_unit == self.name:
                frappe.throw(_("An interdepartment cannot list itself as a member."))
            if row.member_unit in seen:
                frappe.throw(
                    _("{0} is listed twice in Member Units.").format(row.member_unit)
                )
            seen.add(row.member_unit)
            member_type = frappe.db.get_value(
                "Academic Unit", row.member_unit, "unit_type"
            )
            if member_type == "Academic Interdepartment":
                frappe.throw(
                    _(
                        "Member Unit {0} is itself an interdepartment; list its "
                        "constituent departments instead."
                    ).format(row.member_unit)
                )


# ---------------------------------------------------------------------------
# Organizational hierarchy helpers (ADR 062)
# ---------------------------------------------------------------------------
# parent_unit is the org tree used for oversight roll-up — distinct from the
# Interdepartment member_units grouping (academic co-ownership; see faculty._resolve_units).


def descendant_units(unit: str) -> set:
    """``unit`` plus every unit beneath it in the parent_unit hierarchy (recursive,
    cycle-safe). Used to roll an overseer's scope down to sub-units."""
    if not unit:
        return set()
    result = {unit}
    frontier = [unit]
    while frontier:
        children = frappe.get_all(
            "Academic Unit", filters={"parent_unit": ("in", frontier)}, pluck="name"
        )
        fresh = [c for c in children if c not in result]
        result.update(fresh)
        frontier = fresh
    return result


def ancestor_units(unit: str) -> list:
    """The chain of parent units above ``unit``, nearest first (cycle-safe). Excludes
    ``unit`` itself."""
    chain: list = []
    if not unit:
        return chain
    seen = {unit}
    cur = frappe.db.get_value("Academic Unit", unit, "parent_unit")
    while cur and cur not in seen:
        chain.append(cur)
        seen.add(cur)
        cur = frappe.db.get_value("Academic Unit", cur, "parent_unit")
    return chain
