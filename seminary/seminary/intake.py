"""Creating a role record for someone (ADR 068 §1).

Person first, always. A role record — Student, Instructor, Alumni Profile —
says *what someone does here*, not who they are, so it is created against a
Person that already exists rather than conjuring one from whatever fields the
caller happened to have.

Before this module each role controller resolved its own Person inside
`validate()`, which had two consequences. The obvious one: four seams that
disagreed about which attributes to pass, so the spine ended up with holes
nobody chose. The subtle one: `_validate_links()` runs *before* `validate()`,
so a `person` set there missed Frappe's `fetch_from` pass entirely and the
mirrors stayed empty until a second save.

The one exception is `Student Applicant`, and it is a real one: a guest has no
User and cannot write a Person, so intake captures onto the applicant and
`after_insert` promotes. ADR 042 §4 was right about that; what changed is that
it is now the single documented exception rather than one of two symmetric
"onboarding heads".
"""

import frappe
from frappe import _

from seminary.seminary import person as person_spine
from seminary.seminary import person_fields


def person_for_user(user, **attrs):
    """The Person behind a login, created if this is the first sighting."""
    return person_spine.ensure_person(user=user, **attrs)


def person_for_applicant(applicant):
    """The Person an admission should attach to.

    `Student Applicant.after_insert` promoted the intake fields already, so
    this is a lookup rather than a creation — and it must stay a lookup, or
    admission would fork a second identity for the same human.
    """
    person = frappe.db.get_value("Student Applicant", applicant, "person")
    if not person:
        frappe.throw(
            _(
                "Student Applicant {0} is not linked to a person record, so it "
                "cannot be admitted. Re-save the applicant to promote it."
            ).format(applicant)
        )
    return person


def make_student(person, **values):
    """A Student for an existing Person."""
    return _make("Student", person, values)


def make_instructor(person, **values):
    """An Instructor for an existing Person.

    `Instructor.user` is reqd, and the spine is where the User link lives, so
    it is taken from the Person unless the caller overrides it.
    """
    values.setdefault(
        "user", frappe.db.get_value("Person", getattr(person, "name", person), "user")
    )
    return _make("Instructor", person, values)


def make_alumni_profile(person, **values):
    """An Alumni Profile for an existing Person."""
    values.setdefault(
        "user", frappe.db.get_value("Person", getattr(person, "name", person), "user")
    )
    return _make("Alumni Profile", person, values)


def _make(doctype, person, values):
    # Callers hold a Person either way — a fresh `ensure_person` returns the
    # name, a controller usually has the document. Accept both rather than
    # making every call site remember which.
    person = getattr(person, "name", person)
    if not person:
        frappe.throw(
            _("A {0} needs a person record; create the Person first.").format(
                _(doctype)
            )
        )
    if not frappe.db.exists("Person", person):
        frappe.throw(_("Unknown person record {0}.").format(person))

    doc = frappe.new_doc(doctype)
    doc.person = person
    # Set the link before anything else so `_validate_links` — which runs ahead
    # of `validate` — populates every `fetch_from person.*` mirror on this
    # first save rather than the next one.
    doc.update(person_fields.mirror_values(doctype, person))
    doc.update(values)
    doc.insert(ignore_permissions=True)
    return doc
