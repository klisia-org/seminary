# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class GraduationRequirementItem(Document):
    """A reusable library item. It is no longer submittable: instead of
    cancel/amend (impossible while programs and student snapshots reference it),
    a requirement is Retired via its workflow (Active <-> Retired). Retiring only
    hides it from the Program Graduation Requirement picker — existing references
    keep resolving by name (snapshot semantics, ADR 012). Deletion stays blocked
    by Frappe's link integrity while anything still points here.
    """

    pass
