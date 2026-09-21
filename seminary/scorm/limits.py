# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Per-actor rate limits for the SCORM endpoints (p009 S11, p010 H6).

**Why this is not `frappe.rate_limiter.rate_limit`.** That decorator's `key`
argument names a *request parameter whose value identifies the caller* -- it is
not a label for the bucket. Passing a label and `ip_based=False` leaves it with
no identity at all::

    user_key = frappe.form_dict.get(key, "")            # a label is not a field
    ip = frappe.local.request_ip if ip_based is True else None
    identity = identity or ip or user_key               # -> None
    if not identity:
        frappe.throw(_("Either key or IP flag is required."))

`frappe.throw` is a `ValidationError`, so the endpoint answers **417 to every
request**. That is how five SCORM endpoints shipped, and what makes it worth a
module docstring rather than a one-line fix: `rate_limiter.py:133` returns early
when `frappe.request` is unset, so the decorator is a **complete no-op** under
`bench run-tests`, `bench console` and `bench execute`. Every test passed, every
console call worked, and every browser got a 417. A bug that is invisible from
each of the three places we look is worth a named lesson.

The identity we actually want is the **signed-in user**: these endpoints all
require a session, a launch token is minted for one user, and a whole school
behind one NAT must not share a bucket. Frappe's decorator cannot express that,
so the check is spelled out here -- the same shape `delivery` already spells out
for the page renderer, which a decorator cannot reach either.

Fails **open**: a limiter that cannot reach redis must not become a limiter that
refuses everybody.
"""

from __future__ import annotations

import frappe


def identity() -> str:
    """Who to count against: the signed-in user, or the address for a guest."""
    user = None
    try:
        user = frappe.session.user
    except Exception:
        user = None
    if user and user != "Guest":
        return f"u:{user}"

    request = getattr(frappe.local, "request", None)
    return "ip:%s" % (getattr(request, "remote_addr", None) or "unknown")


def exceeded(bucket: str, limit: int, seconds: int, who: str | None = None) -> bool:
    """True when `who` has spent `limit` calls on `bucket` in this window.

    A fixed window rather than a sliding one, for the reason the renderer's copy
    gives: the cost of a rolling log per request is not worth the precision when
    the limits are this loose.
    """
    who = who or identity()
    window = int(frappe.utils.now_datetime().timestamp()) // seconds
    key = frappe.cache.make_key(f"scorm:rl:{bucket}:{who}:{window}")
    try:
        count = frappe.cache.incrby(key, 1)
        if count == 1:
            frappe.cache.expire(key, seconds * 2)
        return count > limit
    except Exception:
        return False


def enforce(bucket: str, limit: int, seconds: int, who: str | None = None) -> None:
    """`exceeded`, as a refusal. Raises `TooManyRequestsError` (429)."""
    if exceeded(bucket, limit, seconds, who=who):
        from seminary.seminary import security_log

        security_log.record_denial("scorm_rate_limit", bucket=bucket)
        raise frappe.TooManyRequestsError
