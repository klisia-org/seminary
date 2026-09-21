# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The commit endpoint: what a package is allowed to tell us (p009 §2.9).

Called by the **application origin** with the user's own session, never by the
delivery origin -- which holds no credential that could. The package's runtime
posts to the player page over `postMessage`; the player page makes this call.

Identity comes from the launch and the session, in that order, and never from
the payload:

* the token names `(user, package, chapter)`, and it was minted only after
  `launch` ran the section guards;
* the launch's user must be the session user, or the call is a logged denial.

So a caller cannot commit against a package they did not launch, nor against
another student's attempt, and cannot smuggle a chapter or a course in.

What a package *can* do is lie about its own state, and nothing here pretends
otherwise: the vocabularies are closed, the scores are clamped to the range the
package declared, `suspend_data` and `location` are length-capped, and the whole
lot is then treated as a claim rather than an assessment (§2.12).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from seminary.scorm import cmi, lessons, tokens
from seminary.scorm.launch import MODE_NORMAL


@frappe.whitelist()
@rate_limit(key="scorm_commit", limit=1200, seconds=3600, ip_based=False)
def commit(token: str, sco: str, data=None) -> dict:
    """Persist what a SCO reported. Returns a result the runtime can read."""
    from seminary.seminary import security_log

    launch = tokens.resolve(token)
    if not launch:
        return {"ok": False, "error": cmi.ERR_GENERAL, "reason": "no such launch"}

    if launch.get("user") != frappe.session.user:
        # The one check that matters: a token is a bearer capability for
        # *reading* a package, and it must never become a way to write as
        # whoever it was issued to.
        security_log.record_denial(
            "scorm_commit_identity", package=launch.get("package")
        )
        return {"ok": False, "error": cmi.ERR_GENERAL, "reason": "not your launch"}

    package = launch["package"]
    chapter = launch["chapter"]

    item = frappe.db.exists(
        "SCORM Package Item", {"parent": package, "sco_identifier": sco}
    )
    if not item:
        return {"ok": False, "error": cmi.ERR_GENERAL, "reason": "no such SCO"}

    if _mode(chapter) != MODE_NORMAL:
        # Staff are previewing. Answer successfully so the package behaves, and
        # write nothing: an instructor checking a package must not record a
        # score against themselves, nor against anybody else.
        return {"ok": True, "stored": False, "reason": "review"}

    try:
        values = cmi.normalise(
            frappe.parse_json(data) if isinstance(data, str) else (data or {})
        )
    except cmi.CMIError as e:
        return {"ok": False, "error": e.code, "reason": str(e)}

    if not values:
        return {"ok": True, "stored": False, "reason": "nothing to store"}

    attempt = _attempt(package, chapter, sco)
    if attempt.locked:
        # Staff have acted on this attempt. Late commits do not rewrite it.
        return {"ok": True, "stored": False, "reason": "locked"}

    for field, value in values.items():
        attempt.set(field, value)
    attempt.last_commit_on = frappe.utils.now_datetime()

    try:
        attempt.save(ignore_permissions=True)
    except cmi.CMIError as e:
        return {"ok": False, "error": e.code, "reason": str(e)}
    except frappe.ValidationError as e:
        return {"ok": False, "error": cmi.ERR_GENERAL, "reason": str(e)}

    lessons.record_progress(
        _lesson_for(chapter, sco),
        chapter,
        attempt.course,
        lessons.status_for(attempt.completion_status, attempt.success_status),
    )

    return {
        "ok": True,
        "stored": True,
        "completion_status": attempt.completion_status,
        "success_status": attempt.success_status,
    }


def _mode(chapter: str) -> str:
    """Re-derived from the session, not carried in the payload.

    The launch response tells the *browser* which mode it is in so the player
    can say so; this is the copy that decides whether anything is written.
    """
    from seminary.scorm.launch import MODE_REVIEW
    from seminary.seminary.guards import is_course_staff

    course = frappe.db.get_value("Course Schedule Chapter", chapter, "coursesc")
    return (
        MODE_REVIEW if is_course_staff(course, include_registrar=True) else MODE_NORMAL
    )


def _attempt(package: str, chapter: str, sco: str):
    existing = frappe.db.get_value(
        "SCORM Attempt",
        {"package": package, "sco_identifier": sco, "member": frappe.session.user},
        "name",
    )
    if existing:
        return frappe.get_doc("SCORM Attempt", existing)

    course = frappe.db.get_value("Course Schedule Chapter", chapter, "coursesc")
    attempt = frappe.new_doc("SCORM Attempt")
    attempt.update(
        {
            "member": frappe.session.user,
            "student": frappe.db.get_value(
                "Scheduled Course Roster",
                {"course_sc": course, "stuemail_rc": frappe.session.user},
                "name",
            ),
            "course": course,
            "chapter": chapter,
            "package": package,
            "sco_identifier": sco,
            "attempt_no": 1,
            "started_on": frappe.utils.now_datetime(),
        }
    )
    attempt.flags.ignore_permissions = True
    return attempt


def _lesson_for(chapter: str, sco: str) -> str | None:
    return frappe.db.get_value(
        "Course Lesson", {"chapter": chapter, "scorm_sco_identifier": sco}, "name"
    )


@frappe.whitelist()
def state(token: str, sco: str) -> dict:
    """The stored state for one SCO, for a player that reconnects.

    Same identity rule as `commit`: the launch must be this session's.
    """
    launch = tokens.resolve(token)
    if not launch or launch.get("user") != frappe.session.user:
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    row = frappe.db.get_value(
        "SCORM Attempt",
        {
            "package": launch["package"],
            "sco_identifier": sco,
            "member": frappe.session.user,
        },
        [
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
        as_dict=True,
    )
    return row or {}
