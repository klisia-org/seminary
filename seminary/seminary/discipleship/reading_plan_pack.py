"""Reading plan packs: share a plan between schools (ADR 087 §11).

A pack is a small .zip: `manifest.json` plus each step attachment under
`media/<sha256>`. It carries the plan's content and nothing about any cohort,
member, date or progress. Import follows ADR 041's trust rules: the pack is
untrusted input, the same field allow-lists govern both directions, the archive's
bounds are checked before anything in it is read, and every file lands private.
"""

import hashlib
import io
import json
import zipfile

import frappe
from frappe import _
from frappe.utils import cint

from seminary.seminary.discipleship import reading_plans

PACK_KIND = "reading_plan"
PACK_FORMAT_VERSION = 1
PLAN_FIELDS = ("title", "plan_type", "description")
STEP_FIELDS = reading_plans.LOCKED_STEP_FIELDS + ("message",)
PLAN_TYPES = ("Bible", "Other")

MAX_PACK_BYTES = 50 * 1024**2  # reading_plan_pack_max_bytes
MAX_UNCOMPRESSED_BYTES = 200 * 1024**2  # reading_plan_pack_max_uncompressed_bytes
MAX_ENTRIES = reading_plans.MAX_STEPS + 1
MAX_MANIFEST_BYTES = 2 * 1024**2
MAX_RATIO = 100
RATIO_FLOOR_BYTES = 10 * 1024**2


def _cap(key, default):
    return int(frappe.conf.get(key) or default)


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def build_pack(plan):
    """(filename, zip bytes) for a plan. Plans are small, so in memory."""
    doc = frappe.get_doc("Reading Plan", plan)
    media = {}
    steps = []
    for row in doc.steps:
        step = {f: row.get(f) for f in STEP_FIELDS if row.get(f) not in (None, "")}
        if row.attachment:
            key = _add_media(row.attachment, media)
            step.pop("attachment", None)
            if key:
                step["attachment"] = key
        steps.append(step)
    manifest = {
        "kind": PACK_KIND,
        "pack_format_version": PACK_FORMAT_VERSION,
        "plan": {f: doc.get(f) for f in PLAN_FIELDS},
        "steps": steps,
        "media": {k: {"file_name": v["file_name"]} for k, v in media.items()},
        "source": {"site": frappe.local.site, "plan": doc.name},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, item in media.items():
            zf.writestr(f"media/{key}", item["content"])
        zf.writestr("manifest.json", json.dumps(manifest, indent=1, default=str))
    filename = f"readingplan-{frappe.scrub(doc.title)[:60] or 'plan'}.zip"
    return filename, buffer.getvalue()


def _add_media(url, media):
    name = frappe.db.get_value("File", {"file_url": url, "is_folder": 0}, "name")
    if not name:
        return None
    from seminary.storage.files import open_stream

    f = frappe.get_doc("File", name)
    # open_stream reads local disk and object storage alike (privatedocs/p004).
    with open_stream(f) as chunks:
        content = b"".join(chunks)
    key = hashlib.sha256(content).hexdigest()
    media.setdefault(key, {"file_name": f.file_name, "content": content})
    return key


@frappe.whitelist(methods=["GET"])
def export_plan(plan):
    """Download a plan as a pack. Anyone who may see the plan may share it:
    a pack holds no more than the plan page shows."""
    reading_plans._require_plan_visible(plan)
    filename, content = build_pack(plan)
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "attachment"


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #
def _read_pack_bytes(file_url):
    name = frappe.db.get_value("File", {"file_url": file_url, "is_folder": 0}, "name")
    if not name:
        frappe.throw(_("Uploaded file not found."))
    doc = frappe.get_doc("File", name)
    doc.check_permission("read")
    if not (doc.file_name or "").lower().endswith(".zip"):
        frappe.throw(_("A reading plan pack is a .zip file."))
    if (doc.file_size or 0) > _cap("reading_plan_pack_max_bytes", MAX_PACK_BYTES):
        frappe.throw(_("This reading plan pack is larger than this site accepts."))
    content = doc.get_content(encodings=[])
    return content.encode("utf-8") if isinstance(content, str) else content


def _check_bounds(zf, compressed_size):
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        frappe.throw(_("This reading plan pack has too many files."))
    total = sum(i.file_size for i in infos)
    if total > _cap("reading_plan_pack_max_uncompressed_bytes", MAX_UNCOMPRESSED_BYTES):
        frappe.throw(_("This reading plan pack is too large once unpacked."))
    if (
        total > RATIO_FLOOR_BYTES
        and compressed_size
        and total / compressed_size > MAX_RATIO
    ):
        frappe.throw(_("This file does not look like a reading plan pack."))
    try:
        manifest = zf.getinfo("manifest.json")
    except KeyError:
        frappe.throw(_("This file is not a reading plan pack (no manifest)."))
    if manifest.file_size > MAX_MANIFEST_BYTES:
        frappe.throw(_("This reading plan pack's manifest is too large."))


def _validate_manifest(m):
    if not isinstance(m, dict) or m.get("kind") != PACK_KIND:
        frappe.throw(_("This file is not a reading plan pack."))
    version = m.get("pack_format_version")
    if not isinstance(version, int) or version > PACK_FORMAT_VERSION:
        frappe.throw(
            _(
                "This reading plan pack is newer than this site supports. Update the app first."
            )
        )
    if not isinstance(m.get("plan"), dict) or not isinstance(m.get("steps"), list):
        frappe.throw(_("This reading plan pack's manifest is not valid."))
    if m["plan"].get("plan_type") not in PLAN_TYPES:
        frappe.throw(_("This reading plan pack's manifest is not valid."))
    if len(m["steps"]) > reading_plans.MAX_STEPS:
        frappe.throw(
            _("A reading plan can have at most {0} steps.").format(
                reading_plans.MAX_STEPS
            )
        )


def _text(value, limit):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return str(value)[:limit]


def import_pack_from_bytes(content):
    reading_plans._require_author_role()
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        frappe.throw(_("This file is not a reading plan pack (not a zip archive)."))
    with archive as zf:
        _check_bounds(zf, len(content))
        try:
            manifest = json.loads(zf.read("manifest.json"))
        except ValueError:
            frappe.throw(_("This reading plan pack's manifest is not valid."))
        _validate_manifest(manifest)
        names = set(zf.namelist())
        media = manifest.get("media") if isinstance(manifest.get("media"), dict) else {}

        plan = {f: manifest["plan"].get(f) for f in PLAN_FIELDS}
        doc = frappe.new_doc("Reading Plan")
        doc.update(
            {
                "title": reading_plans._unique_title(_text(plan["title"], 140)),
                "plan_type": plan["plan_type"],
                "description": _text(plan.get("description"), 2000),
                "author": reading_plans.find_person(user=frappe.session.user),
            }
        )
        files = {}
        for raw in manifest["steps"]:
            if not isinstance(raw, dict):
                continue
            # Allow-list: unknown fields are dropped (version skew between sites).
            step = {
                f: _text(raw.get(f), 100000)
                for f in STEP_FIELDS
                if raw.get(f) is not None
            }
            for f in reading_plans.INT_FIELDS:
                if f in step:
                    step[f] = cint(step[f])
            key = raw.get("attachment")
            step.pop("attachment", None)
            if isinstance(key, str) and f"media/{key}" in names:
                if key not in files:
                    file_name = (
                        _text((media.get(key) or {}).get("file_name"), 140) or key[:16]
                    )
                    files[key] = _save_media(zf.read(f"media/{key}"), file_name)
                step["attachment"] = files[key]
            doc.append("steps", step)
        doc.insert(ignore_permissions=True)
        return doc.name


def _save_media(blob, file_name):
    # Always private, whatever the pack says; adopted onto the plan on save.
    f = frappe.get_doc(
        {"doctype": "File", "file_name": file_name, "content": blob, "is_private": 1}
    ).insert(ignore_permissions=True)
    return f.file_url


@frappe.whitelist()
def import_plan(file_url):
    """Import an uploaded pack as a new plan the caller owns."""
    reading_plans._require_author_role()  # before any I/O
    return import_pack_from_bytes(_read_pack_bytes(file_url))
