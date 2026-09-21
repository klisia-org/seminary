# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The launch capability: a short-lived, revocable read on one package (p009 §2.7).

The delivery origin has no session -- that is the whole point of §2.2 -- so
something has to carry authorisation across to it. This is that something, and
it is worth being precise about what it is and is not.

**What it is.** A random 32-byte secret, minted on the application origin *after*
the launch guards have run, bound to one `(user, package, chapter)` and expiring.
It appears as the first path segment of every delivery URL, which is what keeps
the package's relative references resolving against our origin (§2.6) -- a query
string would be dropped by relative resolution, and a cookie on a separate
registrable domain is a third-party cookie that Safari drops outright.

**What it is worth.** Anyone holding it can read that package's bytes until it
expires. The package's own JavaScript can read it out of `location`, and there is
no way around that: code inside the frame can always see the URL that loaded it.
This is the same bearer-capability property p004 already accepted for every
presigned media URL in the app -- narrowed to one package, attributable to a
launch, and revocable, which a presigned URL is not. It is **not** a session, it
cannot be exchanged for one, and it reaches no LMS endpoint.

**Stability, and the honest note about storage.** A second launch of the same
package by the same user within the TTL reuses the live token. That is not a
convenience: the token is a path segment, so a fresh one per launch gives every
asset a fresh URL and defeats the browser cache entirely. Reuse needs a reverse
index, and a reverse index has to hold the token itself -- so the token *is*
stored in redis, and keying the primary entry by its hash buys less than it
looks like it does. It is kept because the primary keyspace is the large one
(one entry per live launch) and the one an attacker would enumerate, while the
reverse index is a single key per user and package. Recorded rather than
dressed up.
"""

from __future__ import annotations

import hashlib
import json

import frappe

DEFAULT_TTL = 8 * 60 * 60  # scorm_launch_ttl

_PRIMARY = "scorm:launch"
_REVERSE = "scorm:launch:of"


def ttl() -> int:
    return int(frappe.conf.get("scorm_launch_ttl") or DEFAULT_TTL)


def _primary_key(token: str) -> str:
    return f"{_PRIMARY}:{hashlib.sha256(token.encode()).hexdigest()}"


def _reverse_key(user: str, package: str) -> str:
    return f"{_REVERSE}:{hashlib.sha256(f'{user}|{package}'.encode()).hexdigest()}"


def mint(user: str, package: str, chapter: str) -> str:
    """Issue (or reuse) a launch token. Call only after the guards have passed."""
    reverse = _reverse_key(user, package)
    existing = frappe.cache.get_value(reverse)
    if existing:
        live = resolve(existing)
        if live and live.get("chapter") == chapter:
            return existing

    token = frappe.generate_hash(length=64)
    payload = {"user": user, "package": package, "chapter": chapter}
    frappe.cache.set_value(
        _primary_key(token), json.dumps(payload), expires_in_sec=ttl()
    )
    frappe.cache.set_value(reverse, token, expires_in_sec=ttl())
    return token


def resolve(token: str) -> dict | None:
    """The launch this token names, or None.

    There is no secret comparison to make constant-time: the lookup *is* the
    check, because the key is derived from the token. A wrong token reaches a
    key that does not exist.

    The package is re-checked on every resolve, which is what makes deleting a
    package or its last chapter an effective revocation. A change of enrolment is
    not caught here -- it takes effect at the next launch or renewal -- because a
    permission check per asset request would put a round trip on every image in
    a package.
    """
    if not token or len(token) < 32:
        return None

    raw = frappe.cache.get_value(_primary_key(token))
    if not raw:
        return None

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None

    if not frappe.db.exists("SCORM Package", payload.get("package")):
        return None
    return payload


def renew(token: str) -> bool:
    """Push the expiry out while an attempt is open. The launcher heartbeats."""
    payload = resolve(token)
    if not payload:
        return False
    frappe.cache.expire(_primary_key(token), ttl())
    frappe.cache.expire(_reverse_key(payload["user"], payload["package"]), ttl())
    return True


def revoke(token: str) -> None:
    payload = resolve(token)
    frappe.cache.delete_value(_primary_key(token))
    if payload:
        frappe.cache.delete_value(_reverse_key(payload["user"], payload["package"]))
