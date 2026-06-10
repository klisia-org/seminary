"""Import a Course Pack zip onto this site as fresh, fully-editable local docs.

Single request transaction; all validation up front, then strictly-ordered
writes so every reference resolves before use (media -> questions -> activities
-> SCAC -> chapters/lessons -> lesson SCAC-link remap). Mirrors the
validation-first, direct-child-insert, no-parent-save philosophy of
`Course Schedule.import_template`.

Known v1 limitation: Course Folder file contents are not bundled — folders are
recreated empty and a warning is returned.
"""

import hashlib
import io
import json
import zipfile

import frappe
from frappe import _
from frappe.utils import formatdate, nowdate, now
from frappe.utils.file_manager import save_file

from . import editorjs
from .constants import (
    IMPORT_ROLES,
    LESSON_SCAC_LINK_FIELDS,
    PACK_FORMAT_VERSION,
)

_SCAC_ACTIVITY_FIELDS = ("quiz", "assignment", "exam", "discussion")


class _Importer:
    def __init__(
        self, manifest, zf, target_mode, course, course_name, academic_term, section
    ):
        self.m = manifest
        self.zf = zf
        self.target_mode = target_mode
        self.course_arg = course
        self.course_name_arg = course_name
        self.academic_term = academic_term
        self.section = section
        self.warnings = []
        self.url_map = {}  # orig file_url -> new file_url
        self.q_map = {}  # src question name -> new
        self.a_map = (
            {}
        )  # src activity name -> new (folders merged in: foldername -> new)
        self.folder_map = {}  # src foldername -> new foldername
        self.scac_map = {}  # src SCAC row name -> new
        self.l_map = {}  # src lesson name -> new
        self.course = None
        self.grading_scale = None

    # --- helpers ----------------------------------------------------------
    def _rw(self, fields):
        """Rewrite media URLs inside a fields dict's string values."""
        return {
            k: (editorjs.rewrite_urls(v, self.url_map) if isinstance(v, str) else v)
            for k, v in fields.items()
        }

    @staticmethod
    def _has_field(doctype, fieldname):
        return frappe.get_meta(doctype).has_field(fieldname)

    @staticmethod
    def _dedupe_unique(doc):
        """Suffix any unique Data field whose value already exists, so an import
        into a site that already holds a doc with that value (e.g. Quiz.title)
        doesn't collide. References use docnames (via the id maps), not these
        values, so the suffix is purely cosmetic on the new copy."""
        for df in doc.meta.fields:
            if not df.unique or df.fieldtype not in ("Data", "Small Text"):
                continue
            base = doc.get(df.fieldname)
            if not base:
                continue
            value, n = base, 2
            while frappe.db.exists(doc.doctype, {df.fieldname: value}):
                value = f"{base} ({n})"
                n += 1
            if value != base:
                doc.set(df.fieldname, value)

    # --- institution-level deps ------------------------------------------
    def resolve_grading_scale(self):
        dep = (self.m.get("institution_deps") or {}).get("grading_scale")
        if not dep:
            return None
        name = dep["key"]
        if frappe.db.exists("Grading Scale", name):
            existing = frappe.get_doc("Grading Scale", name)
            if existing.get("maxnumgrade") != dep["record"].get("maxnumgrade") or len(
                existing.intervals
            ) != len(dep.get("intervals") or []):
                self.warnings.append(
                    _(
                        "Reused existing Grading Scale '{0}' (its configuration differs "
                        "from the pack's)."
                    ).format(name)
                )
            return name
        gs = frappe.new_doc("Grading Scale")
        gs.update(dep["record"])
        gs.grading_scale_name = name
        for iv in dep.get("intervals") or []:
            gs.append("intervals", iv)
        gs.flags.ignore_permissions = True
        gs.insert(ignore_mandatory=True)
        return gs.name

    def resolve_assessment_criteria(self):
        for name, meta in (
            (self.m.get("institution_deps") or {}).get("assessment_criteria") or {}
        ).items():
            if not frappe.db.exists("Assessment Criteria", name):
                frappe.get_doc(
                    {
                        "doctype": "Assessment Criteria",
                        "assessment_criteria": name,
                        "type": meta.get("type") or "Offline",
                    }
                ).insert(ignore_permissions=True)

    # --- course -----------------------------------------------------------
    def resolve_course(self):
        if self.target_mode == "existing":
            if not self.course_arg or not frappe.db.exists("Course", self.course_arg):
                frappe.throw(_("Select an existing Course to import into."))
            if not frappe.has_permission("Course", "write", doc=self.course_arg):
                frappe.throw(
                    _("You do not have write access to that Course."),
                    frappe.PermissionError,
                )
            return self.course_arg

        base = (
            self.course_name_arg or self.m["source"].get("course") or "Imported Course"
        )
        final, n = base, 2
        while frappe.db.exists("Course", final):
            final = f"{base} ({n})"
            n += 1
        course = frappe.new_doc("Course")
        course.course_name = final
        course.default_grading_scale = self.grading_scale
        course.flags.ignore_permissions = True
        course.insert(ignore_mandatory=True)
        if final != base:
            self.warnings.append(
                _("A Course named '{0}' already existed; imported as '{1}'.").format(
                    base, final
                )
            )
        return course.name

    # --- media ------------------------------------------------------------
    def import_media(self):
        # Folder files are recreated inside their folder (import_folders), not as
        # loose attachments, so skip them here.
        folder_media = self._folder_media_urls()
        for orig_url, meta in (self.m.get("media") or {}).items():
            if orig_url in folder_media:
                continue
            blob = self.zf.read(f"media/{meta['key']}")
            if hashlib.sha256(blob).hexdigest() != meta["sha256"]:
                frappe.throw(
                    _("Course Pack media integrity check failed for {0}.").format(
                        orig_url
                    )
                )
            fname = meta.get("file_name") or meta["key"].split("/")[-1]
            f = save_file(fname, blob, None, None, is_private=meta.get("is_private", 0))
            self.url_map[orig_url] = f.file_url

    def _folder_media_urls(self):
        urls = set()

        def walk(nodes):
            for n in nodes:
                if n.get("type") == "folder":
                    walk(n.get("children") or [])
                elif n.get("media"):
                    urls.add(n["media"])

        for rec in (self.m.get("folders") or {}).values():
            walk(rec.get("files") or [])
        return urls

    # --- course folders ---------------------------------------------------
    def import_folders(self):
        for old_name, rec in (self.m.get("folders") or {}).items():
            base = rec["foldername"]
            final, n = base, 2
            while frappe.db.exists(
                "Course Folder", {"course": self.course, "foldername": final}
            ):
                final = f"{base} ({n})"
                n += 1
            cf = frappe.get_doc(
                {"doctype": "Course Folder", "course": self.course, "foldername": final}
            )
            cf.flags.ignore_permissions = True
            cf.insert(ignore_mandatory=True)
            self._rebuild_folder_tree(cf.file_reference, rec.get("files") or [])
            self.folder_map[old_name] = final
            if final != base:
                self.warnings.append(
                    _("Folder '{0}' imported as '{1}' (name already in use).").format(
                        base, final
                    )
                )

    def _rebuild_folder_tree(self, parent_file, nodes):
        for node in nodes:
            if node.get("type") == "folder":
                sub = frappe.get_doc(
                    {
                        "doctype": "File",
                        "file_name": node["file_name"],
                        "is_folder": 1,
                        "folder": parent_file,
                        "is_private": 1,
                    }
                )
                sub.flags.ignore_permissions = True
                sub.insert(ignore_mandatory=True)
                self._rebuild_folder_tree(sub.name, node.get("children") or [])
            else:
                meta = (self.m.get("media") or {}).get(node.get("media"))
                if not meta:
                    continue
                blob = self.zf.read(f"media/{meta['key']}")
                f = frappe.get_doc(
                    {
                        "doctype": "File",
                        "file_name": node["file_name"],
                        "is_folder": 0,
                        "folder": parent_file,
                        "is_private": node.get("is_private", 0),
                        "content": blob,
                    }
                )
                f.flags.ignore_permissions = True
                f.insert(ignore_mandatory=True)

    # --- questions / activities ------------------------------------------
    def import_questions(self):
        for src, rec in (self.m.get("questions") or {}).items():
            d = frappe.new_doc(rec["doctype"])
            d.update(self._rw(rec["fields"]))
            if rec["doctype"] == "Question":
                d.course = self.course
                for it in rec.get("matching_items") or []:
                    d.append("matching_items", it)
            d.flags.ignore_permissions = True
            d.insert(ignore_mandatory=True)
            self.q_map[src] = d.name

    def import_activities(self):
        for src, rec in (self.m.get("activities") or {}).items():
            dt = rec["doctype"]
            d = frappe.new_doc(dt)
            d.update(self._rw(rec.get("fields") or {}))
            if self._has_field(dt, "course"):
                d.course = self.course
            if dt == "Quiz":
                for qq in rec.get("questions") or []:
                    d.append(
                        "questions",
                        {"question": self.q_map.get(qq["question"]), **qq["fields"]},
                    )
            elif dt == "Exam Activity":
                for eq in rec.get("questions") or []:
                    d.append(
                        "questions",
                        {"question": self.q_map.get(eq["question"]), **eq["fields"]},
                    )
            self._dedupe_unique(d)
            d.flags.ignore_permissions = True
            d.insert(ignore_mandatory=True)
            self.a_map[src] = d.name

    # --- course schedule shell + assessment ------------------------------
    def create_cs(self):
        cs = frappe.new_doc("Course Schedule")
        cs.course = self.course
        cs.academic_term = self.academic_term
        cs.section = self.section
        cs.gradesc_cs = self.grading_scale
        # Land in Draft (the workflow's initial state). Without this, before_insert
        # defaults the state to "Open for Enrollment" when the term is current,
        # and inserting straight into a non-default state trips validate_workflow
        # (no valid Draft->Open transition for a bare shell). Draft is also the
        # right resting state for a template the registrar completes/opens later,
        # and it skips the Open-state back-enrollment/waitlist side effects.
        cs.workflow_state = "Draft"
        # Placeholder dates WITHIN the chosen term (CS.validate_date requires it);
        # the registrar sets the real schedule later. The mandatory
        # instructors/modality check is skipped — this is a content template.
        term = (
            frappe.db.get_value(
                "Academic Term",
                self.academic_term,
                ["term_start_date", "term_end_date"],
                as_dict=True,
            )
            if self.academic_term
            else None
        )
        cs.c_datestart = (term and term.term_start_date) or nowdate()
        cs.c_dateend = (term and term.term_end_date) or nowdate()
        cs.modality = "Virtual"
        cs.flags.ignore_permissions = True
        cs.insert(ignore_mandatory=True)
        # The CS before_insert auto-seeds SCAC from the Course; clear it so we
        # carry the pack's rows exactly (same as import_template's replace).
        frappe.db.delete(
            "Scheduled Course Assess Criteria",
            {"parent": cs.name, "parenttype": "Course Schedule"},
        )
        return cs

    def import_scac(self, cs):
        for idx, rec in enumerate(self.m.get("scac") or [], start=1):
            row = frappe.get_doc(
                {
                    "doctype": "Scheduled Course Assess Criteria",
                    "parent": cs.name,
                    "parenttype": "Course Schedule",
                    "parentfield": "courseassescrit_sc",
                    "idx": idx,
                    "assesscriteria_scac": rec.get("assesscriteria_scac"),
                    **{
                        f: (self.a_map.get(rec.get(f)) if rec.get(f) else None)
                        for f in _SCAC_ACTIVITY_FIELDS
                    },
                    **rec["fields"],
                }
            )
            row.flags.ignore_permissions = True
            row.insert(ignore_mandatory=True)
            self.scac_map[rec["src_name"]] = row.name

    # --- chapters + lessons ----------------------------------------------
    def import_chapters_and_lessons(self, cs):
        n_chapters = n_lessons = 0
        for cidx, chrec in enumerate(self.m.get("chapters") or [], start=1):
            ch = frappe.new_doc("Course Schedule Chapter")
            ch.coursesc = cs.name
            ch.update(self._rw(chrec["fields"]))
            if chrec.get("scorm_media") and chrec["scorm_media"] in self.url_map:
                ch.scorm_package = frappe.db.get_value(
                    "File", {"file_url": self.url_map[chrec["scorm_media"]]}, "name"
                )
            ch.flags.ignore_permissions = True
            ch.insert(ignore_mandatory=True)
            n_chapters += 1
            self._reextract_scorm(ch)

            for lidx, lsrc in enumerate(chrec.get("lessons") or [], start=1):
                lrec = self.m["lessons"][lsrc]
                les = frappe.new_doc("Course Lesson")
                les.chapter = ch.name
                les.update(self._rewrite_lesson_fields(lrec["fields"]))
                les.flags.ignore_permissions = True
                les.insert(ignore_mandatory=True)
                self.l_map[lsrc] = les.name
                n_lessons += 1
                frappe.get_doc(
                    {
                        "doctype": "Course Schedule Lesson Reference",
                        "parent": ch.name,
                        "parenttype": "Course Schedule Chapter",
                        "parentfield": "lessons",
                        "idx": lidx,
                        "lesson": les.name,
                    }
                ).insert(ignore_permissions=True)

            frappe.get_doc(
                {
                    "doctype": "Course Schedule Chapter Reference",
                    "parent": cs.name,
                    "parenttype": "Course Schedule",
                    "parentfield": "chapters",
                    "idx": cidx,
                    "chapter": ch.name,
                }
            ).insert(ignore_permissions=True)
        return n_chapters, n_lessons

    def _rewrite_lesson_fields(self, fields):
        out = self._rw(fields)
        for f in ("content", "instructor_content"):
            out[f] = editorjs.rewrite_urls(
                editorjs.rewrite_content_refs(out.get(f), self.a_map), self.url_map
            )
        for f in ("body", "instructor_notes"):
            out[f] = editorjs.rewrite_urls(
                editorjs.rewrite_body_refs(out.get(f), self.a_map), self.url_map
            )
        return out

    def _reextract_scorm(self, ch):
        if not (ch.get("is_scorm_package") and ch.get("scorm_package")):
            return
        from seminary.seminary.api import (
            extract_package,
            get_launch_file,
            get_manifest_file,
        )

        pkg = frappe._dict({"name": ch.scorm_package})
        extract_path = extract_package(self.course, ch.chapter_title, pkg)
        manifest_file = get_manifest_file(extract_path)
        launch_file = get_launch_file(extract_path)
        frappe.db.set_value(
            "Course Schedule Chapter",
            ch.name,
            {
                "scorm_package_path": extract_path.split("public")[1],
                "manifest_file": (
                    manifest_file.split("public")[1] if manifest_file else None
                ),
                "launch_file": launch_file.split("public")[1] if launch_file else None,
            },
        )

    def remap_lesson_scac_links(self):
        for lsrc, new_lesson in self.l_map.items():
            links = (self.m["lessons"][lsrc].get("scac_links")) or {}
            update = {}
            for field in LESSON_SCAC_LINK_FIELDS:
                src_scac = links.get(field)
                if src_scac and self.scac_map.get(src_scac):
                    update[field] = self.scac_map[src_scac]
            if update:
                frappe.db.set_value("Course Lesson", new_lesson, update)

    # --- orchestration ----------------------------------------------------
    def run(self):
        self.grading_scale = self.resolve_grading_scale()
        self.resolve_assessment_criteria()
        self.course = self.resolve_course()
        self.import_media()
        self.import_questions()
        self.import_activities()
        self.import_folders()
        # Lesson content references folders by foldername; remap alongside
        # activity docnames so a deduped folder name still resolves.
        self.a_map.update(self.folder_map)
        cs = self.create_cs()
        self.import_scac(cs)
        n_ch, n_les = self.import_chapters_and_lessons(cs)
        self.remap_lesson_scac_links()

        cs.add_comment(
            "Info",
            _(
                "Imported Course Pack '{0}' on {1} by {2}: {3} chapters, {4} lessons, "
                "{5} activities, {6} questions."
            ).format(
                self.m["source"].get("title") or self.m["source"].get("course"),
                formatdate(now()),
                frappe.session.user,
                n_ch,
                n_les,
                len(self.a_map),
                len(self.q_map),
            ),
        )
        return {
            "course": self.course,
            "course_schedule": cs.name,
            "chapters": n_ch,
            "lessons": n_les,
            "activities": len(self.a_map) - len(self.folder_map),
            "questions": len(self.q_map),
            "folders": len(self.folder_map),
            "media": len(self.url_map),
            "warnings": self.warnings,
        }


def _read_pack_bytes(file_url):
    name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not name:
        frappe.throw(_("Uploaded Course Pack file not found."))
    content = frappe.get_doc("File", name).get_content(encodings=[])
    if isinstance(content, str):
        content = content.encode("utf-8")
    return content


def _validate_pack(manifest):
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(IMPORT_ROLES):
        frappe.throw(
            _(
                "Only Program Chair, Seminary Manager, or Registrar can import course packs."
            ),
            frappe.PermissionError,
        )
    version = manifest.get("pack_format_version")
    if version is None or version > PACK_FORMAT_VERSION:
        frappe.throw(
            _(
                "This Course Pack (format v{0}) is newer than this site supports (v{1}). "
                "Update the app first."
            ).format(version, PACK_FORMAT_VERSION)
        )


def import_pack_from_bytes(
    content,
    target_mode,
    course=None,
    course_name=None,
    academic_term=None,
    section=None,
):
    """Core import from raw zip bytes — reusable in tests."""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        _validate_pack(manifest)
        return _Importer(
            manifest, zf, target_mode, course, course_name, academic_term, section
        ).run()


@frappe.whitelist()
def import_course_pack(
    file_url,
    target_mode,
    course=None,
    course_name=None,
    academic_term=None,
    section=None,
):
    """Import an uploaded Course Pack. `file_url` is a prior /api/method/upload_file
    result. `target_mode` is 'new' or 'existing'."""
    content = _read_pack_bytes(file_url)
    return import_pack_from_bytes(
        content,
        target_mode,
        course=course,
        course_name=course_name,
        academic_term=academic_term,
        section=section,
    )
