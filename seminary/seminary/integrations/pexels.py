# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

"""Pexels stock-photo integration.

Lets instructors pick a free, no-attribution-required course image from
Pexels (https://www.pexels.com/api/) directly in the course form. The API key
stays server-side: the frontend only ever calls the whitelisted proxy methods
below. Mirrors the api.bible integration in `bible.py`.
"""

import io
from urllib.parse import urlparse

import requests

import frappe
from frappe import _
from frappe.utils.file_manager import save_file
from frappe.utils.image import optimize_image

from seminary.seminary.integrations import client

# Roles allowed to edit a course image (same set api.save_course honours).
COURSE_EDITOR_ROLES = [
    "Instructor",
    "Program Chair",
    "Seminary Manager",
    "System Manager",
]

# SSRF guard: only download from the Pexels image CDN, never an arbitrary URL.
ALLOWED_IMAGE_HOSTS = {"images.pexels.com"}

# Stored card image is clamped to this size and recompressed (Courses page
# renders many at once, so keep them small).
MAX_IMAGE_WIDTH = 1280
MAX_IMAGE_HEIGHT = 960
IMAGE_QUALITY = 82

DOWNLOAD_TIMEOUT = 30


def _get_settings():
    settings = frappe.get_single("Pexels Settings")
    if not settings.enabled:
        frappe.throw(_("Pexels integration is disabled in Pexels Settings."))
    if not settings.base_url:
        frappe.throw(_("Pexels Settings is missing a Base URL."))
    return settings


def _get_api_key(settings) -> str:
    key = settings.get_password("api_key", raise_exception=False)
    if not key:
        frappe.throw(_("Pexels Settings is missing an API Key."))
    return key


def _shape_photo(photo: dict) -> dict:
    """Trim a Pexels photo to just what the picker needs."""
    src = photo.get("src") or {}
    return {
        "id": photo.get("id"),
        "thumb": src.get("medium"),
        # large2x (~1880px) gives optimize_image room to produce a crisp,
        # retina-friendly card image after the downscale/recompress.
        "full": src.get("large2x") or src.get("large") or src.get("original"),
        "alt": photo.get("alt") or "",
    }


@frappe.whitelist()
def search_photos(query: str, page: int = 1) -> dict:
    """Search Pexels for `query`. Returns a trimmed, paginated photo list."""
    frappe.only_for(COURSE_EDITOR_ROLES)
    query = (query or "").strip()
    if not query:
        return {"photos": [], "next_page": None, "total_results": 0}

    settings = _get_settings()
    per_page = settings.results_per_page or 15
    payload = (
        client.get(
            base_url=settings.base_url,
            path="v1/search",
            auth_header="Authorization",
            auth_value=_get_api_key(settings),
            params={"query": query, "per_page": per_page, "page": int(page or 1)},
        )
        or {}
    )

    photos = [_shape_photo(p) for p in payload.get("photos", [])]
    photos = [p for p in photos if p["full"]]
    return {
        "photos": photos,
        # Pexels only returns `next_page` when more results exist.
        "next_page": (int(page or 1) + 1) if payload.get("next_page") else None,
        "total_results": payload.get("total_results", 0),
    }


@frappe.whitelist()
def download_photo(src_url: str) -> dict:
    """Download a chosen Pexels image, optimize it, and store it as a File.

    Returns `{file_url, file_name}` — the same shape FileUploader's success
    callback hands to `saveImage` in CourseForm, so the rest of the save and
    display flow is unchanged.
    """
    frappe.only_for(COURSE_EDITOR_ROLES)
    _get_settings()  # enforce the master switch before doing any work

    host = (urlparse(src_url).hostname or "").lower()
    if host not in ALLOWED_IMAGE_HOSTS:
        frappe.throw(_("Only Pexels image URLs can be downloaded."))

    resp = requests.get(src_url, timeout=DOWNLOAD_TIMEOUT)
    resp.raise_for_status()
    content = resp.content

    content_type = (
        (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
    )
    if not content_type.startswith("image/"):
        frappe.throw(_("The Pexels URL did not return an image."))

    content = optimize_image(
        content,
        content_type,
        max_width=MAX_IMAGE_WIDTH,
        max_height=MAX_IMAGE_HEIGHT,
        quality=IMAGE_QUALITY,
    )

    ext = _extension_for(content_type)
    photo_id = _photo_id_from_url(src_url)
    filename = f"pexels-{photo_id}{ext}"

    # Public, like other course images (Courses.vue renders the URL directly).
    file_doc = save_file(filename, content, None, None, is_private=0)
    return {"file_url": file_doc.file_url, "file_name": file_doc.file_name}


def _extension_for(content_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(content_type, ".jpg")


def _photo_id_from_url(src_url: str) -> str:
    path = urlparse(src_url).path
    for part in path.split("/"):
        if part.isdigit():
            return part
    return "image"


@frappe.whitelist()
def test_connection() -> dict:
    """Verify the configured Pexels credentials work. Used by the settings form."""
    frappe.only_for(["System Manager", "Seminary Manager"])
    try:
        result = search_photos("nature", page=1)
        count = len(result.get("photos", []))
        return {
            "ok": True,
            "message": _("Connected successfully. {0} sample photos returned.").format(
                count
            ),
        }
    except frappe.PermissionError:
        raise
    except Exception as e:
        return {"ok": False, "message": str(e) or _("Unknown error")}
