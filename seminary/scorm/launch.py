# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Authorise a SCORM launch, on the application origin (p009 §2.7).

This is where the permission decision is made -- by the same guards every other
course read uses, on the origin that has the session. The delivery origin makes
no permission decision at all; it holds a capability this module issued.

Everything the launcher needs travels in the response: the delivery base URL,
the SCO list, and the current CMI state for each. The delivery origin is never
asked to look any of it up, which is what keeps it a dumb byte server.
"""

from __future__ import annotations

import hashlib

import frappe
from frappe import _

from seminary.scorm import limits, tokens
from seminary.seminary.guards import is_course_staff, require_enrolled

#: A staff launch is a **preview**: no attempt is created and no commit is
#: persisted. An instructor clicking through a package to check it must not
#: write a score, and SCORM already has a word for this.
MODE_NORMAL = "normal"
MODE_REVIEW = "review"


@frappe.whitelist()
def launch(chapter: str) -> dict:
    """Everything needed to play `chapter`, or a refusal."""
    limits.enforce("launch", 120, 3600)
    row = frappe.db.get_value(
        "Course Schedule Chapter",
        chapter,
        ["name", "coursesc", "chapter_title", "is_scorm_package", "scorm_package_ref"],
        as_dict=True,
    )
    if not row or not row.is_scorm_package:
        frappe.throw(
            _("This chapter is not a SCORM package."), frappe.DoesNotExistError
        )

    # Staff, readers, the registrar tier, and a student on the active roster of
    # a published section -- `is_enrolled` already encodes all of it (p007 §8.1).
    require_enrolled(row.coursesc)

    host = frappe.conf.get("scorm_delivery_host")
    if not host:
        frappe.throw(
            _("SCORM playback is not configured on this site."),
            frappe.DoesNotExistError,
        )

    if not row.scorm_package_ref:
        return {"status": "Pending", "chapter": chapter}

    package = frappe.get_doc("SCORM Package", row.scorm_package_ref)
    if package.status != "Ready":
        return {
            "status": package.status,
            "chapter": chapter,
            # A failure reason names files inside an instructor's package; a
            # student gets the state and nothing else.
            "failure_reason": (
                package.failure_reason
                if is_course_staff(row.coursesc, include_registrar=True)
                else None
            ),
        }

    mode = (
        MODE_REVIEW
        if is_course_staff(row.coursesc, include_registrar=True)
        else MODE_NORMAL
    )
    token = tokens.mint(frappe.session.user, package.name, chapter)
    base = f"https://{host}/scorm/{token}/{package.package_id}/"

    return {
        "status": "Ready",
        "chapter": chapter,
        "course": row.coursesc,
        "package": package.name,
        "scorm_version": package.scorm_version,
        "mode": mode,
        "token": token,
        "token_ttl": tokens.ttl(),
        "delivery_origin": f"https://{host}",
        "launcher": base,
        "scos": _scos(package, row, mode),
    }


def _scos(package, chapter, mode: str) -> list[dict]:
    lessons = {
        row.scorm_sco_identifier: row
        for row in frappe.get_all(
            "Course Lesson",
            filters={"chapter": chapter.name},
            fields=["name", "lesson_title", "scorm_sco_identifier", "scorm_orphaned"],
        )
        if row.scorm_sco_identifier
    }
    attempts = {
        row.sco_identifier: row
        for row in frappe.get_all(
            "SCORM Attempt",
            filters={"package": package.name, "member": frappe.session.user},
            fields=[
                "name",
                "sco_identifier",
                "completion_status",
                "success_status",
                "score_raw",
                "score_min",
                "score_max",
                "score_scaled",
                "location",
                "suspend_data",
                "total_time",
                "locked",
            ],
        )
    }

    out = []
    for item in sorted(package.items, key=lambda i: i.idx):
        lesson = lessons.get(item.sco_identifier)
        out.append(
            {
                "id": item.sco_identifier,
                "title": item.title,
                "href": item.href,
                "lesson": lesson.name if lesson else None,
                "orphaned": bool(lesson and lesson.scorm_orphaned),
                "cmi": _snapshot(
                    package,
                    item.sco_identifier,
                    attempts.get(item.sco_identifier),
                    mode,
                ),
            }
        )
    return out


def _snapshot(package, sco: str, attempt, mode: str) -> dict:
    """The CMI values the launcher seeds its local model from.

    `learner_id` is **opaque and derived**, never the email, the User name or
    the Student docname: a package is third-party code, and an identifier that
    is stable across sites is one we have donated to a vendor. It is stable for
    this learner and this SCO, which is all a package legitimately needs.
    """
    send_name = frappe.conf.get("scorm_send_learner_name")
    send_name = True if send_name is None else bool(send_name)

    snapshot = {
        "learner_id": opaque_learner_id(frappe.session.user, package.name, sco),
        "learner_name": (
            frappe.utils.get_fullname(frappe.session.user) if send_name else ""
        ),
        "mode": mode,
        "credit": "credit" if mode == MODE_NORMAL else "no-credit",
        "entry": "resume" if attempt and attempt.location else "ab-initio",
    }
    if not attempt:
        return snapshot

    snapshot.update(
        {
            "completion_status": attempt.completion_status,
            "success_status": attempt.success_status,
            "score_raw": attempt.score_raw,
            "score_min": attempt.score_min,
            "score_max": attempt.score_max,
            "score_scaled": attempt.score_scaled,
            "location": attempt.location,
            "suspend_data": attempt.suspend_data,
            "total_time": attempt.total_time,
            "locked": bool(attempt.locked),
        }
    )
    return snapshot


def opaque_learner_id(user: str, package: str, sco: str) -> str:
    """Stable for (learner, package, SCO); meaningless anywhere else.

    Keyed with the site's own secret so the same person at two schools is two
    different learners to the same vendor's package.
    """
    secret = frappe.local.conf.get("encryption_key") or frappe.local.site
    return hashlib.sha256(f"{secret}|{user}|{package}|{sco}".encode()).hexdigest()[:32]


@frappe.whitelist()
def heartbeat(token: str) -> dict:
    """Push the launch's expiry out while the player is open.

    Only for the user it was issued to: a token is a bearer capability, and the
    one thing that must not be bearer-only is extending its life.
    """
    limits.enforce("heartbeat", 600, 3600)
    payload = tokens.resolve(token)
    if not payload or payload.get("user") != frappe.session.user:
        return {"ok": False}
    return {"ok": tokens.renew(token)}


@frappe.whitelist()
def end(token: str) -> dict:
    """Revoke a launch. The TTL is the real bound; this is the early exit.

    **Not called on player unmount, deliberately.** `tokens.mint` reuses a live
    token for the same (user, package), so the token one player holds is very
    often the one the next player is already using -- moving between two SCOs
    of a package mounts the new player before unmounting the old. Revoking on
    unmount therefore killed the capability the new player had just been
    handed, and its iframe got a bare 404 with no CSP, so the browser applied
    nginx's `X-Frame-Options` and refused to display it. Found on the first
    browser pass. Unmount was never much of a revocation in any case: it does
    not fire when a tab is closed, which is how a student actually leaves.

    Kept as the revocation primitive, for an explicit end-of-attempt action and
    for staff revoking a launch they have reason to.

    Revocation is the cheap half of the token lifecycle and the half an attacker
    has no use for, but the endpoint still resolves a caller-supplied token, so
    it gets the same ceiling as the rest (p010 H6). A player calls it once.
    """
    limits.enforce("end", 600, 3600)
    payload = tokens.resolve(token)
    if payload and payload.get("user") == frappe.session.user:
        tokens.revoke(token)
    return {"ok": True}
