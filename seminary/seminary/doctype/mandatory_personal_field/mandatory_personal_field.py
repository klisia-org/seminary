# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Which personal details a school insists on (ADR 067 section 9).

A thin curation layer over `person_fields.py`, not a second registry. Everything
except `mandatory` is read from there and rewritten on save: what the field is
called, whether a matching rule can read it, whether it is typed or worked out,
and where a human enters it. The school owns exactly one bit, which is the one
thing the code cannot know.

`mandatory` is not uniform enforcement, and that is deliberate. On an
application form it refuses the submission, because that is the one moment the
datum can be demanded of the person who has it. On a Person or an import row it
warns, because a rule enabled this week must not make a record created three
years ago unsaveable while somebody is correcting a phone number.

And the mentor half has no intake form at all -- an Instructor is created by
`seminary.seminary.intake` or by the importer, so there is no application to
demand anything on. For mentors the planner's readiness check is not a backstop
behind the enforcement; it *is* the enforcement.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class MandatoryPersonalField(Document):
    def validate(self):
        self.refresh_from_registry()
        self.guard_rules_that_depend_on_it()

    def refresh_from_registry(self):
        """Everything but `mandatory` belongs to the code.

        Rewritten on every save rather than trusted, because `read_only` is a
        form hint that a REST insert or an import never sees -- and a row
        claiming a rule can read a field it cannot would offer a criterion that
        can never match anybody.
        """
        from seminary.seminary import person_fields
        from seminary.seminary.discipleship import criteria

        spec = person_fields.SPEC_BY_PERSON_FIELD.get(self.person_field)
        if not spec:
            frappe.throw(
                _(
                    "{0} is not a personal detail this system records. This "
                    "list ships with the application; it is not something to "
                    "add to."
                ).format(frappe.bold(self.person_field or _("(empty)")))
            )

        self.field_label = label_for(spec)
        self.derived = 1 if spec.derived else 0
        self.automation_valid = (
            1
            if any(
                rule.requires_field == self.person_field
                for rule in criteria.registry().values()
            )
            else 0
        )
        self.sources = "\n".join(sources_for(spec))

    def guard_rules_that_depend_on_it(self):
        """Un-mandating a detail a live rule reads is refused, by name.

        Silently dropping a criterion changes who mentors whom, and that is not
        a side effect anybody should get from clearing a checkbox.
        """
        if self.mandatory or self.is_new():
            return
        before = self.get_doc_before_save()
        if not before or not before.mandatory:
            return

        types = cohort_types_depending_on(self.person_field)
        if types:
            frappe.throw(
                _(
                    "{0} is required because {1} matches students to mentors on "
                    "it. Remove that rule from {2} first — otherwise the rule "
                    "would quietly stop working and nobody would be told."
                ).format(
                    frappe.bold(self.field_label or self.person_field),
                    frappe.bold(", ".join(sorted(types))),
                    _("those Cohort Types") if len(types) > 1 else _("it"),
                )
            )


# ------------------------------------------------------------------ helpers


def label_for(spec):
    """A human name for a Person field, taken from the Person form itself so
    the two never drift."""
    df = frappe.get_meta("Person").get_field(spec.person_field)
    return _(df.label) if df and df.label else spec.person_field


def sources_for(spec):
    """Where a human can actually type this detail.

    Since ADR 068 the role records mirror the Person, so a mirror is not a
    source: nobody can type into it. What is left is the applicant form, the
    importer, and the Person record itself.
    """
    from seminary.seminary import person_fields

    out = []
    binding = spec.roles.get(person_fields.APPLICANT)
    if binding:
        out.append(_("Application form ({0})").format(binding.fieldname))
    if spec.derived:
        out.append(_("Worked out from the address; never typed"))
    else:
        out.append(_("Person record, by a Registrar or Seminary Manager"))
        out.append(_("Person Import Batch"))
    return out


def cohort_types_depending_on(person_field):
    """Active Cohort Types whose matching rules read this detail."""
    from seminary.seminary.discipleship import criteria

    handlers = [
        handler
        for handler in criteria.registry().values()
        if handler.requires_field == person_field
    ]
    if not handlers:
        return set()

    wanted = frappe.get_all(
        "Cohort Assignment Criterion",
        filters={"handler": ["in", [h.handler for h in handlers]], "is_active": 1},
        pluck="name",
    )
    if not wanted:
        return set()

    rows = frappe.get_all(
        "Cohort Type Criterion",
        filters={"criterion": ["in", wanted], "parenttype": "Cohort Type"},
        fields=["parent"],
        ignore_permissions=True,
    )
    if not rows:
        return set()
    return set(
        frappe.get_all(
            "Cohort Type",
            filters={"name": ["in", [r.parent for r in rows]], "is_active": 1},
            pluck="name",
        )
    )


def is_required(person_field):
    """Has the school insisted on this detail?

    Absent row means no: the seeder creates every row, so a missing one is a
    site that has not migrated rather than a silent yes.
    """
    return bool(
        frappe.db.get_value("Mandatory Personal Field", person_field, "mandatory")
    )


def required_fields():
    """Every Person field the school insists on, typed ones only.

    A derived field cannot be demanded on a form -- nobody types a latitude --
    so "required" for one of those means *resolvable*, which the planner's
    readiness check reports and no save ever refuses.
    """
    return set(
        frappe.get_all(
            "Mandatory Personal Field",
            filters={"mandatory": 1, "derived": 0},
            pluck="name",
        )
    )
