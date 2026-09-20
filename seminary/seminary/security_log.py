# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The `seminary.security` logger and denial counter (p010 H1, p005 item 13, A09-1).

## What was missing

Phases 0-2 and 1.5 closed the authorization and injection classes. What none of
them added is any way to tell that somebody is *trying*. p005a A09-3 put it
exactly: **a successful privilege-escalation attempt leaves nothing.** Frappe
renders `PermissionError` as a bare 403 with no row anywhere, and not one of
seminary's own `frappe.throw(..., PermissionError)` sites logs first. So the
site's entire record of "stuA spent an afternoon walking `frappe.client.get`
over other students' submissions" is a handful of nginx access-log lines that
nobody reads and that carry no actor.

## Why a logger and not an Error Log row

Error Log is a doctype: it is readable by roles that may not read the record the
denial was about, it is written inside the request transaction (so it rolls back
with the throw that caused it), and it is exactly where p005a found PII already
leaking (A09-3, fixed in H3). A rotating site log file has none of those
properties, costs nothing on the request path, and is what an operator greps.

## The redaction rule is the point

p005a checked every `log_error` call in the app and found the app clean: no
secret, token, session id or password reaches any log today. **That property is
worth more than any line this module writes**, so it is enforced here rather
than trusted: `_safe_context` drops a key by name before its value is ever
formatted, and truncates what survives. A logger that leaks a token is worse
than no logger.

## What may be named

The actor, the endpoint or doctype, and the permission type -- always. A
*docname* only when the caller passes one it has established the actor could
already see, because a denial message that names the record the actor was
refused is itself the disclosure the refusal prevented. That is the same
reasoning p008 F11 applied to `applicant_payment` and p008a applied to the
folder API.
"""

from __future__ import annotations

import json
import logging

import frappe

#: Log file is `sites/<site>/logs/seminary.security.log` (and the bench-level
#: copy), rotated by frappe's own handler.
LOGGER_NAME = "seminary.security"

#: Denial counts live in redis, not in a doctype: a counter that rolls back with
#: the transaction it is counting is useless. One plain integer key per day and
#: kind, so an operator can ask "how many denials today" without scanning the
#: log.
#:
#: Plain keys rather than frappe's hash helpers, and the site prefix applied by
#: hand, because frappe's `RedisWrapper` is **half** overridden: `hincrby` is
#: raw redis (unprefixed, integer-valued) while `hgetall` is overridden to
#: prefix the key with the site *and* `pickle.loads` every value
#: (`frappe/utils/redis_wrapper.py:229`). The pair addresses two different keys
#: in two different encodings; the counter silently read zero forever. `incrby`,
#: `get`, `expire` and `keys` are all un-overridden, so staying on raw redis for
#: the whole counter is the one self-consistent choice.
COUNTER_PREFIX = "seminary:security:denials"
COUNTER_TTL = 14 * 24 * 60 * 60

#: Dropped by *name*, before the value is formatted. Substring match, lowercased:
#: `access_key`, `request_token`, `csrf_token` and `api_secret` all match.
_SENSITIVE = (
    "token",
    "secret",
    "password",
    "passwd",
    "sid",
    "key",
    "signature",
    "cookie",
    "authorization",
    "payload",
)

_MAX_VALUE = 200

#: Request-local guard so a denial thrown by `guards` and then observed as a 403
#: by the `after_request` hook is one line, not two.
_FLAG = "seminary_denial_logged"


def logger():
    """The security logger, pinned to WARNING.

    Frappe's default level is `ERROR` off the dev server
    (`frappe/utils/logger.py:11`), so without this pin every denial would be
    written nowhere in production and be perfectly visible in development --
    the exact inversion of what this module is for. Caught because the first
    run of `test_p010_security_log` logged nothing at all.
    """
    log = frappe.logger(LOGGER_NAME, allow_site=True)
    if log.level > logging.WARNING:
        log.setLevel(logging.WARNING)
    return log


def _is_sensitive(name: str) -> bool:
    lowered = str(name).lower()
    return any(marker in lowered for marker in _SENSITIVE)


def _safe_value(value):
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    return text if len(text) <= _MAX_VALUE else text[:_MAX_VALUE] + "..."


def _safe_context(context: dict) -> dict:
    """Drop sensitive keys by name, truncate the rest. Never raises."""
    out = {}
    for name, value in (context or {}).items():
        if _is_sensitive(name):
            out[name] = "[redacted]"
            continue
        out[name] = _safe_value(value)
    return out


def _actor() -> str:
    try:
        return frappe.session.user or "Guest"
    except Exception:
        return "unknown"


def _site_prefix() -> str:
    """What `RedisWrapper.make_key` prepends, applied by hand. See COUNTER_PREFIX."""
    return "%s|" % (frappe.local.conf.get("db_name") or "unknown")


def _day_prefix(day: str | None = None) -> str:
    from frappe.utils import today

    return f"{_site_prefix()}{COUNTER_PREFIX}:{day or today()}:"


def _bump(kind: str) -> None:
    try:
        cache = frappe.cache()
        key = _day_prefix() + kind
        cache.incrby(key, 1)
        cache.expire(key, COUNTER_TTL)
    except Exception:  # nosec B110 -- the counter must never cost a response
        # A counter must never cost a response. The log line still went out.
        # (This `except` hid the wrapper mismatch above completely -- only the
        # test that asserted the counter *moves* found it.)
        pass


def record_denial(kind: str, **context) -> None:
    """One structured line plus one counter tick. Never raises.

    `kind` is a short stable slug (`permission`, `rate_limit`, `http_403`) --
    stable because it is the counter's field name and an operator's grep anchor.
    """
    try:
        if getattr(frappe.local, _FLAG, False):
            return
        setattr(frappe.local, _FLAG, True)

        entry = {"kind": kind, "actor": _actor()}
        entry.update(_safe_context(context))
        try:
            entry["path"] = frappe.local.request.path
        except (
            Exception
        ):  # nosec B110 -- no request context (background job, bench execute)
            pass
        logger().warning(json.dumps(entry, default=str, sort_keys=True))
        _bump(kind)
    except Exception:
        try:
            frappe.logger().error("security_log failed", exc_info=True)
        except (
            Exception
        ):  # nosec B110 -- the fallback logger failed; there is nowhere left to go
            pass


def denial_counts(day: str | None = None) -> dict:
    """Today's counts by kind. For operators and for the phase's own tests."""
    prefix = _day_prefix(day)
    counts = {}
    try:
        cache = frappe.cache()
        for key in cache.keys(prefix + "*"):
            name = key.decode() if isinstance(key, bytes) else key
            value = cache.get(name)
            try:
                counts[name[len(prefix) :]] = int(value)
            except (TypeError, ValueError):
                continue
    except Exception:
        return counts
    return counts


def log_denied_response(response=None, request=None, **kwargs):
    """`after_request` sibling of `http_headers.apply_security_headers`.

    Catches the denials that never pass through `guards` -- Frappe's own
    `has_permission`, a `permission_query_conditions` refusal surfaced as 403,
    a whitelist miss -- which is most of them. The `_FLAG` guard means a denial
    that *did* come from `guards` is not counted twice.

    Never raises: a log line must not cost a response.
    """
    if response is None:
        return
    try:
        if getattr(response, "status_code", 200) not in (401, 403):
            return
        record_denial(
            "http_%s" % getattr(response, "status_code", "403"),
            endpoint=(frappe.form_dict or {}).get("cmd"),
            method=getattr(request, "method", None),
        )
    except (
        Exception
    ):  # nosec B110 -- after_request: raising here turns a 403 into a 500
        pass
