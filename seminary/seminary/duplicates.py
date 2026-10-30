"""Finding and merging duplicate Persons and Partner Organizations (privatedocs/p022).

`ensure_person` matches by email, so one human with two addresses becomes two
Persons. A daily pass proposes pairs that may be one record, as Possible
Duplicate rows; staff merge a pair or mark it Not the Same, which is
remembered so it is never proposed again.

A merge keeps one record and moves every link to it with Frappe's merge
rename, then writes back what the removed record knew: blanks are filled from
it, and where the two disagree the person merging chose. Apps whose records
must stay one per Person (koinonia's Donor) merge them first, through the
`before_record_merge` hook: {"Person": "app.module.function"}, called with
(kept, removed, choices). `record_merge_differences` adds the app's own
disagreements to the merge screen, and `record_merge_conflicts` may refuse a
merge. `person_merge_roles` names roles that may merge Persons who hold no
academic or staff record.
"""

import json
import re

import frappe
from frappe import _
from frappe.model.rename_doc import rename_doc
from frappe.utils import cint, now_datetime
from unidecode import unidecode

from seminary.seminary.person import EMAIL_CHANNEL, normalize_email

MERGEABLE = ("Person", "Partner Organization")
MERGE_ROLES = ("Seminary Manager", "Registrar", "System Manager")
# Holding any of these makes a Person the registrar's to merge (§5).
ACADEMIC_RECORDS = ("Student Applicant", "Student", "Instructor", "Alumni Profile")
TITLE_FIELD = {"Person": "full_name", "Partner Organization": "organization_name"}
# A key shared by more people than this is an office phone or a family
# address, not a duplicate.
CROWDED_KEY = 6

# Written by the merge itself, or derived on save.
SKIPPED_FIELDS = {
    "Person": {
        "full_name",
        "primary_email",
        "user",
        "is_staff",
        "latitude",
        "longitude",
        "geocoded_on",
        "geocode_precision",
        "geo_status",
    },
    "Partner Organization": {
        "latitude",
        "longitude",
        "geocoded_on",
        "geocode_precision",
        "geo_status",
    },
}
NO_VALUE_TYPES = {
    "Section Break",
    "Column Break",
    "Tab Break",
    "HTML",
    "Button",
    "Heading",
    "Fold",
    "Table",
    "Table MultiSelect",
}
CONSENT_ORDER = {"Opted Out": 2, "Opted In": 1, "Unset": 0}


# --------------------------------------------------------------------------- #
# Finding pairs
# --------------------------------------------------------------------------- #
def _norm(value):
    return re.sub(r"[^a-z0-9]", "", unidecode(value or "").lower())


def _phone(value):
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 7 else None


def person_keys():
    """{key: set(person)} with a reason for each key."""
    keys = {}

    def add(kind, value, person):
        if value:
            keys.setdefault((kind, value), set()).add(person)

    for p in frappe.get_all(
        "Person",
        fields=[
            "name",
            "first_name",
            "last_name",
            "date_of_birth",
            "pincode",
            "primary_email",
            "primary_mobile",
        ],
    ):
        add("email", normalize_email(p.primary_email), p.name)
        add("phone", _phone(p.primary_mobile), p.name)
        name = _norm(p.first_name) + "|" + _norm(p.last_name)
        if _norm(p.first_name) and _norm(p.last_name):
            if p.date_of_birth:
                add("name_dob", f"{name}|{p.date_of_birth}", p.name)
            if _norm(p.pincode):
                add("name_postcode", f"{name}|{_norm(p.pincode)}", p.name)
    for row in frappe.get_all(
        "Person Channel Address",
        filters={"parenttype": "Person"},
        fields=["parent", "channel", "value"],
    ):
        if row.channel == EMAIL_CHANNEL:
            add("email", normalize_email(row.value), row.parent)
        else:
            add("phone", _phone(row.value), row.parent)
    return keys


def organization_keys():
    keys = {}

    def add(kind, value, org):
        if value:
            keys.setdefault((kind, value), set()).add(org)

    for o in frappe.get_all(
        "Partner Organization",
        fields=["name", "organization_name", "tax_id", "primary_email", "city"],
    ):
        add("tax_id", _norm(o.tax_id), o.name)
        add("email", normalize_email(o.primary_email), o.name)
        if _norm(o.organization_name):
            add("name_city", f"{_norm(o.organization_name)}|{_norm(o.city)}", o.name)
    return keys


REASONS = {
    "email": _("The same email address"),
    "phone": _("The same phone number"),
    "name_dob": _("The same name and date of birth"),
    "name_postcode": _("The same name and postcode"),
    "tax_id": _("The same tax ID"),
    "name_city": _("The same name and city"),
}


def pairs_from(keys):
    """{(a, b): set(reason)} for every pair sharing a key, a < b."""
    pairs = {}
    for (kind, _value), names in keys.items():
        if len(names) < 2 or len(names) > CROWDED_KEY:
            continue
        names = sorted(names)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                pairs.setdefault((a, b), set()).add(kind)
    return pairs


def pair_key(doctype, a, b):
    a, b = sorted((a, b))
    return f"{doctype}|{a}|{b}"


def _title(doctype, name):
    return frappe.db.get_value(doctype, name, TITLE_FIELD[doctype])


def refresh_pairs(doctype):
    """Bring the Open pairs for one doctype in line with today's records."""
    found = pairs_from(person_keys() if doctype == "Person" else organization_keys())
    existing = {
        r.pair_key: r
        for r in frappe.get_all(
            "Possible Duplicate",
            filters={"reference_doctype": doctype},
            fields=["name", "pair_key", "status", "reasons"],
        )
    }
    seen = set()
    for (a, b), kinds in found.items():
        key = pair_key(doctype, a, b)
        seen.add(key)
        reasons = "\n".join(str(REASONS[k]) for k in sorted(kinds))
        row = existing.get(key)
        if row:
            if row.status == "Open" and row.reasons != reasons:
                doc = frappe.get_doc("Possible Duplicate", row.name)
                doc.reasons = reasons
                doc.save(ignore_permissions=True)
            continue
        frappe.get_doc(
            {
                "doctype": "Possible Duplicate",
                "reference_doctype": doctype,
                "pair_key": key,
                "first": a,
                "first_title": _title(doctype, a),
                "second": b,
                "second_title": _title(doctype, b),
                "reasons": reasons,
            }
        ).insert(ignore_permissions=True)
    # An Open pair that no longer matches was fixed by an edit. A Not the
    # Same decision is kept, so the pair stays answered if it matches again.
    for key, row in existing.items():
        if key not in seen and row.status == "Open":
            frappe.delete_doc("Possible Duplicate", row.name, ignore_permissions=True)


def daily():
    for doctype in MERGEABLE:
        refresh_pairs(doctype)
    frappe.db.commit()


# --------------------------------------------------------------------------- #
# Who may merge
# --------------------------------------------------------------------------- #
def holds_academic_record(person):
    if cint(frappe.db.get_value("Person", person, "is_staff")):
        return True
    return any(frappe.db.exists(dt, {"person": person}) for dt in ACADEMIC_RECORDS)


def app_merge_roles():
    return set(frappe.get_hooks("person_merge_roles") or [])


def can_merge(pair, user=None):
    """Registrars merge any pair; an app's roles merge Persons who are only
    the app's (§5). Returns (allowed, why not)."""
    roles = set(frappe.get_roles(user))
    if roles & set(MERGE_ROLES):
        return True, None
    if pair.reference_doctype == "Person" and roles & app_merge_roles():
        if not (
            holds_academic_record(pair.first) or holds_academic_record(pair.second)
        ):
            return True, None
    return False, _(
        "This merge is the registrar's: one of these records is an applicant, "
        "student, instructor, alum or staff member, or an organisation."
    )


def _pair(name):
    frappe.has_permission("Possible Duplicate", "read", throw=True)
    pair = frappe.get_doc("Possible Duplicate", name)
    pair.check_permission("read")
    return pair


# --------------------------------------------------------------------------- #
# Comparing
# --------------------------------------------------------------------------- #
def _fmt(value):
    if value in (None, ""):
        return ""
    return str(value)


def field_differences(doctype, first, second):
    """Fields both records fill with different values: the person merging
    picks one. A field only one of them fills is taken without asking."""
    meta = frappe.get_meta(doctype)
    skipped = SKIPPED_FIELDS.get(doctype, set())
    out = []
    for df in meta.fields:
        if df.fieldtype in NO_VALUE_TYPES or df.fieldname in skipped or df.read_only:
            continue
        a, b = first.get(df.fieldname), second.get(df.fieldname)
        if df.fieldtype == "Check":
            if cint(a) == cint(b):
                continue
        elif not a or not b or _fmt(a) == _fmt(b):
            continue
        out.append(
            {
                "key": df.fieldname,
                "label": _(df.label),
                "first": _fmt(a),
                "second": _fmt(b),
            }
        )
    if doctype == "Person":
        if (
            first.primary_email
            and second.primary_email
            and first.primary_email != second.primary_email
        ):
            out.insert(
                0,
                {
                    "key": "primary_email",
                    "label": _("Primary Email"),
                    "first": first.primary_email,
                    "second": second.primary_email,
                },
            )
        if first.user and second.user:
            out.insert(
                0,
                {
                    "key": "user",
                    "label": _("Login (the other is disabled)"),
                    "first": first.user,
                    "second": second.user,
                },
            )
    return out


def conflicts(doctype, first, second):
    """Reasons the merge cannot go ahead: records that must stay one per
    Person or organisation, held by both."""
    out = []
    for field in frappe.get_all(
        "DocField",
        filters={"fieldtype": "Link", "options": doctype, "unique": 1},
        fields=["parent", "fieldname"],
    ) + frappe.get_all(
        "Custom Field",
        filters={"fieldtype": "Link", "options": doctype, "unique": 1},
        fields=["dt as parent", "fieldname"],
    ):
        a = frappe.db.get_value(field.parent, {field.fieldname: first.name})
        b = frappe.db.get_value(field.parent, {field.fieldname: second.name})
        if a and b:
            out.append(
                _("Both have a {0} ({1} and {2}). Resolve those first.").format(
                    _(field.parent), a, b
                )
            )
    for path in (frappe.get_hooks("record_merge_conflicts") or {}).get(doctype, []):
        out.extend(frappe.get_attr(path)(first, second) or [])
    return out


@frappe.whitelist()
def merge_preview(pair: str):
    pair = _pair(pair)
    if pair.status != "Open":
        frappe.throw(_("This pair is not open."))
    first = frappe.get_doc(pair.reference_doctype, pair.first)
    second = frappe.get_doc(pair.reference_doctype, pair.second)
    differences = field_differences(pair.reference_doctype, first, second)
    for path in (frappe.get_hooks("record_merge_differences") or {}).get(
        pair.reference_doctype, []
    ):
        differences.extend(frappe.get_attr(path)(first, second) or [])
    allowed, why = can_merge(pair)
    return {
        "doctype": pair.reference_doctype,
        "first": {
            "name": first.name,
            "title": first.get(TITLE_FIELD[pair.reference_doctype]),
        },
        "second": {
            "name": second.name,
            "title": second.get(TITLE_FIELD[pair.reference_doctype]),
        },
        "differences": differences,
        "conflicts": conflicts(pair.reference_doctype, first, second),
        "can_merge": allowed,
        "why_not": why,
    }


# --------------------------------------------------------------------------- #
# Deciding
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def not_the_same(pair: str):
    pair = _pair(pair)
    allowed, why = can_merge(pair)
    if not allowed:
        frappe.throw(why, frappe.PermissionError)
    pair.status = "Not the Same"
    pair.decided_by = frappe.session.user
    pair.decided_on = now_datetime()
    pair.save(ignore_permissions=True)


@frappe.whitelist()
def merge(pair: str, keep: str, choices=None):
    """Merge the pair into `keep`. `choices` maps a differing field to
    "first" or "second": whose value survives."""
    pair = _pair(pair)
    if pair.status != "Open":
        frappe.throw(_("This pair is not open."))
    allowed, why = can_merge(pair)
    if not allowed:
        frappe.throw(why, frappe.PermissionError)
    if keep not in (pair.first, pair.second):
        frappe.throw(_("Keep one of the two records."))
    choices = frappe.parse_json(choices) if choices else {}
    removed = pair.second if keep == pair.first else pair.first
    picked = {
        key: (pair.first if side == "first" else pair.second)
        for key, side in choices.items()
        if side in ("first", "second")
    }
    return merge_records(pair.reference_doctype, keep, removed, picked)


def merge_records(doctype, keep, remove, picked=None):
    """Merge `remove` into `keep`. `picked` maps a field to the record whose
    value survives; unnamed fields keep `keep`'s value and fill its blanks
    from `remove`. No permission check: callers decide who may."""
    picked = picked or {}
    kept = frappe.get_doc(doctype, keep)
    removed = frappe.get_doc(doctype, remove)
    problems = conflicts(doctype, kept, removed)
    if problems:
        frappe.throw("<br>".join(problems))

    for path in (frappe.get_hooks("before_record_merge") or {}).get(doctype, []):
        frappe.get_attr(path)(kept, removed, picked)

    removed_title = removed.get(TITLE_FIELD[doctype])
    if doctype == "Person":
        _dedupe_partner_contacts(keep, remove)
    rename_doc(
        doctype,
        remove,
        keep,
        merge=True,
        force=True,
        ignore_permissions=True,
        show_alert=False,
        rebuild_search=False,
    )

    kept = frappe.get_doc(doctype, keep)
    _write_back(kept, removed, picked)
    kept.flags.ignore_required_details = True
    kept.save(ignore_permissions=True)
    if doctype == "Person":
        _settle_logins(kept, removed, picked)

    frappe.get_doc(
        {
            "doctype": "Record Merge Log",
            "reference_doctype": doctype,
            "kept": keep,
            "kept_title": kept.get(TITLE_FIELD[doctype]),
            "removed": remove,
            "removed_title": removed_title,
            "merged_by": frappe.session.user,
            "merged_on": now_datetime(),
            "choices": json.dumps(picked, indent=1, sort_keys=True),
        }
    ).insert(ignore_permissions=True)
    _rekey_pairs(doctype, keep)
    return keep


def _write_back(kept, removed, picked):
    meta = frappe.get_meta(kept.doctype)
    skipped = SKIPPED_FIELDS.get(kept.doctype, set())
    for df in meta.fields:
        if df.fieldtype in NO_VALUE_TYPES or df.fieldname in skipped or df.read_only:
            continue
        if picked.get(df.fieldname) == removed.name:
            kept.set(df.fieldname, removed.get(df.fieldname))
        elif df.fieldtype == "Check":
            continue
        elif not kept.get(df.fieldname) and removed.get(df.fieldname):
            kept.set(df.fieldname, removed.get(df.fieldname))
    for df in meta.get_table_fields():
        _combine_rows(kept, removed, df.fieldname)
    if kept.doctype == "Person":
        _combine_emails(kept, removed, picked)


def _row_key(doctype, row):
    if doctype == "Person Channel Address":
        return (row.channel, (row.value or "").strip().lower())
    if doctype == "Person Consent":
        return (row.channel, row.category)
    if doctype == "Partner Contact":
        return (row.person,)
    meta = frappe.get_meta(doctype)
    return tuple(
        row.get(df.fieldname)
        for df in meta.fields
        if df.fieldtype not in NO_VALUE_TYPES
    )


def _combine_rows(kept, removed, fieldname):
    child = kept.meta.get_field(fieldname).options
    have = {_row_key(child, r): r for r in kept.get(fieldname)}
    for row in removed.get(fieldname):
        key = _row_key(child, row)
        mine = have.get(key)
        if mine is None:
            values = {
                k: v
                for k, v in row.as_dict().items()
                if k not in frappe.model.default_fields and k != "doctype"
            }
            if child == "Person Channel Address":
                values["is_primary"] = 0
            have[key] = kept.append(fieldname, values)
        elif child == "Person Consent":
            # The stricter answer stands: an opt-out on either record holds.
            if CONSENT_ORDER.get(row.status, 0) > CONSENT_ORDER.get(mine.status, 0):
                mine.status, mine.source, mine.recorded_on = (
                    row.status,
                    row.source,
                    row.recorded_on,
                )


def _combine_emails(kept, removed, picked):
    emails = [e for e in (kept.primary_email, removed.primary_email) if e]
    if picked.get("primary_email") == removed.name:
        kept.primary_email = removed.primary_email
    elif not kept.primary_email:
        kept.primary_email = removed.primary_email
    have = {
        (r.value or "").strip().lower()
        for r in kept.channel_addresses
        if r.channel == EMAIL_CHANNEL
    }
    for email in emails:
        if email.lower() not in have:
            kept.append(
                "channel_addresses",
                {"channel": EMAIL_CHANNEL, "value": email, "status": "Active"},
            )
            have.add(email.lower())


def _settle_logins(kept, removed, picked):
    """One login survives; the other is disabled, never deleted (§4)."""
    users = [u for u in (kept.user, removed.user) if u]
    if not users:
        return
    survivor = kept.user or removed.user
    if kept.user and removed.user and picked.get("user") == removed.name:
        survivor = removed.user
    for user in users:
        if user != survivor:
            frappe.db.set_value("User", user, "enabled", 0)
    if kept.user != survivor:
        kept.db_set("user", survivor)


def _dedupe_partner_contacts(keep, remove):
    """An organisation listing both Persons keeps one contact row: the
    rename would otherwise leave the same Person on it twice."""
    for row in frappe.get_all(
        "Partner Contact",
        filters={"parenttype": "Partner Organization", "person": remove},
        fields=["name", "parent"],
    ):
        if frappe.db.exists(
            "Partner Contact",
            {
                "parenttype": "Partner Organization",
                "parent": row.parent,
                "person": keep,
            },
        ):
            frappe.db.delete("Partner Contact", {"name": row.name})


def _rekey_pairs(doctype, keep):
    """The rename pointed the removed record's pairs at the survivor: drop
    the pair it now makes with itself and any repeat (a Not the Same answer
    wins over an Open one), then fix each key."""
    seen, drop, update = set(), [], []
    for row in frappe.get_all(
        "Possible Duplicate",
        filters={"reference_doctype": doctype},
        or_filters={"first": keep, "second": keep},
        fields=["name", "first", "second", "pair_key"],
        order_by="status asc, creation asc",
    ):
        key = pair_key(doctype, row.first, row.second)
        if row.first == row.second or key in seen:
            drop.append(row.name)
            continue
        seen.add(key)
        if key != row.pair_key:
            update.append((row, key))
    for name in drop:
        frappe.delete_doc(
            "Possible Duplicate", name, ignore_permissions=True, force=True
        )
    for row, key in update:
        a, b = sorted((row.first, row.second))
        frappe.db.set_value(
            "Possible Duplicate",
            row.name,
            {
                "pair_key": key,
                "first": a,
                "second": b,
                "first_title": _title(doctype, a),
                "second_title": _title(doctype, b),
            },
            update_modified=False,
        )
