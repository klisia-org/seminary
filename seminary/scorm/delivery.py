# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Serve a SCORM package from the isolated delivery origin (p009 §2.2, §2.6).

    GET https://<scorm_delivery_host>/scorm/<token>/<package id>/<member path>

Five checks, in order, and the fourth is the one that matters:

1. the request arrived on the delivery host;
2. the token resolves to a live launch;
3. the package id is the one that launch named;
4. **the member path is a key of the package's inventory** -- looked up verbatim,
   never resolved against anything. The client names an inventory entry or it
   gets a 404. That single dict lookup is what closes traversal, bucket probing
   and cross-package reads; nothing here computes a path;
5. the member is served according to its recorded type.

"No such member" and "no such package" answer identically, so the endpoint
cannot be used to enumerate what exists.

## Why text is proxied and media is redirected

Not size -- **whether the thing can contain a relative reference**. Once a
document is fetched via a 302 to a presigned URL, the browser's document URL
becomes the object-store URL, and `assets/main.js`, `../shared/style.css`, the
entire way a SCORM package addresses itself, resolves there unsigned and 403s.
So anything that can carry a relative reference is streamed through this origin,
and everything else -- the video and audio where the egress actually lives --
redirects to a presigned URL exactly as `storage.api.download_file` does.

`storage.api.download_file` itself is not reused and not extended. Its safety
comes from resolving a key to a `File` row; a package has thousands of members
and no rows. The inventory is what makes *this* safe.

## The launcher

`…/<package id>/` with no member path serves our own launcher document. It
cannot be shadowed by a package member, because a member path can never be
empty, and it is same-origin with the SCOs it frames -- which is what lets the
standard `window.API` walk find the runtime with zero bytes of the package
rewritten (§2.8). The runtime itself arrives with S7; today the launcher frames
the first SCO and says so.
"""

from __future__ import annotations

import json

import frappe
from werkzeug.wrappers import Response

from seminary.scorm import tokens

PREFIX = "scorm"

#: Generous: one package can pull hundreds of assets on a single page. What this
#: stops is a flood from one address, not a student opening a lesson (p010 H6).
RATE_LIMIT = 1200
RATE_WINDOW = 60

#: How long a presigned redirect for a media member lives, and how long the
#: browser may cache the redirect itself. Mirrors `storage.api`.
REDIRECT_TTL = 900
_CACHE_SAFETY_MARGIN = 120


def delivery_host() -> str | None:
    return frappe.conf.get("scorm_delivery_host") or None


def is_delivery_request() -> bool:
    """True when this request arrived on the delivery host.

    Frappe routes on path and is indifferent to `Host`, so without this the
    whole app would answer on the delivery domain and the origin split would be
    decoration. Checked here *and* in `before_request` (`guard_delivery_host`),
    so the isolation does not depend on one hook being registered.
    """
    host = delivery_host()
    if not host:
        return False
    request = getattr(frappe.local, "request", None)
    if not request:
        return False
    return (request.host or "").split(":")[0].lower() == host.lower()


def guard_delivery_host():
    """`before_request`. On the delivery host, only `/scorm/...` exists.

    Everything else -- Desk, the SPA, `/api`, `/app`, every website route -- is
    a 404 there, and any session presented is ignored rather than honoured. The
    session cookie is host-only (`frappe/auth.py` sets no `Domain`), so in
    practice none arrives; this makes that a rule rather than a happy accident.
    """
    if not is_delivery_request():
        return

    request = frappe.local.request
    path = (request.path or "").strip("/")
    if path == PREFIX or path.startswith(f"{PREFIX}/"):
        return

    from seminary.seminary import security_log

    security_log.record_denial("scorm_host_scope", path=request.path)
    frappe.local.login_manager = None
    raise frappe.DoesNotExistError


def _rate_limited() -> bool:
    """One counter per address per minute, in redis.

    `frappe.rate_limiter.rate_limit` decorates whitelisted methods; a page
    renderer is not one, so the same shape is spelled out here rather than a
    limit being quietly skipped on the one surface a stranger can reach.
    """
    request = getattr(frappe.local, "request", None)
    address = getattr(request, "remote_addr", None) or "unknown"
    window = int(frappe.utils.now_datetime().timestamp()) // RATE_WINDOW
    key = frappe.cache.make_key(f"scorm:rl:{address}:{window}")
    try:
        count = frappe.cache.incrby(key, 1)
        if count == 1:
            frappe.cache.expire(key, RATE_WINDOW * 2)
        return count > RATE_LIMIT
    except Exception:
        # A limiter that cannot count must not be a limiter that refuses.
        return False


class SCORMDelivery:
    """`page_renderer`. Serves one package member, or the launcher.

    A page renderer rather than a whitelisted method because the **document URL
    matters**: a package's relative references resolve against it, so the URL
    has to be a real path (`…/<package id>/index.html`) and not
    `/api/method/...?path=`. This is the mechanism `SCORMRenderer` used before
    p008 F12 deleted it — the difference is that this one is registered, bound
    to a foreign host, and serves from an inventory rather than from a path it
    joined together itself.
    """

    __slots__ = ("http_status_code", "path")

    def __init__(self, path, http_status_code=None):
        self.path = path
        self.http_status_code = http_status_code

    def _url_path(self) -> str:
        """The raw URL path, not the endpoint frappe hands a renderer.

        `resolve_path` (`frappe/website/path_resolver.py:187`) **strips a
        trailing `.html`** and then maps the result through the route table
        before any custom renderer is consulted -- so a request for
        `.../index.html` arrives here as `.../index`, and every HTML member of
        every package 404s while its stylesheets and scripts serve fine. Found
        on the first live pass; the fake-backend tests could not see it because
        they construct the renderer with the path themselves.

        A package addresses itself by real filenames. Read the URL.
        """
        request = getattr(frappe.local, "request", None)
        raw = (request.path if request else None) or self.path or ""
        return raw.strip("/")

    def can_render(self) -> bool:
        path = self._url_path()
        return is_delivery_request() and (
            path == PREFIX or path.startswith(f"{PREFIX}/")
        )

    def render(self) -> Response:
        if _rate_limited():
            raise frappe.TooManyRequestsError

        parts = self._url_path().split("/")
        # ["scorm", token, package_id, *member]
        if len(parts) < 3:
            return self._missing()

        token, package_id, member_path = parts[1], parts[2], "/".join(parts[3:])

        if not self._app_origin():
            # Misconfiguration, not a miss: serving with the wrong
            # `frame-ancestors` is worse than not serving (see `_app_origin`).
            frappe.log_error(
                "scorm_delivery_host is set but neither scorm_app_origin nor "
                "host_name is. The delivery origin cannot name the origin that "
                "is allowed to frame it, so nothing is served.",
                "scorm: delivery origin is misconfigured",
            )
            return self._missing()

        launch = tokens.resolve(token)
        if not launch:
            return self._missing("token")

        package = frappe.get_cached_doc("SCORM Package", launch["package"])
        if package.package_id != package_id or package.status != "Ready":
            return self._missing("package")

        if not member_path:
            return self._launcher(package, token)

        entry = package.member(member_path)
        if entry is None:
            return self._missing("member")

        from seminary.scorm import archive

        key = package.key_for(member_path)
        if archive.is_proxied(member_path):
            return self._proxy(key, member_path, entry)
        return self._redirect(key, member_path, entry)

    # ------------------------------------------------------------- responses

    def _missing(self, kind: str | None = None) -> Response:
        """One answer for every miss, so this cannot be used to enumerate.

        A wrong token, a package that is not this launch's, a package still
        unpacking and a member the archive never contained are indistinguishable
        from outside.
        """
        if kind:
            from seminary.seminary import security_log

            security_log.record_denial(f"scorm_{kind}_miss", path=self._url_path())
        return Response(status=404, response=b"", mimetype="text/plain")

    def _headers(self, content_type: str, etag: str | None = None) -> dict:
        headers = {
            "Content-Type": content_type,
            # The package is attacker-supplied. None of this protects the app --
            # the origin split does that -- it contains what the package can do
            # to itself and stops anyone else framing this origin.
            "Content-Security-Policy": (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; "
                f"frame-ancestors {self._app_origin()}"
            ),
            "X-Content-Type-Options": "nosniff",
            # Origin-keyed, so `document.domain` cannot be used to reach towards
            # a sibling delivery host (p009 §2.14).
            "Origin-Agent-Cluster": "?1",
            # The launch token is in the path; a package that loads a third-party
            # resource must not hand it over in a `Referer`.
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "private, max-age=3600",
            "Vary": "Cookie",
        }
        if etag:
            headers["ETag"] = f'"{etag}"'
        return headers

    @staticmethod
    def _app_origin() -> str:
        """Where the player page lives. From configuration, never `get_url()`.

        Press sets `host_name`, and `frappe.utils.get_url` returns it whatever
        host the request arrived on -- while on a bench with no `host_name` it
        falls back to the request `Host`, which *here* is the delivery host. A
        value built from it would be right on a laptop and wrong in production,
        or the reverse.

        **There is no fallback, deliberately.** `'self'` on this origin means the
        *delivery* host, so `frame-ancestors 'self'` forbids the app from framing
        the player -- an empty frame with nothing in any log. Deriving it from
        `frappe.local.site` is no better: a second hostname pointing at a site
        resolves to that hostname, which is the delivery host again. A delivery
        origin that does not know its app origin is misconfigured, and §2.14's
        rule holds -- refuse to serve rather than degrade.
        """
        configured = frappe.conf.get("scorm_app_origin") or frappe.conf.get("host_name")
        if not configured:
            return ""
        return configured if configured.startswith("http") else f"https://{configured}"

    def _proxy(self, key: str, member_path: str, entry: dict) -> Response:
        """Stream the member through this origin, so the document URL stays here."""
        etag = entry.get("sha256")
        request = getattr(frappe.local, "request", None)
        if etag and request and request.headers.get("If-None-Match") == f'"{etag}"':
            return Response(
                status=304, headers=self._headers(entry["content_type"], etag)
            )

        from seminary.storage.backend import get_storage_backend

        backend = get_storage_backend()
        stream = backend.stream(key, chunk_size=256 * 1024)
        headers = self._headers(entry["content_type"], etag)
        if entry.get("size"):
            headers["Content-Length"] = str(entry["size"])
        return Response(stream, status=200, headers=headers, direct_passthrough=True)

    def _redirect(self, key: str, member_path: str, entry: dict) -> Response:
        """Hand the browser a presigned URL. This is where the egress saving is.

        Safe for these members precisely because they carry no relative
        references: a video or a font does not resolve anything against the URL
        it was fetched from.
        """
        from seminary.storage.backend import get_storage_backend

        url = get_storage_backend().presigned_get(
            key,
            ttl=REDIRECT_TTL,
            file_name=member_path.rsplit("/", 1)[-1],
            content_type=entry.get("content_type"),
            as_attachment=False,
        )
        response = Response(status=302)
        response.headers["Location"] = url
        response.headers["Cache-Control"] = (
            f"private, max-age={max(REDIRECT_TTL - _CACHE_SAFETY_MARGIN, 0)}"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def _launcher(self, package, token: str) -> Response:
        """Our own document, same-origin with the SCOs it frames.

        That sameness is the whole trick of §2.8: the SCO's standard
        `while (win.parent) { if (win.API) ... }` walk finds the runtime here
        with **zero bytes of the package rewritten**.

        The runtime is inlined rather than served as a second file. A separate
        asset would need a URL under this package's prefix, and every such URL
        is a member path -- so it could be shadowed by a package that happens to
        contain a file of that name. One document has nothing to collide with.
        """
        launch = tokens.resolve(token) or {}
        config = {
            "version": package.scorm_version or "1.2",
            "appOrigin": self._app_origin(),
            "package": package.package_id,
            "index": 0,
            "scos": [
                {
                    "id": i.sco_identifier,
                    "title": i.title,
                    "href": i.href,
                    # Seeded from the launch so the package resumes where the
                    # student left it without a round trip on startup.
                    "cmi": _cmi_for(launch.get("user"), package.name, i.sco_identifier),
                }
                for i in sorted(package.items, key=lambda i: i.idx)
            ],
        }
        html = (
            _launcher_template()
            .replace("__TITLE__", "SCORM")
            .replace("__RUNTIME__", _runtime_source())
            .replace("__CONFIG__", json.dumps(config))
        )
        return Response(
            html.encode(),
            status=200,
            headers=self._headers("text/html; charset=utf-8"),
        )


def _asset(name: str) -> str:
    """Read one of our own files from the app, cached for the worker's life.

    Never from the package inventory: these are ours, and a package must not be
    able to influence what the launcher runs.
    """
    import os

    cache = getattr(frappe.local, "_scorm_assets", None)
    if cache is None:
        cache = {}
        frappe.local._scorm_assets = cache
    if name not in cache:
        path = os.path.join(frappe.get_app_path("seminary"), "scorm", "assets", name)
        with open(path, encoding="utf-8") as handle:
            cache[name] = handle.read()
    return cache[name]


def _launcher_template() -> str:
    return _asset("launcher.html")


def _runtime_source() -> str:
    return _asset("runtime.js")


def _cmi_for(user: str | None, package: str, sco: str) -> dict:
    """The stored state for one SCO, in the shape the runtime seeds from."""
    from seminary.scorm.launch import opaque_learner_id

    snapshot = {"learner_id": opaque_learner_id(user or "", package, sco)}
    if not user:
        return snapshot

    row = frappe.db.get_value(
        "SCORM Attempt",
        {"package": package, "sco_identifier": sco, "member": user},
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
        ],
        as_dict=True,
    )
    if row:
        snapshot.update({k: v for k, v in row.items() if v is not None})
    return snapshot
