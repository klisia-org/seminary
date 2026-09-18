# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Who may read an uploaded file (privatedocs/p007 §8.2).

Frappe serves a public File (`/files/…`) straight from nginx with no session:
"public" is the whole internet, not the school. The intranet behaviour a school
wants is Frappe's *private* rule: `File.has_permission` on a private File falls
through to the read permission of the document the File is attached to. So:

* **Every upload is private.** A public save stands only for a publisher
  (System Manager, Website Manager), for the two server paths whose reader has
  no session (outbound email images, the telephony carrier), or for a field
  listed in `PUBLIC_FILE_FIELDS`.
* **The host document decides who reads it.** Attach fields are attached by
  Frappe itself (`attach_files_to_document`); files that live inside content
  (lesson bodies, exam answers) are attached here, by `adopt_embedded`.

## Adding a field to the public website

One line in `PUBLIC_FILE_FIELDS`: `("Course", "hero_image"): None,`. The value is
`None` for "always may be public", or a predicate of the host document's name.
`"*"` as the fieldname covers every Attach field of the doctype. A rich-text
field (Text Editor and kin) can be listed too: the images pasted into it are
published with the host and the stored HTML is rewritten to their new URL. Nothing else has
to change: the wildcard `on_update` hook keeps the File in step with its host.
"""

from __future__ import annotations

import html
import json
import re
from urllib.parse import quote, unquote

import frappe
from frappe import _
from frappe.utils import cint

from seminary.storage.backend import FILE_URL_RE, URL_PREFIX, normalize_file_url

PUBLISHER_ROLES = {"System Manager", "Website Manager"}


# --------------------------------------------------------------------- predicates


def _program_published(name) -> bool:
    return bool(frappe.db.get_value("Program", name, "published"))


def person_photo_is_public(person) -> bool:
    """The "Our Team" rule (ADR 061, `faculty.get_unit_roster(public=True)`):
    not blocked from the web, and an active member of a unit that publishes."""
    if not person or frappe.db.get_value("Person", person, "block_from_web"):
        return False
    return bool(
        frappe.db.sql(
            """
            select 1
            from `tabAcademic Unit Membership` m
            join `tabAcademic Unit` u on u.name = m.unit
            where m.person = %s and m.is_active = 1
              and u.publish_on_web = 1 and u.is_active = 1
            limit 1
            """,
            person,
        )
    )


def _instructor_photo_is_public(instructor) -> bool:
    return person_photo_is_public(
        frappe.db.get_value("Instructor", instructor, "person")
    )


# ---------------------------------------------------------------------- registries

#: (doctype, fieldname) -> None | predicate(host docname). See the module docstring.
PUBLIC_FILE_FIELDS = {
    ("Website Branding", "*"): None,
    ("Seminary Settings", "*"): None,
    ("Letter Head", "*"): None,
    ("Partner Organization", "image"): None,
    ("Program", "hero_image"): _program_published,
    ("Program", "image_blurb"): _program_published,
    # Rich text shown on /programs: images pasted into it follow the program.
    ("Program", "blurb"): _program_published,
    ("Program", "program_description"): _program_published,
    ("Program", "program_requirements"): _program_published,
    ("Program", "duration_txt"): _program_published,
    ("Person", "image"): person_photo_is_public,
    ("Instructor", "profileimage"): _instructor_photo_is_public,
}

#: Private, but any signed-in user may read them: an avatar is shown to every
#: classmate, and a classmate cannot read the Person it hangs on.
INTRANET_FILE_FIELDS = {
    ("Person", "image"),
    ("Student", "image"),
    ("Instructor", "profileimage"),
    ("Alumni Profile", "image"),
    ("User", "user_image"),
}

#: Fields that carry a copy of another field's URL. A privacy flip renames a disk
#: file (`/files/x` <-> `/private/files/x`); Frappe rewrites the host field only.
URL_MIRRORS = (
    ("Person", "image"),
    ("Student", "image"),
    ("Instructor", "profileimage"),
    ("Alumni Profile", "image"),
    ("User", "user_image"),
)


def _self_host(doc):
    return doc.doctype, doc.name


#: Doctypes whose *content* embeds file URLs, and the document those files
#: should borrow their read permission from.
EMBEDDED_FILE_FIELDS = {
    "Course Lesson": {
        "fields": ("content", "body", "instructor_content", "instructor_notes"),
        "children": (),
        "host": lambda doc: ("Course Schedule", doc.get("course_sc")),
    },
    "Exam Submission": {
        "fields": (),
        "children": (("result", "answer"),),
        "host": _self_host,
    },
    "Quiz Submission": {
        "fields": (),
        "children": (("result", "answer"),),
        "host": _self_host,
    },
}


def _membership_targets(doc):
    out = []
    if doc.get("person"):
        out.append(("Person", doc.person))
    if doc.get("instructor"):
        out.append(("Instructor", doc.instructor))
    return out


def _unit_targets(doc):
    out = []
    for m in frappe.get_all(
        "Academic Unit Membership",
        filters={"unit": doc.name},
        fields=["person", "instructor"],
    ):
        out.extend(_membership_targets(m))
    return out


def _person_targets(doc):
    return [
        ("Instructor", n)
        for n in frappe.get_all("Instructor", {"person": doc.name}, pluck="name")
    ]


#: A save of the key doctype can change the predicate of other hosts.
DEPENDENTS = {
    "Academic Unit": _unit_targets,
    "Academic Unit Membership": _membership_targets,
    "Person": _person_targets,
}


# -------------------------------------------------------------------------- policy


def _host_doctypes() -> set:
    return {dt for dt, _f in PUBLIC_FILE_FIELDS}


def _registered(doctype, fieldname):
    """(found, predicate) for a File attached to doctype.fieldname."""
    for key in ((doctype, fieldname), (doctype, "*")):
        if key in PUBLIC_FILE_FIELDS:
            return True, PUBLIC_FILE_FIELDS[key]
    return False, None


def _is_seminary_doctype(doctype) -> bool:
    def _lookup():
        module = frappe.db.get_value("DocType", doctype, "module")
        return (
            bool(module)
            and frappe.db.get_value("Module Def", module, "app_name") == "seminary"
        )

    return frappe.cache.hget("seminary_file_policy_app", doctype, _lookup)


def _attached_field(file_doc):
    """The host field a File sits on, looked up by URL when the row does not
    say (Frappe only fills `attached_to_field` on some paths)."""
    if file_doc.attached_to_field:
        return file_doc.attached_to_field
    dt, dn = file_doc.attached_to_doctype, file_doc.attached_to_name
    if not (dt and dn and file_doc.file_url):
        return None
    candidates = [f for d, f in PUBLIC_FILE_FIELDS if d == dt and f != "*"]
    for field in candidates:
        try:
            if frappe.db.get_value(dt, dn, field) == file_doc.file_url:
                return field
        except Exception:
            frappe.clear_last_message()
    return None


def may_be_public(file_doc) -> bool:
    if frappe.flags.seminary_public_file:
        return True
    dt, dn = file_doc.attached_to_doctype, file_doc.attached_to_name
    if dt and dn:
        found, predicate = _registered(dt, _attached_field(file_doc))
        if found:
            return predicate is None or bool(predicate(dn))
        if _is_seminary_doctype(dt):
            return False
    return bool(PUBLISHER_ROLES & set(frappe.get_roles()))


def may_be_public_for_host(file_doc) -> bool:
    """`may_be_public` without the uploader's role: what the *host* allows. A
    file on a seminary document is public only through the registry; a file on
    anything else (a Web Page, a Blog Post) is none of this policy's business."""
    dt, dn = file_doc.attached_to_doctype, file_doc.attached_to_name
    if not (dt and dn):
        return True
    found, predicate = _registered(dt, _attached_field(file_doc))
    if found:
        return predicate is None or bool(predicate(dn))
    return not _is_seminary_doctype(dt)


def apply_on_insert(file_doc):
    """`SeminaryFile.before_insert`, ahead of Frappe writing the bytes: an
    upload that may not be public is stored private. Silent on purpose — every
    uploader in the SPA and on Desk keeps working, the file just lands where
    only its readers reach it."""
    if file_doc.is_folder or cint(file_doc.is_private):
        return
    if (file_doc.file_url or "").startswith(("http://", "https://")):
        return  # a link, not an upload
    if not may_be_public(file_doc):
        file_doc.is_private = 1


def check_on_save(file_doc):
    """`SeminaryFile.validate`, ahead of Frappe moving the bytes: an existing
    private file is made public only by someone who may."""
    if file_doc.is_new() or file_doc.is_folder or cint(file_doc.is_private):
        return
    if not file_doc.has_value_changed("is_private"):
        return
    if not may_be_public(file_doc):
        frappe.throw(
            _(
                "This file cannot be made public. Public files are readable by "
                "anyone on the internet; ask a Website Manager."
            ),
            frappe.PermissionError,
        )


def intranet_readable(file_doc, user=None) -> bool:
    user = user or frappe.session.user
    if user == "Guest":
        return False
    dt = file_doc.attached_to_doctype
    if not dt:
        return False
    field = file_doc.attached_to_field
    if field:
        return (dt, field) in INTRANET_FILE_FIELDS
    # Row without a fieldname: an image attached to one of the avatar hosts.
    for d, f in INTRANET_FILE_FIELDS:
        if d != dt:
            continue
        try:
            value = frappe.db.get_value(dt, file_doc.attached_to_name, f)
        except Exception:
            frappe.clear_last_message()
            continue
        if value and value == file_doc.file_url:
            return True
    return False


# ------------------------------------------------------------------ privacy flips


def _rows_for(url):
    return frappe.get_all(
        "File",
        filters={"file_url": url, "is_folder": 0},
        fields=[
            "name",
            "is_private",
            "owner",
            "attached_to_doctype",
            "attached_to_name",
            "attached_to_field",
        ],
    )


def _replace_in_mirrors(old, new):
    for doctype, field in URL_MIRRORS:
        if not frappe.db.has_column(doctype, field):
            continue
        for name in frappe.get_all(doctype, filters={field: old}, pluck="name"):
            frappe.db.set_value(doctype, name, field, new, update_modified=False)


def _replace_in_content(old, new):
    for doctype, cfg in EMBEDDED_FILE_FIELDS.items():
        targets = [(doctype, f) for f in cfg["fields"]]
        for table_field, column in cfg["children"]:
            child = frappe.get_meta(doctype).get_field(table_field)
            if child:
                targets.append((child.options, column))
        spellings = {(old, new), (quote(old), quote(new))}
        for dt, column in targets:
            if not frappe.db.has_column(dt, column):
                continue
            for old_s, new_s in spellings:
                # `%` in a percent-encoded spelling only widens the LIKE
                # pre-filter; `replace()` itself is exact.
                frappe.db.sql(
                    f"update `tab{dt}` set `{column}` = replace(`{column}`, %s, %s) "  # nosec B608
                    f"where `{column}` like %s",
                    (old_s, new_s, f"%{old_s}%"),
                )


def set_privacy(url, public, host=None):
    """Make every File row behind `url` public or private. Returns the URL the
    file answers to afterwards (a disk file is renamed by the flip)."""
    if (url or "").startswith(("http://", "https://")):
        return url  # a link to somebody else's server, not a file of ours
    rows = _rows_for(url)
    want = 0 if public else 1
    if not rows or all(cint(r.is_private) == want for r in rows):
        return url
    row = rows[0]
    if host:
        for r in rows:
            if (r.attached_to_doctype, r.attached_to_name) == tuple(host[:2]):
                row = r
                break
    doc = frappe.get_doc("File", row.name)
    doc.is_private = want
    previous = frappe.flags.seminary_public_file
    frappe.flags.seminary_public_file = True
    try:
        doc.save(ignore_permissions=True)
    finally:
        frappe.flags.seminary_public_file = previous
    new = doc.file_url
    if new != url:
        if host and len(host) == 3:
            dt, dn, field = host
            if frappe.get_meta(dt).issingle:
                frappe.db.set_single_value(dt, field, new)
            else:
                frappe.db.set_value(dt, dn, field, new, update_modified=False)
        _replace_in_mirrors(url, new)
        _replace_in_content(url, new)
    return new


def _is_file_url(value) -> bool:
    return bool(value) and bool(FILE_URL_RE.match(value))


def _other_address(url):
    if url.startswith("/private/files/"):
        return url[len("/private") :]
    if url.startswith("/files/"):
        return "/private" + url
    return None


RICH_TEXT_FIELDTYPES = ("Text Editor", "HTML Editor", "Markdown Editor")


def _sync_rich_text(doctype, name, field, value, public):
    """A registered rich-text field: the images pasted into it follow the host.

    Only Files attached to this very document are touched. Frappe attaches a
    pasted image to the document it was pasted into, so that is exactly the set
    the editor put there; a URL somebody typed by hand, pointing at a file that
    hangs elsewhere, is not published by being mentioned on a public page."""
    if not value or not isinstance(value, str):
        return
    content = value
    for match in find_urls(value):
        url = _lookup_url(match)
        rows = [
            r
            for r in _rows_for(url)
            if (r.attached_to_doctype, r.attached_to_name) == (doctype, name)
        ]
        if not rows:
            # A stale URL: the file was flipped after this HTML was loaded into
            # a form, and the form saved the old address back. Point it at
            # where the file lives now.
            twin = _other_address(url)
            if twin and any(
                (r.attached_to_doctype, r.attached_to_name) == (doctype, name)
                for r in _rows_for(twin)
            ):
                content = content.replace(match, set_privacy(twin, public))
            continue
        new = set_privacy(url, public, host=(doctype, name))
        if new != url:
            # `match` still carries Frappe's `?fid=` suffix on a private URL.
            content = content.replace(match, new)
    if content != value:
        if frappe.get_meta(doctype).issingle:
            frappe.db.set_single_value(doctype, field, content)
        else:
            frappe.db.set_value(doctype, name, field, content, update_modified=False)


def sync_public_state(doctype, name):
    """Bring the Files on a host's registered fields in line with the registry:
    public while the predicate holds, private when it stops holding."""
    meta = frappe.get_meta(doctype)
    for (dt, field), predicate in PUBLIC_FILE_FIELDS.items():
        if dt != doctype:
            continue
        fields = (
            [
                df.fieldname
                for df in meta.get(
                    "fields", {"fieldtype": ["in", ["Attach", "Attach Image"]]}
                )
            ]
            if field == "*"
            else [field]
        )
        for f in fields:
            if not meta.has_field(f):
                continue
            value = (
                frappe.db.get_single_value(doctype, f)
                if meta.issingle
                else frappe.db.get_value(doctype, name, f)
            )
            public = predicate is None or bool(predicate(name))
            if meta.get_field(f).fieldtype in RICH_TEXT_FIELDTYPES:
                try:
                    _sync_rich_text(doctype, name, f, value, public)
                except Exception:
                    frappe.log_error(
                        frappe.get_traceback(),
                        f"file_policy: could not sync {doctype} {name}.{f}",
                    )
                continue
            if not _is_file_url(value):
                continue
            try:
                set_privacy(value, public, host=(doctype, name, f))
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"file_policy: could not sync {doctype} {name}.{f}",
                )


# ------------------------------------------------------------ embedded-file hosts


_FILE_PREFIXES = ("/files/", "/private/files/", URL_PREFIX)
_ATTR_RE = re.compile(r"""(?:src|href|data-src)\s*=\s*(?:"([^"]+)"|'([^']+)')""", re.I)
_MD_RE = re.compile(r"\]\((/[^)]+)\)")
_MACRO_RE = re.compile(r"""\(\s*["'](/[^"']+)["']\s*\)""")


def _is_file_address(value) -> bool:
    return isinstance(value, str) and value.startswith(_FILE_PREFIXES)


def find_urls(text) -> set:
    """Every file address written in `text`, exactly as written.

    A bare pattern scan (`FILE_URL_RE`) stops at whitespace, and uploaded files
    are routinely called "Syllabus Fall 2026.pdf". So read the structure first:
    EditorJS JSON values, HTML attributes, Markdown links and the legacy
    `{{ Video("…") }}` macros all delimit the address themselves. The pattern
    scan only picks up what is left."""
    found = set()
    if not text or not isinstance(text, str):
        return found

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            if _is_file_address(node) and "<" not in node:
                found.add(node)
            else:
                scan(node)

    def scan(chunk):
        for rx in (_ATTR_RE, _MD_RE, _MACRO_RE):
            for m in rx.findall(chunk):
                value = next((g for g in m if g), "") if isinstance(m, tuple) else m
                if _is_file_address(value):
                    found.add(value)
        for m in FILE_URL_RE.findall(chunk):
            if not any(f.startswith(m) for f in found):
                found.add(m)

    stripped = text.lstrip()
    if stripped[:1] in "{[":
        try:
            walk(json.loads(text))
            return found
        except ValueError:
            pass
    scan(text)
    return found


def _lookup_url(raw) -> str:
    """The `File.file_url` a written address refers to."""
    return unquote(normalize_file_url(html.unescape(raw))).rstrip("\\")


def _embedded_urls(doc, cfg) -> set:
    chunks = [doc.get(f) or "" for f in cfg["fields"]]
    for table_field, column in cfg["children"]:
        chunks.extend((row.get(column) or "") for row in (doc.get(table_field) or []))
    urls = set()
    for chunk in chunks:
        urls.update(_lookup_url(raw) for raw in find_urls(chunk))
    return urls


def _may_adopt(rows, source_host) -> bool:
    """Naming a URL in content must not be a way to read someone else's file:
    the saver has to be able to read it already. A template import is the one
    exception, for files that belong to the section being copied."""
    user = frappe.session.user
    if user == "Administrator":
        return True
    if source_host and any(
        (r.attached_to_doctype, r.attached_to_name) == tuple(source_host) for r in rows
    ):
        return True
    for r in rows:
        if r.owner == user or not cint(r.is_private):
            return True
        if frappe.get_doc("File", r.name).is_downloadable():
            return True
    return False


def adopt(url, host, source_host=None):
    """Attach the file behind `url` to `host` (doctype, name) as a private File,
    so the host's readers can open it. Returns the URL to use from now on."""
    host_dt, host_dn = host
    if not (host_dt and host_dn):
        return url
    rows = _rows_for(url)
    if not rows:
        return url
    mine = [
        r
        for r in rows
        if (r.attached_to_doctype, r.attached_to_name) == (host_dt, host_dn)
    ]
    loose = [r for r in rows if not r.attached_to_doctype]
    if not mine:
        if not _may_adopt(rows, source_host):
            return url
        if loose:
            frappe.db.set_value(
                "File",
                loose[0].name,
                {"attached_to_doctype": host_dt, "attached_to_name": host_dn},
                update_modified=False,
            )
            mine = [loose[0]]
        elif all(not cint(r.is_private) for r in rows):
            return url  # somebody else's public file (a logo, say): leave it
        else:
            src = frappe.get_doc("File", rows[0].name)
            twin = frappe.new_doc("File")
            twin.update(
                {
                    "file_name": src.file_name,
                    "file_url": src.file_url,
                    "file_size": src.file_size,
                    "file_type": src.file_type,
                    "content_hash": src.content_hash,
                    "is_private": 1,
                    "folder": src.folder or "Home/Attachments",
                    "attached_to_doctype": host_dt,
                    "attached_to_name": host_dn,
                }
            )
            # A second row over the same bytes. `db_insert` on purpose: the
            # File lifecycle would re-check that the *saver* can read the
            # source, which `_may_adopt` has already decided.
            twin.name = frappe.generate_hash(length=10)
            twin.db_insert()
            return url
    if not cint(mine[0].is_private):
        return set_privacy(url, public=False, host=host)
    return url


def adopt_embedded(doc, source_host=None):
    cfg = EMBEDDED_FILE_FIELDS.get(doc.doctype)
    if not cfg:
        return
    host = cfg["host"](doc)
    for url in _embedded_urls(doc, cfg):
        try:
            adopt(url, host, source_host=source_host)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"file_policy: could not adopt {url}"
            )


# --------------------------------------------------------------------------- hooks


def _refresh_registered_fields(doc):
    """A flip renames the file, so the value just saved may be out of date.
    Put the stored value back on the document: the save response is what the
    Desk form shows next, and what it would save back."""
    meta = doc.meta
    for dt, field in PUBLIC_FILE_FIELDS:
        if dt != doc.doctype or field == "*" or not meta.has_field(field):
            continue
        stored = (
            frappe.db.get_single_value(dt, field)
            if meta.issingle
            else frappe.db.get_value(dt, doc.name, field)
        )
        if stored != doc.get(field):
            doc.set(field, stored)
    # Frappe's own flip writes the new URL onto the host with a fresh
    # `modified`, which would make the form the user is looking at stale
    # ("modified after you have opened it") on their very next save.
    if not meta.issingle and doc.get("modified"):
        frappe.db.set_value(
            doc.doctype, doc.name, "modified", doc.modified, update_modified=False
        )


def on_host_update(doc, method=None):
    """Wildcard `on_update`. Three dict misses for every other doctype."""
    doctype = doc.doctype
    if doctype in EMBEDDED_FILE_FIELDS:
        adopt_embedded(doc, source_host=frappe.flags.seminary_adopt_from)
    if doctype in _host_doctypes():
        sync_public_state(doctype, doc.name)
        _refresh_registered_fields(doc)
    targets = DEPENDENTS.get(doctype)
    if targets:
        for dt, dn in targets(doc):
            sync_public_state(dt, dn)


def on_membership_gone(doc, method=None):
    """`after_delete` of an Academic Unit Membership: the person may have left
    their last published unit."""
    for dt, dn in _membership_targets(doc):
        sync_public_state(dt, dn)
