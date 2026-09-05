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

from seminary.seminary.person_fields import (
    AUTHORED,
    SPEC_BY_ARG,
    SPEC_BY_PERSON_FIELD,
)

EMAIL_CHANNEL = "Email"

# Which fields exist, and whether each is authoritative or fill-only, is
# declared once in `person_fields.SPEC` (ADR 068). The `IDENTITY_FIELDS` /
# `FILL_ONLY_FIELDS` tuples that used to live here were a second, partial copy
# of that list — and `FILL_ONLY_FIELDS` was referenced nowhere at all, so the
# fill-only behaviour it described was really just `_apply`'s fallthrough.


def _values_from_kwargs(kwargs):
    """Map ensure/update keyword arguments onto Person fieldnames.

    Callers pass `locals()`. That looks sly, but it is the point: writing the
    dict out by hand means every attribute added to the registry has to be
    remembered in two more places, and forgetting one drops it *silently* —
    which is precisely how the address never reached the spine. Anything not
    named in the registry (email, user, overwrite, stray locals) is ignored.
    """
    return {
        SPEC_BY_ARG[arg].person_field: value
        for arg, value in kwargs.items()
        if arg in SPEC_BY_ARG
    }


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
    gender=None,
    date_of_birth=None,
    nationality=None,
    phonetic_name=None,
    mailing_country=None,
    address_line_1=None,
    address_line_2=None,
    city=None,
    state=None,
    pincode=None,
    blood_group=None,
    marital_status=None,
    ethnicity=None,
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

    values = _values_from_kwargs(locals())

    existing = find_person(email=email, user=user)
    if existing:
        person = frappe.get_doc("Person", existing)
        changed = _apply(person, values, email=email, overwrite=False)
        changed = _link_user(person, user) or changed
        if changed:
            person.save(ignore_permissions=True)
        return person.name

    person = frappe.new_doc("Person")
    # The same Link guard `_apply` uses: this branch writes straight onto a new
    # doc rather than going through it, so without this an applicant's gender
    # literal would still raise LinkValidationError on a localised site.
    person.update(
        {
            field: value
            for field, value in values.items()
            if value and _link_target_exists(field, value)
        }
    )
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
    gender=None,
    date_of_birth=None,
    nationality=None,
    phonetic_name=None,
    mailing_country=None,
    address_line_1=None,
    address_line_2=None,
    city=None,
    state=None,
    pincode=None,
    blood_group=None,
    marital_status=None,
    ethnicity=None,
    overwrite=False,
):
    """Re-sync a known Person from a role record.

    With overwrite=True (pre-admission applicant re-promotion: the intake form
    is still the authoritative editor) identity fields are last-write-wins,
    including clears; fill-only fields and email still never blank out. With
    overwrite=False it behaves like ensure_person's fill-blanks pass.
    """
    values = _values_from_kwargs(locals())
    person = frappe.get_doc("Person", person_name)
    changed = _apply(person, values, email=normalize_email(email), overwrite=overwrite)
    changed = _link_user(person, user) or changed
    if changed:
        person.save(ignore_permissions=True)
    return person.name


def _apply(person, values, email=None, overwrite=False):
    """Write `values` (keyed by Person fieldname) with the registry's semantics.

    An AUTHORED field is last-write-wins when the caller is authoritative, but
    a `never_blank` one is never cleared. Everything else only fills a blank —
    an existing Person stays authoritative over it.
    """
    changed = False
    for field, value in values.items():
        spec = SPEC_BY_PERSON_FIELD[field]
        if value and not _link_target_exists(field, value):
            continue
        current = person.get(field)
        if spec.mode == AUTHORED and overwrite:
            if spec.never_blank and not value:
                continue
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


def _link_target_exists(field, value):
    """Guard every Link write at the one mutation point.

    `Student Applicant.gender` was a Select of the literals Male/Female while
    `Person.gender` is a Link to Gender; ADR 068 §9 made both Links so a
    curated Gender table is actually reachable. The guard stays, because the
    hand-off is still not guaranteed: Frappe's setup wizard seeds genders
    through `_()`, so a site set up in another language has rows named in that
    language and an imported or legacy literal may match none of them. Handing
    that to a Link raises LinkValidationError, and the caller is an admissions
    path that must not break on it.

    Skipping is deliberate over throwing: the datum is then simply absent, and
    absence is what the ADR 067 readiness pre-flight is built to surface. This
    lives here rather than at each caller because repeating the guard per
    hand-off is how the spine ended up with four disagreeing versions of every
    other rule (ADR 068).
    """
    df = frappe.get_meta("Person").get_field(field)
    if not df or df.fieldtype != "Link":
        return True
    return bool(frappe.db.exists(df.options, value))


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


# link_customer (Person <-> Customer) moved to the oikonomos bridge
# (oikonomos.financial.customer_person.link_customer). Customer is an ERPNext
# doctype, so the link is owned there; the Person spine here stays Frappe-only.
# (The Donor <-> Person link in integrations/giving.py is the sibling pattern.)


def set_channel_address(person_name, channel, value):
    """Upsert (or clear, when value is blank) a non-primary channel address on a
    Person — e.g. an instructor's WhatsApp number for portal contact. Primary
    addresses are owned by the identity sync (primary_mobile/email mirrors) and
    are left untouched. Returns the stored value (None when cleared)."""
    if not person_name or not channel:
        return None
    if not frappe.db.exists("Communication Channel", channel):
        frappe.throw(_("Unknown channel {0}.").format(channel))
    person = frappe.get_doc("Person", person_name)
    value = (value or "").strip() or None
    row = next(
        (
            r
            for r in person.channel_addresses
            if r.channel == channel and not r.is_primary
        ),
        None,
    )
    if value:
        if row:
            row.value = value
            row.status = "Active"
        else:
            person.append(
                "channel_addresses",
                {"channel": channel, "value": value, "status": "Active"},
            )
    elif row:
        person.channel_addresses.remove(row)
    else:
        return None
    person.save(ignore_permissions=True)
    return value
