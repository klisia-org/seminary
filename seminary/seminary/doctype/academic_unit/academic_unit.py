# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.website.website_generator import WebsiteGenerator

from seminary.seminary.utils import slugify


class AcademicUnit(WebsiteGenerator):
    def validate(self):
        self._validate_member_units()
        self._set_web_route()

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
