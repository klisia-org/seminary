# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class AcademicTerm(Document):
    def autoname(self):
        self.name = (
            self.academic_year + " ({})".format(self.term_name)
            if self.term_name
            else ""
        )

    def validate(self):
        self.set_title()
        self.validate_duplication()
        self.validate_dates()
        self.validate_term_against_year()
        self.enforce_single_current_term()

    def enforce_single_current_term(self):
        """`iscurrent_acterm` names one term app-wide.

        Everything that asks "what term is it" reads this flag, so two terms
        carrying it is not a richer answer, it is no answer -- whichever row the
        query happened to return first. `tasks._update_term_flags` maintains it
        from the dates; this is the guard for the other way in, a person ticking
        the box by hand.

        Ticking it here means it: the other terms are cleared rather than the
        save refused, because a registrar setting the current term is stating
        something, not asking permission.
        """
        if not self.iscurrent_acterm:
            return
        others = frappe.get_all(
            "Academic Term",
            filters={"iscurrent_acterm": 1, "name": ("!=", self.name or "")},
            pluck="name",
        )
        for name in others:
            frappe.db.set_value(
                "Academic Term", name, "iscurrent_acterm", 0, update_modified=False
            )

    def set_title(self):
        self.title = (
            self.academic_year + " ({})".format(self.term_name)
            if self.term_name
            else ""
        )

    def validate_duplication(self):
        # Check if entry with same academic_year and the term_name already exists
        term = frappe.db.sql(
            """select name from `tabAcademic Term` where academic_year= %s and term_name= %s
		and docstatus<2 and name != %s""",
            (self.academic_year, self.term_name, self.name),
        )
        if term:
            frappe.throw(
                _(
                    "An academic term with this 'Academic Year' {0} and 'Term Name' {1} already exists. Please modify these entries and try again."
                ).format(self.academic_year, self.term_name)
            )

    def validate_dates(self):
        # Check that start of academic year is earlier than end of academic year
        if (
            self.term_start_date
            and self.term_end_date
            and getdate(self.term_start_date) > getdate(self.term_end_date)
        ):
            frappe.throw(
                _(
                    "The Term End Date cannot be before the Term Start Date. Please correct the dates and try again."
                )
            )

    def validate_term_against_year(self):
        # Check that the start of the term is not before the start of the academic year
        # and end of term is not after the end of the academic year"""

        year = frappe.db.get_value(
            "Academic Year",
            self.academic_year,
            ["year_start_date", "year_end_date"],
            as_dict=1,
        )

        if (
            self.term_start_date
            and getdate(year.year_start_date)
            and (getdate(self.term_start_date) < getdate(year.year_start_date))
        ):
            frappe.throw(
                _("The Term cannot start before the Academic Year {0}").format(
                    frappe.bold(self.academic_year)
                )
            )

        if (
            self.term_end_date
            and getdate(year.year_end_date)
            and (getdate(self.term_end_date) > getdate(year.year_end_date))
        ):
            frappe.throw(
                _("The Term cannot end after the Academic Year {0}").format(
                    frappe.bold(self.academic_year)
                )
            )


@frappe.whitelist()
def get_academic_year_context(academic_year, exclude_term=None):
    """Return year date range and sibling terms to help users pick valid term dates."""
    year = frappe.db.get_value(
        "Academic Year",
        academic_year,
        ["year_start_date", "year_end_date"],
        as_dict=1,
    )
    if not year:
        return {"year": None, "terms": []}

    filters = {"academic_year": academic_year}
    if exclude_term:
        filters["name"] = ["!=", exclude_term]

    terms = frappe.get_all(
        "Academic Term",
        filters=filters,
        fields=["name", "term_name", "term_start_date", "term_end_date"],
        order_by="term_start_date asc",
    )

    return {"year": year, "terms": terms}
