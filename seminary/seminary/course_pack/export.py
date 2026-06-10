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
        self.media_blobs = {}  # media key -> bytes
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
        content = fdoc.get_content(encodings=[])
        if isinstance(content, str):
            content = content.encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        ext = os.path.splitext(rows[0].file_name or "")[1]
        sub = "private" if rows[0].is_private else "public"
        key = f"{sub}/{digest[:16]}{ext}"
        self.media[url] = {
            "key": key,
            "sha256": digest,
            "size": len(content),
            "is_private": int(rows[0].is_private or 0),
            "file_name": rows[0].file_name,
        }
        self.media_blobs[key] = content

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
        }

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
        }
        return manifest

    def _collect_scac(self):
        scac = []
        for row in self.cs.courseassescrit_sc:
            rec = {"src_name": row.name, "fields": self._pick(row, SCAC_FIELDS)}
            rec["assesscriteria_scac"] = row.assesscriteria_scac
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


def build_pack_bytes(cs_name):
    """Return (filename, zip_bytes) for a Course Schedule. Reusable in tests."""
    exporter = _Exporter(cs_name)
    manifest = exporter.build()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=1, default=str))
        for key, blob in exporter.media_blobs.items():
            archive.writestr(f"media/{key}", blob)

    slug = frappe.scrub(manifest["source"].get("course") or "course")
    filename = f"coursepack-{slug}-{frappe.utils.nowdate().replace('-', '')}.zip"
    return filename, buffer.getvalue()


@frappe.whitelist(methods=["GET"])
def export_course_pack(course_schedule):
    """Stream a Course Pack zip for the given Course Schedule (read-only)."""
    _validate_export(course_schedule)
    filename, content = build_pack_bytes(course_schedule)
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "attachment"
