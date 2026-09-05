# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

"""Generic HTTP GET helper for key-based external integrations.

Thin wrapper over `frappe.integrations.utils.make_get_request`, which handles
the session, the error raising and the content-type parsing.

**It does not create Integration Request records.** `make_request` sets
`frappe.flags.integration_request` and nothing more — a caller that wants an
audit trail has to write one itself with `create_request_log`, as
`integrations/geocoding.py` does. This docstring used to claim the logging came
for free, which was never true and is worth knowing before relying on it.

Provider-specific behaviour (URL building, response shaping, defaults) belongs
in the per-provider module, not here.
"""

from urllib.parse import urljoin

from frappe.integrations.utils import make_get_request, make_post_request


def get(
    base_url: str,
    path: str,
    *,
    auth_header: str | None = None,
    auth_value: str | None = None,
    params: dict | None = None,
) -> dict | list | str | None:
    """GET `base_url + path`, optionally with one auth header, parsed body back.

    Args:
        base_url: e.g. "https://rest.api.bible" (no trailing slash required)
        path: e.g. "bibles/{id}/passages/JHN.3.16" (no leading slash required)
        auth_header: header name the provider expects, e.g. "api-key" or
            "Authorization". Omit it for a provider that authenticates by query
            parameter instead — Google's geocoder takes `key=` — rather than
            passing a header the provider ignores.
        auth_value: header value, e.g. the raw key or "Bearer xyz"
        params: optional query string dict
    """
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    headers = {"Accept": "application/json"}
    if auth_header:
        headers[auth_header] = auth_value
    return make_get_request(url, headers=headers, params=params)


def post(
    base_url: str,
    path: str,
    *,
    body: dict | None = None,
    headers: dict | None = None,
) -> dict | list | str | None:
    """POST JSON to `base_url + path` and return the parsed body.

    Separate from `get` because the providers that need it authenticate with
    their own headers rather than a single auth pair — Places API (New) wants
    both `X-Goog-Api-Key` and a mandatory `X-Goog-FieldMask`, and omitting the
    mask is an error rather than a default.
    """
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    all_headers = {"Accept": "application/json", "Content-Type": "application/json"}
    all_headers.update(headers or {})
    return make_post_request(url, json=body or {}, headers=all_headers)
