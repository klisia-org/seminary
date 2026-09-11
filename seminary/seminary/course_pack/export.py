"""Export a Course Schedule's full authored content as a portable Course Pack zip.

Identity model: every exported doc is keyed in the manifest by its **source
docname**, and lesson content keeps its references verbatim. Import never assumes
those names are free on the target — it creates fresh docs and remaps
(source_name -> new_name, source_url -> new_url) in a single pass, exactly the
`source_name -> new_name` map approach already used by
`Course Schedule.import_template`.

Per-instance state (roster, grades, dates, room, instructors, workflow, …) is
never carried: the manifest only stores the content allow-lists in constants.py.
"""

import hashlib
import io
import json
import os
import zipfile
from urllib.parse import unquote

import frappe
from frappe import _
from frappe.utils import now

from . import editorjs
from .constants import (
    ASSIGNMENT_FIELDS,
    CHAPTER_FIELDS,
    DISCUSSION_FIELDS,
    EXAM_FIELDS,
    EXAM_QUESTION_FIELDS,
    EXPORT_ROLES,
    COURSE_COMPETENCY_DIMENSION_FIELDS,
    COURSE_COMPETENCY_FIELDS,
    ASSESSMENT_DIMENSION_WEIGHT_FIELDS,
    GRADING_SCALE_DIMENSION_FIELDS,
    GRADING_SCALE_FIELDS,
    GRADING_SCALE_INTERVAL_FIELDS,
    LESSON_FIELDS,
    LESSON_SCAC_LINK_FIELDS,
    OPEN_QUESTION_FIELDS,
    PACK_FORMAT_VERSION,
    QUESTION_FIELDS,
    QUIZ_FIELDS,
    QUIZ_QUESTION_FIELDS,
    SCAC_FIELDS,
    SCRIPTURE_MATCHING_ITEM_FIELDS,
)

_ACTIVITY_LINK_FIELDS = (
    ("quiz", "Quiz"),
    ("assignment", "Assignment Activity"),
    ("exam", "Exam Activity"),
    ("discussion", "Discussion Activity"),
)


class _Exporter:
    def __init__(self, cs_name):
        self.cs = frappe.get_doc("Course Schedule", cs_name)
        self.media = {}  # orig_url -> meta dict
        # media key -> source File docname. Deliberately NOT the bytes: a pack of
        # lecture video would otherwise sit in worker memory in its entirety, on
        # top of the assembled zip. Blobs are streamed in at write time instead.
        self.media_sources = {}
        self.questions = {}  # src_name -> record
        self.activities = {}  # src_name -> record
        self.folders = {}  # foldername -> {foldername, files: tree}
        self.assessment_criteria = {}  # name -> {type}
        self._seen_q = set()
        self._seen_a = set()
        self._seen_folders = set()

    # --- helpers ----------------------------------------------------------
    @staticmethod
    def _pick(doc, fields):
        return {f: doc.get(f) for f in fields}

    def _add_media_url(self, url):
        """Bundle a local File referenced by `url`. No-op for external/missing.

        Rich-text URLs are often percent-encoded (e.g. spaces as %20) while the
        File's stored `file_url` has literal characters, so we look up by both
        the raw and the decoded form. The pack keys media by the exact string
        found in content, so the import-side rewrite matches.
        """
        if not url or url in self.media:
            return
        rows = None
        for candidate in dict.fromkeys([url, unquote(url)]):
            rows = frappe.get_all(
                "File",
                filters={"file_url": candidate},
                fields=["name", "is_private", "file_name"],
                limit=1,
            )
            if rows:
                break
        if not rows:
            return
        fdoc = frappe.get_doc("File", rows[0].name)
        digest, size = _hash_media(fdoc)
        ext = os.path.splitext(rows[0].file_name or "")[1]
        sub = "private" if rows[0].is_private else "public"
        key = f"{sub}/{digest[:16]}{ext}"
        self.media[url] = {
            "key": key,
            "sha256": digest,
            "size": size,
            "is_private": int(rows[0].is_private or 0),
            "file_name": rows[0].file_name,
        }
        # Remember where to stream from, not what to stream. Several URLs can map
        # to one key (identical content), and the first source wins — they are by
        # definition byte-identical.
        self.media_sources.setdefault(key, fdoc.name)

    def _scan_media(self, fields):
        for value in fields.values():
            for url in editorjs.scan_urls(value):
                self._add_media_url(url)

    # --- questions / activities ------------------------------------------
    def _ensure_question(self, doctype, name):
        if not name or name in self._seen_q:
            return
        self._seen_q.add(name)
        if not frappe.db.exists(doctype, name):
            return  # dangling reference (deleted) — tolerate, like the frontend
        q = frappe.get_doc(doctype, name)
        if doctype == "Question":
            rec = {
                "doctype": "Question",
                "fields": self._pick(q, QUESTION_FIELDS),
                "matching_items": [
                    self._pick(r, SCRIPTURE_MATCHING_ITEM_FIELDS)
                    for r in q.get("matching_items") or []
                ],
            }
        else:  # Open Question
            rec = {
                "doctype": "Open Question",
                "fields": self._pick(q, OPEN_QUESTION_FIELDS),
            }
        self._scan_media(rec["fields"])
        self.questions[name] = rec

    def _ensure_activity(self, doctype, name):
        if not name or name in self._seen_a:
            return
        self._seen_a.add(name)
        if not frappe.db.exists(doctype, name):
            return  # dangling reference (deleted) — tolerate, like the frontend
        a = frappe.get_doc(doctype, name)
        rec = {"doctype": doctype}
        if doctype == "Quiz":
            rec["fields"] = self._pick(a, QUIZ_FIELDS)
            rec["questions"] = []
            for qq in a.get("questions") or []:
                self._ensure_question("Question", qq.question)
                rec["questions"].append(
                    {
                        "fields": self._pick(qq, QUIZ_QUESTION_FIELDS),
                        "question": qq.question,
                    }
                )
        elif doctype == "Exam Activity":
            rec["fields"] = self._pick(a, EXAM_FIELDS)
            rec["questions"] = []
            for eq in a.get("questions") or []:
                self._ensure_question("Open Question", eq.question)
                rec["questions"].append(
                    {
                        "fields": self._pick(eq, EXAM_QUESTION_FIELDS),
                        "question": eq.question,
                    }
                )
        elif doctype == "Assignment Activity":
            rec["fields"] = self._pick(a, ASSIGNMENT_FIELDS)
        elif doctype == "Discussion Activity":
            rec["fields"] = self._pick(a, DISCUSSION_FIELDS)
        self._scan_media(rec.get("fields", {}))
        self.activities[name] = rec

    # --- course folders (referenced by foldername, not docname) ----------
    def _ensure_folder(self, foldername):
        """Bundle a Course Folder's file tree. Lesson content references folders
        by foldername (the FolderTool stores `data.folder = foldername`), so we
        resolve the Course Folder by (foldername, course) and walk its File tree."""
        if not foldername or foldername in self._seen_folders:
            return
        self._seen_folders.add(foldername)
        cf = frappe.db.get_value(
            "Course Folder",
            {"foldername": foldername, "course": self.cs.course},
            ["name", "file_reference"],
            as_dict=True,
        ) or frappe.db.get_value(
            "Course Folder",
            {"foldername": foldername},
            ["name", "file_reference"],
            as_dict=True,
        )
        if not cf or not cf.file_reference:
            return  # dangling reference — tolerate
        self.folders[foldername] = {
            "foldername": foldername,
            "files": self._walk_folder(cf.file_reference, set()),
        }

    def _walk_folder(self, folder_id, visited):
        if folder_id in visited:
            return []
        visited.add(folder_id)
        nodes = []
        for e in frappe.get_all(
            "File",
            filters={"folder": folder_id},
            fields=["name", "file_name", "is_folder", "file_url", "is_private"],
            order_by="is_folder desc, file_name asc",
            ignore_permissions=True,
        ):
            if e.is_folder:
                nodes.append(
                    {
                        "type": "folder",
                        "file_name": e.file_name,
                        "children": self._walk_folder(e.name, visited),
                    }
                )
            elif e.file_url:
                self._add_media_url(e.file_url)
                nodes.append(
                    {
                        "type": "file",
                        "file_name": e.file_name,
                        "media": e.file_url,
                        "is_private": int(e.is_private or 0),
                    }
                )
        return nodes

    # --- institution-level deps ------------------------------------------
    def _grading_scale(self):
        name = self.cs.gradesc_cs
        if not name or not frappe.db.exists("Grading Scale", name):
            return None
        gs = frappe.get_doc("Grading Scale", name)
        return {
            "key": name,
            "record": self._pick(gs, GRADING_SCALE_FIELDS),
            "intervals": [
                self._pick(r, GRADING_SCALE_INTERVAL_FIELDS) for r in gs.intervals
            ],
            "dimensions": [
                self._pick(r, GRADING_SCALE_DIMENSION_FIELDS)
                for r in (gs.get("gradingscaledimensions") or [])
            ],
        }

    def _competencies(self):
        """Course competencies travel with the pack (ADR 065).

        They are course-level curriculum, not a per-offering choice, so a pack
        without them would import a competency-based course that cannot be
        graded. Keyed by competency_code, which is the stable identifier
        assessments and chapters are remapped against on import.
        """
        rows = []
        for name in frappe.get_all(
            "Course Competency", filters={"course": self.cs.course}, pluck="name"
        ):
            doc = frappe.get_doc("Course Competency", name)
            rows.append(
                {
                    "src_name": name,
                    "fields": self._pick(doc, COURSE_COMPETENCY_FIELDS),
                    "dimensions": [
                        self._pick(d, COURSE_COMPETENCY_DIMENSION_FIELDS)
                        for d in (doc.dimensions or [])
                    ],
                }
            )
        return rows

    def _add_assessment_criteria(self, name):
        if not name or name in self.assessment_criteria:
            return
        ac_type = frappe.db.get_value("Assessment Criteria", name, "type")
        self.assessment_criteria[name] = {"type": ac_type}

    # --- main build -------------------------------------------------------
    def build(self):
        scac = self._collect_scac()
        chapters, lessons = self._collect_chapters_and_lessons()
        manifest = {
            "pack_format_version": PACK_FORMAT_VERSION,
            "generated_at": now(),
            "generator": {
                "app": "seminary",
                "site": frappe.local.site,
                "language": _site_language(),
            },
            "source": {
                "course": self.cs.course,
                "course_code": self.cs.get("coursecode_cs"),
                "course_schedule": self.cs.name,
                "title": self.cs.get("title"),
            },
            "institution_deps": {
                "grading_scale": self._grading_scale(),
                "assessment_criteria": self.assessment_criteria,
            },
            "media": self.media,
            "questions": self.questions,
            "activities": self.activities,
            "folders": self.folders,
            "chapters": chapters,
            "lessons": lessons,
            "scac": scac,
            "competencies": self._competencies(),
        }
        return manifest

    def _collect_scac(self):
        scac = []
        for row in self.cs.courseassescrit_sc:
            rec = {"src_name": row.name, "fields": self._pick(row, SCAC_FIELDS)}
            rec["assesscriteria_scac"] = row.assesscriteria_scac
            # Carried by code, not by record name: the competency is recreated
            # on the target site with a different name (ADR 065).
            rec["competency_code"] = (
                frappe.db.get_value(
                    "Course Competency", row.course_competency, "competency_code"
                )
                if row.get("course_competency")
                else None
            )
            rec["dimension_weights"] = frappe.get_all(
                "Assessment Dimension Weight",
                filters={"assess_criteria": row.name},
                fields=list(ASSESSMENT_DIMENSION_WEIGHT_FIELDS),
            )
            self._add_assessment_criteria(row.assesscriteria_scac)
            for field, doctype in _ACTIVITY_LINK_FIELDS:
                value = row.get(field)
                rec[field] = value or None
                if value:
                    self._ensure_activity(doctype, value)
            scac.append(rec)
        return scac

    def _collect_chapters_and_lessons(self):
        chapters = []
        lessons = {}
        chapter_refs = frappe.get_all(
            "Course Schedule Chapter Reference",
            filters={"parent": self.cs.name, "parenttype": "Course Schedule"},
            fields=["chapter", "idx"],
            order_by="idx asc",
        )
        for cref in chapter_refs:
            if not cref.chapter or not frappe.db.exists(
                "Course Schedule Chapter", cref.chapter
            ):
                continue
            ch = frappe.get_doc("Course Schedule Chapter", cref.chapter)
            chrec = {
                "src_name": ch.name,
                "fields": self._pick(ch, CHAPTER_FIELDS),
                "scorm_media": None,
                "lessons": [],
                # By code, not by record name: the competency is recreated under
                # a different name on the target site (ADR 065). This mapping is
                # what gives a competency its place in the outline, and with it
                # the end-of-competency self-assessment trigger and content
                # gating, so a pack that dropped it would import a course whose
                # pacing silently stopped working.
                "competency_code": (
                    frappe.db.get_value(
                        "Course Competency", ch.course_competency, "competency_code"
                    )
                    if ch.get("course_competency")
                    else None
                ),
            }
            if ch.get("scorm_package"):
                furl = frappe.db.get_value("File", ch.scorm_package, "file_url")
                if furl:
                    self._add_media_url(furl)
                    chrec["scorm_media"] = furl

            lesson_refs = frappe.get_all(
                "Course Schedule Lesson Reference",
                filters={"parent": ch.name, "parenttype": "Course Schedule Chapter"},
                fields=["lesson", "idx"],
                order_by="idx asc",
            )
            for lref in lesson_refs:
                if not lref.lesson or not frappe.db.exists(
                    "Course Lesson", lref.lesson
                ):
                    continue
                lesson = frappe.get_doc("Course Lesson", lref.lesson)
                fields = self._pick(lesson, LESSON_FIELDS)
                refs = (
                    editorjs.scan_content_refs(lesson.content)
                    + editorjs.scan_content_refs(lesson.instructor_content)
                    + editorjs.scan_body_refs(lesson.body)
                    + editorjs.scan_body_refs(lesson.instructor_notes)
                )
                for doctype, name in refs:
                    if doctype == "Course Folder":
                        self._ensure_folder(name)
                    else:
                        self._ensure_activity(doctype, name)
                self._scan_media(fields)
                scac_links = {
                    f: lesson.get(f) for f in LESSON_SCAC_LINK_FIELDS if lesson.get(f)
                }
                lessons[lesson.name] = {"fields": fields, "scac_links": scac_links}
                chrec["lessons"].append(lesson.name)
            chapters.append(chrec)
        return chapters, lessons


def _site_language():
    """The site's default language as a 2-letter ISO 639-1 code (e.g. 'pt-BR'
    -> 'pt'). Lets a course library filter/group packs by language."""
    lang = frappe.db.get_single_value("System Settings", "language") or "en"
    return lang.split("-")[0].lower()[:2]


def _validate_export(cs_name):
    if not frappe.db.exists("Course Schedule", cs_name):
        frappe.throw(_("Course Schedule {0} does not exist.").format(cs_name))
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(EXPORT_ROLES):
        frappe.throw(
            _(
                "Only Program Chair, Seminary Manager, or Registrar can export course packs."
            ),
            frappe.PermissionError,
        )
    if not frappe.has_permission("Course Schedule", "read", doc=cs_name):
        frappe.throw(
            _("You do not have read access to this Course Schedule."),
            frappe.PermissionError,
        )


def _hash_media(file_doc):
    """Return `(sha256_hex, size)` for a File, reading it in chunks.

    Streamed rather than loaded so that hashing a 500 MB lecture recording costs
    a constant amount of memory. Works whether the bytes are on local disk or in
    object storage (privatedocs/p004).

    The digest is over the raw bytes, exactly as the previous
    `get_content(encodings=[])` implementation was, so pack keys for existing
    content are unchanged and old packs stay comparable.
    """
    from seminary.storage.files import open_stream

    digest = hashlib.sha256()
    size = 0
    with open_stream(file_doc) as chunks:
        for chunk in chunks:
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _write_pack(exporter, manifest, fileobj):
    """Write the pack zip into `fileobj`, streaming each media blob through.

    `manifest.json` is written **last**. The importer reads entries by name
    (`zf.read("manifest.json")`, `zf.read(f"media/{key}")`), which resolves
    through the central directory, so physical order carries no meaning — and
    writing media first means a blob is never held in memory waiting for the
    manifest.
    """
    from seminary.storage.files import open_stream

    with zipfile.ZipFile(fileobj, "w", zipfile.ZIP_DEFLATED) as archive:
        for key, source in exporter.media_sources.items():
            with (
                open_stream(source) as chunks,
                archive.open(f"media/{key}", "w") as target,
            ):
                for chunk in chunks:
                    target.write(chunk)
        archive.writestr("manifest.json", json.dumps(manifest, indent=1, default=str))


def _pack_filename(manifest):
    slug = frappe.scrub(manifest["source"].get("course") or "course")
    return f"coursepack-{slug}-{frappe.utils.nowdate().replace('-', '')}.zip"


def build_pack_bytes(cs_name):
    """Return (filename, zip_bytes) for a Course Schedule. Reusable in tests.

    Holds the whole pack in memory, so it is for tests and small packs. The
    served export path (`export_course_pack`) avoids this whenever object
    storage is configured.
    """
    exporter = _Exporter(cs_name)
    manifest = exporter.build()

    buffer = io.BytesIO()
    _write_pack(exporter, manifest, buffer)
    return _pack_filename(manifest), buffer.getvalue()


PACK_FOLDER = "Course Packs"


def _pack_folder():
    """The File folder generated packs live in, created on first use.

    A folder rather than a filename convention so packs are visible and
    manageable in the File UI, and so `cleanup_old_packs` has an unambiguous
    thing to sweep.
    """
    name = f"Home/{PACK_FOLDER}"
    if frappe.db.exists("File", name):
        return name
    folder = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": PACK_FOLDER,
            "is_folder": 1,
            "folder": "Home",
        }
    )
    folder.flags.ignore_permissions = True
    folder.insert(ignore_if_duplicate=True)
    return folder.name


def _store_pack(exporter, manifest, filename, cs_name):
    """Assemble the pack on disk, upload it in parts, return its File row.

    Memory stays flat: the zip is written to a temporary file and streamed to
    object storage, so neither the media nor the assembled pack is ever a single
    `bytes` in the worker. That is the point of this path — ADR 041 noted
    building packs in memory as a caveat to revisit, and a pack of recorded video
    is exactly where it hurts.

    The File row is created with `file_url` already pointing at object storage, so
    `File.is_remote_file` is true and Frappe's disk pipeline no-ops. `content_hash`
    is MD5 to match `frappe.core.doctype.file.utils.get_content_hash`, which is
    what the delete refcount compares — and it is computed here rather than taken
    from the upload's ETag, because a multipart ETag is not a content hash.
    """
    import tempfile

    from seminary.storage import get_storage_backend
    from seminary.storage.backend import object_key, url_for_key

    backend = get_storage_backend()

    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
        _write_pack(exporter, manifest, tmp)
        tmp.flush()
        size = tmp.tell()

        # Not a security hash: MD5 is what frappe's own `get_content_hash` uses,
        # and the delete refcount compares against that value.
        digest = hashlib.md5(usedforsecurity=False)
        tmp.seek(0)
        for chunk in iter(lambda: tmp.read(1024 * 1024), b""):
            digest.update(chunk)
        content_hash = digest.hexdigest()

        key = object_key(content_hash)
        tmp.seek(0)
        backend.put_fileobj(key, tmp, content_type="application/zip")

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": filename,
            "file_url": url_for_key(key),
            "is_private": 1,
            "file_size": size,
            "content_hash": content_hash,
            "folder": _pack_folder(),
            "attached_to_doctype": "Course Schedule",
            "attached_to_name": cs_name,
        }
    )
    file_doc.flags.ignore_permissions = True
    file_doc.insert()
    return file_doc


@frappe.whitelist(methods=["GET"])
def export_course_pack(course_schedule):
    """Serve a Course Pack zip for the given Course Schedule (read-only).

    With object storage configured the pack is assembled on disk, uploaded, and
    handed back as a redirect to its permission-checked download URL — so the
    bytes reach the browser from object storage and never traverse a worker, and
    pack egress costs nothing. Without it, behaviour is unchanged: the pack is
    built in memory and streamed through the response as before.
    """
    _validate_export(course_schedule)

    from seminary.storage import get_storage_backend

    exporter = _Exporter(course_schedule)
    manifest = exporter.build()
    filename = _pack_filename(manifest)

    if not get_storage_backend().is_configured():
        buffer = io.BytesIO()
        _write_pack(exporter, manifest, buffer)
        frappe.local.response.filename = filename
        frappe.local.response.filecontent = buffer.getvalue()
        frappe.local.response.type = "download"
        frappe.local.response.display_content_as = "attachment"
        return

    file_doc = _store_pack(exporter, manifest, filename, course_schedule)
    # Redirect to our own download endpoint rather than straight to a presigned
    # URL, so the pack is served through the same permission check as any other
    # offloaded file instead of a second, parallel authorization path.
    frappe.local.response.type = "redirect"
    frappe.local.response.location = file_doc.file_url


def cleanup_old_packs():
    """Delete generated packs past their retention window (daily scheduler).

    Packs are reproducible artifacts, not records: keeping them forever would
    grow object storage without bound, one copy per export. Deleting the File row
    is enough — the storage delete hook removes the object once no row references
    that content (privatedocs/p004).
    """
    days = frappe.conf.get("course_pack_retention_days", 7)
    if not days:
        return

    folder = f"Home/{PACK_FOLDER}"
    if not frappe.db.exists("File", folder):
        return

    cutoff = frappe.utils.add_days(now(), -int(days))
    stale = frappe.get_all(
        "File",
        filters={"folder": folder, "is_folder": 0, "creation": ["<", cutoff]},
        pluck="name",
    )
    for name in stale:
        try:
            frappe.delete_doc(
                "File", name, ignore_permissions=True, delete_permanently=True
            )
        except Exception:
            frappe.log_error(
                title="course_pack: could not delete expired pack",
                message=f"{name}\n{frappe.get_traceback()}",
            )
