"""Declarative communication triggers (ADR 044).

A Communication Trigger watches a doctype for a condition (status,
workflow_state, any field {operator} {value}) and, when it comes true, sends a
Communication Template to configured recipients (role / user / person resolved
from a document field) through the consent-aware, rate-limited ledger
(ADR 043). Write the plumbing once — scholarship approved, hold released,
application status changed — configure the rest on the desk.

Save triggers are EDGE-triggered: they fire when the conditions flip from
false to true, never again while they merely stay true. With
once_per_document the idempotency key additionally caps it at one send per
document per recipient, ever.

Wired through wildcard doc_events; the cached watched-doctype set makes the
non-watched 99% of saves a dict-lookup no-op.
"""

import frappe
from frappe.utils import cint, flt

CACHE_KEY = "communication_trigger_doctypes"
SKIP_DOCTYPES = {"Communication Log", "Communication Trigger", "Version", "ToDo"}


def clear_trigger_cache():
    frappe.cache().delete_value(CACHE_KEY)


def _watched_doctypes():
    def generator():
        return frappe.get_all(
            "Communication Trigger",
            filters={"enabled": 1},
            distinct=True,
            pluck="reference_doctype",
        )

    return frappe.cache().get_value(CACHE_KEY, generator) or []


def process(doc, method=None):
    """Wildcard doc_events entry point. Must stay cheap: every save in the
    system passes through here."""
    if (
        doc.doctype in SKIP_DOCTYPES
        or getattr(doc, "flags", None)
        and doc.flags.in_patch
    ):
        return
    if frappe.flags.in_install or frappe.flags.in_migrate:
        return
    if not frappe.db.table_exists("Communication Trigger", cached=True):
        return
    if doc.doctype not in _watched_doctypes():
        return
    for name in frappe.get_all(
        "Communication Trigger",
        filters={"enabled": 1, "reference_doctype": doc.doctype},
        pluck="name",
    ):
        try:
            _evaluate(frappe.get_doc("Communication Trigger", name), doc, method)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"Communication Trigger {name} failed"
            )


def _evaluate(trigger, doc, method):
    previous = doc.get_doc_before_save()
    is_insert = previous is None and method in ("on_update", "after_insert")

    if trigger.trigger_on == "Insert":
        if not is_insert or not _matches(trigger, doc):
            return
    elif trigger.trigger_on == "Save":
        if method not in ("on_update", "on_update_after_submit"):
            return
        if not _matches(trigger, doc):
            return
        # Edge detection: skip if the conditions were already true before.
        if not is_insert and previous is not None and _matches(trigger, previous):
            return
    elif trigger.trigger_on == "Submit":
        if method != "on_submit" or not _matches(trigger, doc):
            return
    elif trigger.trigger_on == "Cancel":
        if method != "on_cancel" or not _matches(trigger, doc):
            return
    else:
        return

    _fire(trigger, doc)


def _matches(trigger, doc):
    return all(
        _check(doc.get(cond.fieldname), cond.operator, cond.value)
        for cond in trigger.conditions
    )


def _check(current, operator, expected):
    if operator == "Is Set":
        return bool(current)
    if operator == "Is Not Set":
        return not current
    if operator == "In":
        wanted = [v.strip() for v in (expected or "").split(",")]
        return str(current or "") in wanted
    if operator == "Contains":
        return (expected or "") in str(current or "")
    if operator in ("Greater Than", "Greater or Equal", "Less Than", "Less or Equal"):
        a, b = flt(current), flt(expected)
        return {
            "Greater Than": a > b,
            "Greater or Equal": a >= b,
            "Less Than": a < b,
            "Less or Equal": a <= b,
        }[operator]
    if operator == "Not Equals":
        return str(current or "") != str(expected or "")
    return str(current or "") == str(expected or "")  # Equals


def _fire(trigger, doc):
    from seminary.seminary import comms

    for recipient in trigger.recipients:
        for person_name, to_address in _resolve_recipient(recipient, doc):
            if not person_name and not to_address:
                continue
            dedupe = None
            if cint(trigger.once_per_document):
                who = person_name or to_address
                dedupe = (
                    f"comm-trigger::{trigger.name}::{doc.doctype}::{doc.name}"
                    f"::{who}::{recipient.channel}"
                )
            try:
                comms.send(
                    person_name,
                    trigger.template,
                    to_address=to_address,
                    channel=recipient.channel or "Email",
                    reference_doctype=doc.doctype,
                    reference_name=doc.name,
                    triggered_by=f"communication-trigger::{trigger.name}",
                    dedupe_key=dedupe,
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Communication Trigger {trigger.name}: send failed for {doc.name}",
                )


def _resolve_recipient(recipient, doc):
    """Yield (person_name, to_address) pairs. Role/User recipients get a
    Person ensured from their User (the ADR 042 staff seam); a Document Field
    resolves through whatever it points at."""
    from seminary.seminary import person as person_spine

    if recipient.recipient_type == "User":
        return [(person_spine.ensure_person(user=recipient.user), None)]

    if recipient.recipient_type == "Role":
        from seminary.seminary.comms import get_role_users

        return [
            (person_spine.ensure_person(user=u), None)
            for u in get_role_users(recipient.role)
        ]

    # Document Field
    value = doc.get(recipient.document_field)
    if not value:
        return []
    df = doc.meta.get_field(recipient.document_field)
    if df and df.fieldtype == "Link":
        target = df.options
        if target == "Person":
            return [(value, None)]
        if target == "User":
            return [(person_spine.ensure_person(user=value), None)]
        if frappe.get_meta(target).has_field("person"):
            person = frappe.db.get_value(target, value, "person")
            return [(person, None)] if person else []
        return []
    # Plain Data field: treat as an email address, match a Person if we can.
    return [(person_spine.find_person(email=value), value)]
