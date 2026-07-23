"""Flagging & moderation for the Community subsystem (ADR 064, Phase 9).

Any reader can flag a post or reply they can see. Moderation authority is
Leader + Staff: a leader moderates within the subtree of cohorts they lead;
staff moderate globally. Both work the same flag queue. `private` / `direct`
posts are never in scope (a reader can only flag what they can see, and those
are visible only to their author/recipient).
"""

import frappe
from frappe import _
from frappe.utils import now

from seminary.seminary.discipleship.feed_api import _is_staff, _my_person
from seminary.seminary.discipleship.permissions import led_cohorts, post_has

_TARGETS = ("Cohort Post", "Cohort Post Comment")


def _can_moderate_cohort(cohort, user=None):
    user = user or frappe.session.user
    return _is_staff(user) or cohort in led_cohorts(user)


def _post_of(target_doctype, target_name):
    if target_doctype == "Cohort Post":
        return target_name
    return frappe.db.get_value("Cohort Post Comment", target_name, "post")


# --------------------------------------------------------------------------- #
# Flagging (any reader)
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def flag_content(target_doctype, target_name, reason, detail=None):
    person = _my_person()
    if target_doctype not in _TARGETS:
        frappe.throw(_("Only posts and replies can be flagged."))
    post_doc = frappe.get_doc("Cohort Post", _post_of(target_doctype, target_name))
    if not post_has(post_doc, user=frappe.session.user):
        frappe.throw(_("You cannot flag this."), frappe.PermissionError)
    flag = frappe.get_doc(
        {
            "doctype": "Cohort Content Flag",
            "target_doctype": target_doctype,
            "target_name": target_name,
            "reporter": person,
            "reason": reason,
            "detail": detail,
        }
    ).insert(ignore_permissions=True)
    return flag.name


# --------------------------------------------------------------------------- #
# Moderation queue (leaders + staff)
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def list_flags(status="Open"):
    """Open flags the caller may moderate (get_list applies flag scoping)."""
    filters = {}
    if status:
        filters["status"] = status
    flags = frappe.get_list(
        "Cohort Content Flag",
        filters=filters,
        fields=[
            "name",
            "target_doctype",
            "target_name",
            "cohort",
            "reason",
            "detail",
            "reporter",
            "status",
            "creation",
        ],
        order_by="creation asc",
    )
    for f in flags:
        f["preview"] = _preview(f["target_doctype"], f["target_name"])
    return flags


def _preview(target_doctype, target_name):
    content = frappe.db.get_value(target_doctype, target_name, "content") or ""
    text = frappe.utils.strip_html(content).strip()
    return text[:140]


@frappe.whitelist()
def resolve_flag(flag, action, note=None):
    """action: dismiss | block | review. Blocking hides the target from the feed."""
    doc = frappe.get_doc("Cohort Content Flag", flag)
    if not _can_moderate_cohort(doc.cohort):
        frappe.throw(_("You cannot moderate this."), frappe.PermissionError)
    if action == "dismiss":
        doc.status = "Dismissed"
    elif action == "block":
        doc.status = "Actioned"
        _set_target_status(doc.target_doctype, doc.target_name, "blocked")
    elif action == "review":
        doc.status = "Reviewed"
    else:
        frappe.throw(_("Unknown action."))
    doc.reviewed_by = frappe.session.user
    doc.reviewed_on = now()
    if note:
        doc.resolution_note = note
    doc.save(ignore_permissions=True)
    return doc.status


def _set_target_status(target_doctype, target_name, status):
    frappe.db.set_value(target_doctype, target_name, "status", status)


# --------------------------------------------------------------------------- #
# Direct moderation actions (leaders + staff)
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def set_post_status(post, status):
    """Pin, unpin (published), or block a post."""
    if status not in ("published", "pinned", "blocked"):
        frappe.throw(_("Invalid status."))
    cohort = frappe.db.get_value("Cohort Post", post, "cohort")
    if not _can_moderate_cohort(cohort):
        frappe.throw(_("You cannot moderate this."), frappe.PermissionError)
    frappe.db.set_value("Cohort Post", post, "status", status)
    return status


@frappe.whitelist()
def moderate_comment(comment, blocked=1):
    cohort = frappe.db.get_value("Cohort Post Comment", comment, "cohort")
    if not _can_moderate_cohort(cohort):
        frappe.throw(_("You cannot moderate this."), frappe.PermissionError)
    frappe.db.set_value(
        "Cohort Post Comment",
        comment,
        "status",
        "blocked" if int(blocked) else "published",
    )
    return True


@frappe.whitelist()
def can_moderate():
    """True if the caller leads any cohort or is staff — gates the moderation UI."""
    return _is_staff(frappe.session.user) or bool(led_cohorts(frappe.session.user))
