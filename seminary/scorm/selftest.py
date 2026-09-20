# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Prove the delivery origin is wired before a package depends on it (p009 S11).

SCORM delivery has four moving parts that live in four different places: two
keys in `site_config.json`, two hook registrations in the app, a bucket at the
object store, and a DNS record plus a certificate at the edge. Nothing binds
them together, so **every wrong combination fails silently and late** -- the
player frames an origin that answers nothing, or answers everything, and the
first person to find out is an instructor who has just waited twenty minutes
for an 800 MB upload.

    bench --site <site> execute seminary.scorm.selftest.run

Four arms, in order of how much they cost to check:

1. **Configuration.** `scorm_delivery_host` is set; an app origin is knowable
   (`scorm_app_origin` or `host_name` -- `delivery._app_origin` refuses to serve
   without one, and logs rather than raises, so this is otherwise invisible);
   and the two hosts are on **different registrable domains**, which is the one
   configuration mistake that silently undoes §2.2. See `_registrable`.

2. **Hooks.** `SCORMDelivery` is in `page_renderer` and `guard_delivery_host` is
   in `before_request`. An app installed but not migrated, or a `hooks.py`
   edited by hand, leaves a delivery host that serves the whole site.

3. **Storage.** A byte round-trip under `scorm/_selftest/`, in the package
   prefix rather than `media/` -- the same object store, but the path SCORM
   actually uses, so a bucket policy scoped by prefix is exercised too.

4. **The live origin.** Three HTTP requests to the delivery host, over TLS,
   from this server. This is the arm the other three cannot substitute for: it
   is the only one that touches DNS, the certificate, the proxy's `Host`
   routing, and the `before_request` guard *as deployed*.

## What arm 4 proves, and what it does not

It proves that something is answering on the delivery host over a valid
certificate, that it refuses `/app` and `/api`, and that `/scorm/...` reaches a
renderer rather than the website router. Those are exactly the failures worth
catching: a delivery host that serves Desk is the origin split undone, and a
delivery host that 404s `/scorm/` through the *website* router means the
renderer is not registered.

It does **not** prove that the host resolves to this site. Nothing reachable on
the delivery origin identifies the site behind it without a launch token, and
minting one would mean building a package to launch. An operator reading a green
arm 4 has been told the delivery origin behaves correctly; the DNS record is
their own to have pointed at the right proxy, and arm 4 reports the address it
reached so that it can be checked by eye.

Requests never follow redirects and never send a cookie: this server holds an
administrator session, and a selftest that authenticated itself against the
delivery host would be testing the wrong thing.
"""

from __future__ import annotations

import frappe

#: Arm 4 runs from a worker. A delivery host whose DNS is wrong will hang on
#: connect, and a selftest that blocks a worker for a minute is a selftest an
#: operator stops running.
HTTP_TIMEOUT = 10

#: Paths probed on the delivery host, and what each one must NOT be.
#:
#: `/app` and the API method are the origin split itself: if either answers 200
#: the delivery host is serving the application, and a package can reach the
#: session of anyone who opens it. `/scorm/` is the opposite check -- it must
#: reach *our renderer*, which is distinguishable from frappe's own 404 because
#: `SCORMDelivery._missing` answers `text/plain` with an empty body while the
#: website router renders an HTML page.
PROBE_DESK = "/app"
PROBE_API = "/api/method/frappe.auth.get_logged_user"
PROBE_SCORM = "/scorm/"


@frappe.whitelist()
def run() -> dict:
    """Run all four arms. Returns a verdict per arm plus an overall `ok`."""
    frappe.only_for("System Manager")

    arms = {
        "config": _config(),
        "hooks": _hooks(),
        "storage": _storage(),
    }
    # Arm 4 needs a host to talk to; running it against `None` would report a
    # connection failure and bury the real finding, which arm 1 already made.
    arms["origin"] = (
        _origin()
        if arms["config"]["ok"]
        else {"ok": False, "detail": "Not run: see config."}
    )

    return {
        "ok": all(arm["ok"] for arm in arms.values()),
        "arms": arms,
    }


# --------------------------------------------------------------- arm 1: config


def _registrable(host: str) -> str:
    """The last two labels of `host`.

    A deliberate approximation of the public-suffix list, and wrong in one
    direction only: `a.co.uk` and `b.co.uk` both reduce to `co.uk` and are
    reported as sharing a registrable domain, which is a false *refusal* an
    operator can read and overrule. The opposite error -- passing two hosts that
    really can set each other's cookies -- is the one §2.2 cannot tolerate, and
    this cannot make it. Shipping the full list to catch a case nobody here has
    is not worth the dependency.
    """
    return ".".join(host.lower().strip(".").split(".")[-2:])


def _config() -> dict:
    from seminary.scorm import delivery

    host = delivery.delivery_host()
    if not host:
        return {
            "ok": False,
            "detail": "`scorm_delivery_host` is not set; SCORM playback is off on this site.",
        }

    app_origin = delivery.SCORMDelivery._app_origin()
    if not app_origin:
        return {
            "ok": False,
            "delivery_host": host,
            "detail": (
                "`scorm_delivery_host` is set but neither `scorm_app_origin` nor "
                "`host_name` is. The delivery origin cannot name the origin allowed "
                "to frame it, so it refuses to serve -- and says so only in the "
                "Error Log."
            ),
        }

    app_host = app_origin.split("://", 1)[-1].split("/")[0].split(":")[0]
    if _registrable(host) == _registrable(app_host):
        return {
            "ok": False,
            "delivery_host": host,
            "app_origin": app_origin,
            "detail": (
                f"`{host}` and `{app_host}` share the registrable domain "
                f"`{_registrable(host)}`. A sibling subdomain can set a cookie the "
                "application host will receive, which hands every package uploader "
                "a session-fixation primitive -- the delivery host must be a "
                "different registrable domain (p009 §2.2)."
            ),
        }

    return {
        "ok": True,
        "delivery_host": host,
        "app_origin": app_origin,
        "send_learner_name": bool(
            True
            if frappe.conf.get("scorm_send_learner_name") is None
            else frappe.conf.get("scorm_send_learner_name")
        ),
    }


# ---------------------------------------------------------------- arm 2: hooks


def _hooks() -> dict:
    renderers = frappe.get_hooks("page_renderer") or []
    before = frappe.get_hooks("before_request") or []

    missing = []
    if "seminary.scorm.delivery.SCORMDelivery" not in renderers:
        missing.append("page_renderer -> seminary.scorm.delivery.SCORMDelivery")
    if "seminary.scorm.delivery.guard_delivery_host" not in before:
        missing.append("before_request -> seminary.scorm.delivery.guard_delivery_host")

    if missing:
        return {
            "ok": False,
            "missing": missing,
            "detail": (
                "Hooks are not registered. Without the renderer nothing is served; "
                "without the guard the whole application answers on the delivery "
                "host. Run `bench --site <site> migrate` and clear the cache."
            ),
        }
    return {"ok": True}


# -------------------------------------------------------------- arm 3: storage


def _storage() -> dict:
    from seminary.storage.backend import get_storage_backend

    backend = get_storage_backend()
    name = type(backend).__name__
    if not backend.is_configured():
        return {
            "ok": False,
            "backend": name,
            "detail": (
                "No object storage configured. SCORM packages are exploded to "
                "object storage and have no on-disk path (p009 §2.1), so playback "
                "cannot work without it."
            ),
        }

    key = f"scorm/_selftest/{frappe.generate_hash(length=16)}/probe.txt"
    payload = b"seminary scorm selftest"
    try:
        backend.put(key, payload, content_type="text/plain")
        if backend.read(key) != payload:
            return {
                "ok": False,
                "backend": name,
                "detail": "Object read back did not match what was written.",
            }
    except Exception as e:
        return {
            "ok": False,
            "backend": name,
            "detail": f"Round-trip under `scorm/` failed: {e}",
        }
    finally:
        # Best effort, for the same reason `storage.api.selftest` gives: losing
        # the verdict to a cleanup failure would be worse than a stray probe.
        try:
            backend.delete(key)
        except Exception:
            frappe.log_error(
                title="seminary.scorm: selftest probe not cleaned up",
                message=f"{key}\n{frappe.get_traceback()}",
            )

    return {"ok": True, "backend": name, "prefix": "scorm/"}


# --------------------------------------------------------------- arm 4: origin


def _fetch(host: str, path: str) -> dict:
    import requests

    url = f"https://{host}{path}"
    try:
        response = requests.get(
            url,
            timeout=HTTP_TIMEOUT,
            allow_redirects=False,
            # No cookie jar, no session: see the module docstring.
            headers={"User-Agent": "seminary-scorm-selftest"},
        )
    except Exception as e:
        return {"error": str(e)}
    return {
        "status": response.status_code,
        "content_type": (response.headers.get("Content-Type") or "").split(";")[0],
        "length": len(response.content or b""),
    }


def _origin() -> dict:
    from seminary.scorm import delivery

    host = delivery.delivery_host()
    probes = {path: _fetch(host, path) for path in (PROBE_DESK, PROBE_API, PROBE_SCORM)}

    failures = []

    unreachable = [p for p, r in probes.items() if "error" in r]
    if unreachable:
        return {
            "ok": False,
            "host": host,
            "probes": probes,
            "detail": (
                f"Could not reach https://{host} -- DNS, the certificate, or the "
                "proxy. This is the expected result on a development bench, where "
                "the delivery host does not resolve; it is a real failure anywhere "
                "a student will open a package."
            ),
        }

    for path in (PROBE_DESK, PROBE_API):
        if probes[path]["status"] == 200:
            failures.append(
                f"`{path}` answered 200 on the delivery host. The application is "
                "being served on the delivery origin, which undoes the isolation "
                "the whole design rests on (p009 §2.2)."
            )

    scorm = probes[PROBE_SCORM]
    if scorm["status"] != 404:
        failures.append(
            f"`{PROBE_SCORM}` answered {scorm['status']}; a path with no token "
            "must be a 404."
        )
    elif scorm["content_type"] != "text/plain" or scorm["length"]:
        # frappe's own 404 is an HTML page; `SCORMDelivery._missing` is an empty
        # `text/plain`. Reaching the website router here means the renderer is
        # not being consulted, so every package member would 404 too.
        failures.append(
            f"`{PROBE_SCORM}` 404'd through the website router "
            f"({scorm['content_type'] or 'no content-type'}, {scorm['length']} bytes) "
            "rather than through SCORMDelivery. The renderer is registered but not "
            "reached -- check that the request arrives with the delivery `Host`."
        )

    if failures:
        return {"ok": False, "host": host, "probes": probes, "failures": failures}
    return {
        "ok": True,
        "host": host,
        "probes": probes,
        "detail": (
            "The delivery origin refuses Desk and the API and reaches the SCORM "
            "renderer. This does not prove the host resolves to *this* site -- see "
            "the module docstring."
        ),
    }
