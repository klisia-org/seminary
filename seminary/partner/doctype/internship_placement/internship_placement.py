# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.partner import internship


class InternshipPlacement(Document):
    def validate(self):
        self._validate_dates()
        self._validate_site_count()
        self._populate_genders()

    def _populate_genders(self):
        """Surface the student's gender (read-only) to inform the registrar's
        approval. Sourced from the Person spine. The supervisor's gender is a
        fetch_from on site_supervisor.gender. Informative only — never enforced."""
        student = frappe.db.get_value(
            "Internship Application", self.internship_application, "student"
        )
        person = frappe.db.get_value("Student", student, "person") if student else None
        self.student_gender = (
            frappe.db.get_value("Person", person, "gender") if person else None
        )

    def after_insert(self):
        internship.snapshot_placement_requirements(self)
        internship.recompute_placement_hours(self.name)

    def on_update(self):
        internship.recompute_placement_hours(self.name)

    def on_trash(self):
        internship.recompute_application_hours(self.internship_application)

    def _validate_dates(self):
        if (
            self.actual_start
            and self.actual_end
            and self.actual_end < self.actual_start
        ):
            frappe.throw(_("Actual end date cannot be before the actual start date."))

    def _validate_site_count(self):
        """Honour the type's multi-site policy: a single placement unless the type
        allows multiple, and never more than max_sites."""
        cfg = frappe.db.get_value(
            "Internship Type",
            self.internship_type,
            ["allow_multi_site", "max_sites"],
            as_dict=True,
        )
        if not cfg:
            return
        others = frappe.db.count(
            "Internship Placement",
            {
                "internship_application": self.internship_application,
                "name": ("!=", self.name),
            },
        )
        if not cfg.allow_multi_site and others >= 1:
            frappe.throw(
                _("This internship type does not allow multiple placement sites.")
            )
        # A second (or later) site needs explicit registrar sign-off on the
        # application, so multi-site placements are a deliberate decision.
        if cfg.allow_multi_site and others >= 1:
            if not frappe.db.get_value(
                "Internship Application",
                self.internship_application,
                "multi_site_approved",
            ):
                frappe.throw(
                    _(
                        "Adding another placement site requires registrar multi-site "
                        "approval on the application (check 'Multi-Site Approved')."
                    )
                )
        if cfg.allow_multi_site and cfg.max_sites and others + 1 > cfg.max_sites:
            frappe.throw(
                _("This internship type allows at most {0} placement sites.").format(
                    cfg.max_sites
                )
            )
