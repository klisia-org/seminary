# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

"""Generic HTTP GET helper for key-based external integrations.

Thin wrapper over frappe.integrations.utils.make_get_request so we inherit its
Integration Request logging. Provider-specific behaviour (URL building, response
shaping, defaults) belongs in the per-provider module, not here.
"""

from urllib.parse import urljoin

from frappe.integrations.utils import make_get_request


def get(
    base_url: str,
    path: str,
    *,
    auth_header: str,
    auth_value: str,
    params: dict | None = None,
) -> dict | list | str | None:
    """GET `base_url + path` with one auth header, return the parsed body.

    Args:
        base_url: e.g. "https://rest.api.bible" (no trailing slash required)
        path: e.g. "bibles/{id}/passages/JHN.3.16" (no leading slash required)
        auth_header: header name the provider expects, e.g. "api-key" or "Authorization"
        auth_value: header value, e.g. the raw key or "Bearer xyz"
        params: optional query string dict
    """
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    headers = {auth_header: auth_value, "Accept": "application/json"}
    return make_get_request(url, headers=headers, params=params)
