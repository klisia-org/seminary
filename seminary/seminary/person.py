"""Person identity spine (ADR 042).

One Person per human; role doctypes (Student Applicant, Student, Instructor,
Alumni Profile) link to it and mirror its contact data read-only. This module
is the ONE mutation point: every onboarding path calls ensure_person() at its
head — there is no sync layer to catch records that skip it.

Identity is the opaque PERS id. Email is reachability data: it is only the
*match heuristic* used to find an existing Person, never a key, and changing
it never renames anything (in particular not the email-keyed Frappe User).
"""

import frappe
from frappe import _

EMAIL_CHANNEL = "Email"

# Spine-owned identity/contact fields settable through ensure/update.
IDENTITY_FIELDS = ("first_name", "middle_name", "last_name", "primary_mobile")
FILL_ONLY_FIELDS = ("language", "country", "image")


def normalize_email(value):
    return (value or "").strip().lower() or None


def find_person(email=None, user=None):
    """Locate an existing Person by User link or by email (primary or any
    Email channel address). Returns the Person name or None."""
    if user:
        name = frappe.db.get_value("Person", {"user": user})
        if name:
            return name
    email = normalize_email(email)
    if email:
        name = frappe.db.get_value("Person", {"primary_email": email})
        if name:
            return name
        name = frappe.db.get_value(
            "Person Channel Address",
            {"parenttype": "Person", "channel": EMAIL_CHANNEL, "value": email},
            "parent",
        )
        if name:
            return name
    return None


def ensure_person(
    email=None,
    *,
    user=None,
    first_name=None,
    middle_name=None,
    last_name=None,
    mobile=None,
    language=None,
    country=None,
    image=None,
):
    """Get-or-create the Person for an email/User; returns the Person name.

    Existing Persons are authoritative: passed values only fill blanks, they
    never clobber. (Pre-admission applicant edits, which ARE authoritative,
    go through update_person with overwrite=True instead.) A User mismatch is
    an identity conflict and throws — two different logins can never share a
    Person.
    """
    email = normalize_email(email)
    if user and not frappe.db.exists("User", user):
        user = None
    if not email and user:
        email = normalize_email(frappe.db.get_value("User", user, "email") or user)
    if not email and not user:
        frappe.throw(_("Cannot resolve a Person without an email or a User."))

    if user and not (first_name or last_name):
        lifted = frappe.db.get_value(
            "User", user, ["first_name", "middle_name", "last_name"], as_dict=True
        )
        if lifted:
            first_name = lifted.first_name
            middle_name = middle_name or lifted.middle_name
            last_name = last_name or lifted.last_name

    values = {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "primary_mobile": mobile,
        "language": language,
        "country": country,
        "image": image,
    }

    existing = find_person(email=email, user=user)
    if existing:
        person = frappe.get_doc("Person", existing)
        changed = _apply(person, values, email=email, overwrite=False)
        changed = _link_user(person, user) or changed
        if changed:
            person.save(ignore_permissions=True)
        return person.name

    person = frappe.new_doc("Person")
    person.update({field: value for field, value in values.items() if value})
    person.primary_email = email
    person.user = user
    if not person.first_name:
        # first_name is reqd; fall back to the email/user local part.
        person.first_name = (email or user).split("@")[0]
    person.insert(ignore_permissions=True)
    return person.name


def update_person(
    person_name,
    email=None,
    *,
    user=None,
    first_name=None,
    middle_name=None,
    last_name=None,
    mobile=None,
    language=None,
    country=None,
    image=None,
    overwrite=False,
):
    """Re-sync a known Person from a role record.

    With overwrite=True (pre-admission applicant re-promotion: the intake form
    is still the authoritative editor) identity fields are last-write-wins,
    including clears; fill-only fields and email still never blank out. With
    overwrite=False it behaves like ensure_person's fill-blanks pass.
    """
    person = frappe.get_doc("Person", person_name)
    values = {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "primary_mobile": mobile,
        "language": language,
        "country": country,
        "image": image,
    }
    changed = _apply(person, values, email=normalize_email(email), overwrite=overwrite)
    changed = _link_user(person, user) or changed
    if changed:
        person.save(ignore_permissions=True)
    return person.name


def _apply(person, values, email=None, overwrite=False):
    changed = False
    for field, value in values.items():
        current = person.get(field)
        if field in IDENTITY_FIELDS and overwrite:
            if field == "first_name" and not value:
                continue  # reqd — never blank
            if (value or "") != (current or ""):
                person.set(field, value or "")
                changed = True
        elif value and not current:
            person.set(field, value)
            changed = True
    if (
        email
        and email != person.primary_email
        and (overwrite or not person.primary_email)
    ):
        person.primary_email = email
        changed = True
    return changed


def _link_user(person, user):
    if not user:
        return False
    if person.user and person.user != user:
        frappe.throw(
            _(
                "Person {0} is already linked to User {1}; refusing to relink to {2}. "
                "Two different logins cannot share one Person."
            ).format(person.name, person.user, user)
        )
    if not person.user:
        person.user = user
        return True
    return False


def link_customer(person_name, customer):
    """Record the financial party on the Person (first link wins) and mirror
    the reverse link on the Customer's custom person field."""
    if not customer or not person_name:
        return
    if not frappe.db.get_value("Person", person_name, "customer"):
        frappe.db.set_value(
            "Person", person_name, "customer", customer, update_modified=False
        )
    if frappe.db.has_column("Customer", "person") and not frappe.db.get_value(
        "Customer", customer, "person"
    ):
        frappe.db.set_value(
            "Customer", customer, "person", person_name, update_modified=False
        )
