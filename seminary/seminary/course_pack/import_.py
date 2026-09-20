"""Import a Course Pack zip onto this site as fresh, fully-editable local docs.

Single request transaction; all validation up front, then strictly-ordered
writes so every reference resolves before use (media -> questions -> activities
-> SCAC -> chapters/lessons -> lesson SCAC-link remap). Mirrors the
validation-first, direct-child-insert, no-parent-save philosophy of
`Course Schedule.import_template`.

Course Folders travel with the pack (p006 F2, ADR §2.2b): each folder's file
tree is bundled and rebuilt here under the scope mapping in `import_folders`,
every folder file is stored private, and one `Course Folder Activity` row
records the pack it came from. School folders are never in a pack; the
exporter's warnings name them and are surfaced here.
"""

import hashlib
import io
import json
import zipfile

import frappe
from frappe import _
from frappe.utils import formatdate, nowdate, now

from . import editorjs
from .constants import (
    ASSESSMENT_DIMENSION_WEIGHT_FIELDS,
    CHAPTER_FIELDS,
    COURSE_COMPETENCY_DIMENSION_FIELDS,
    COURSE_COMPETENCY_FIELDS,
    EXAM_QUESTION_FIELDS,
    GRADING_SCALE_DIMENSION_FIELDS,
    GRADING_SCALE_FIELDS,
    GRADING_SCALE_INTERVAL_FIELDS,
    IMPORT_ROLES,
    IMPORTABLE_DOCTYPES,
    LESSON_FIELDS,
    LESSON_SCAC_LINK_FIELDS,
    MAX_PACK_BYTES,
    MAX_PACK_ENTRIES,
    MAX_PACK_MEMBER_BYTES,
    MAX_PACK_MANIFEST_BYTES,
    MAX_PACK_RATIO,
    MAX_PACK_UNCOMPRESSED_BYTES,
    PACK_FORMAT_VERSION,
    PACK_RATIO_FLOOR_BYTES,
    QUIZ_QUESTION_FIELDS,
    SCAC_FIELDS,
    SCRIPTURE_MATCHING_ITEM_FIELDS,
)


def _only(fields, allowed):
    """The manifest's field dict, reduced to the pack allow-list (p008 F9). What
    the exporter never writes, the importer never reads -- so `owner`,
    `docstatus`, `name`, `doctype`, `parent` and the like cannot ride in."""
    if not isinstance(fields, dict):
        return {}
    return {k: v for k, v in fields.items() if k in allowed}


def _importable(section, doctype):
    """The field allow-list for a record of ``doctype`` in manifest ``section``,
    or a refusal: a doctype the pack format does not define is not version skew."""
    allowed = IMPORTABLE_DOCTYPES[section].get(doctype)
    if allowed is None:
        frappe.throw(
            _(
                "This Course Pack contains a record type this site will not import: {0}."
            ).format(frappe.utils.escape_html(str(doctype))),
            frappe.ValidationError,
        )
    return allowed


_SCAC_ACTIVITY_FIELDS = ("quiz", "assignment", "exam", "discussion")


class _Importer:
    def __init__(
        self,
        manifest,
        zf,
        target_mode,
        course,
        course_name,
        academic_term,
        section,
        instructor=None,
    ):
        self.m = manifest
        self.zf = zf
        self.target_mode = target_mode
        self.course_arg = course
        self.course_name_arg = course_name
        self.academic_term = academic_term
        self.section = section
        # Destination Instructor: Instructor- and Section-scope folders in the
        # pack become this professor's Instructor folders (Course scope if none).
        self.instructor = instructor or None
        self.warnings = []
        self.url_map = {}  # orig file_url -> new file_url
        self.q_map = {}  # src question name -> new
        self.a_map = {}  # src activity name -> new
        # src folder key (docname; foldername in packs older than p006) -> new
        # Course Folder docname, and new docname -> display label.
        self.folder_map = {}
        self.folder_labels = {}
        self.scac_map = {}  # src SCAC row name -> new
        self.competency_map = {}  # competency_code -> new Course Competency name
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
        gs.update(_only(dep.get("record"), GRADING_SCALE_FIELDS))
        gs.grading_scale_name = name
        for iv in dep.get("intervals") or []:
            gs.append("intervals", _only(iv, GRADING_SCALE_INTERVAL_FIELDS))
        for dim in dep.get("dimensions") or []:
            gs.append(
                "gradingscaledimensions", _only(dim, GRADING_SCALE_DIMENSION_FIELDS)
            )
        gs.flags.ignore_permissions = True
        gs.insert(ignore_mandatory=True)
        return gs.name

    def import_competencies(self, course):
        """Recreate the course's competencies, keyed by competency_code.

        Existing codes are reused rather than duplicated: importing a pack twice
        into the same course must not produce two copies of every competency,
        and any assessment already pointing at one has to keep pointing at it.
        """
        for rec in self.m.get("competencies") or []:
            code = (rec.get("fields") or {}).get("competency_code")
            if not code:
                continue
            existing = frappe.db.get_value(
                "Course Competency", {"course": course, "competency_code": code}, "name"
            )
            if existing:
                self.competency_map[code] = existing
                continue
            doc = frappe.new_doc("Course Competency")
            doc.update(_only(rec.get("fields"), COURSE_COMPETENCY_FIELDS))
            doc.course = course
            for dim in rec.get("dimensions") or []:
                doc.append("dimensions", _only(dim, COURSE_COMPETENCY_DIMENSION_FIELDS))
            doc.flags.ignore_permissions = True
            doc.insert(ignore_mandatory=True)
            self.competency_map[code] = doc.name

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
        # coursecode is mandatory and unique on Course, and it was never set
        # here (insert runs with ignore_mandatory). Course Competency names
        # itself "{coursecode}-{competency_code}", so every competency of every
        # imported course was named "-<code>" -- and the second import of any
        # pack collided with the first (p006 §7.3, p008 F10). The manifest has
        # carried the source's code all along.
        course.coursecode = self._unique_coursecode(final)
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

    def _unique_coursecode(self, course_name):
        source = self.m.get("source") if isinstance(self.m.get("source"), dict) else {}
        base = str(source.get("course_code") or "").strip()
        # a code is an identifier: no markup, no path, bounded
        base = "".join(c for c in base if c.isalnum() or c in "-_ .")[:60].strip()
        base = base or frappe.scrub(course_name).upper()[:60]
        code, n = base, 2
        while frappe.db.exists("Course", {"coursecode": code}):
            code = f"{base}-{n}"
            n += 1
        return code

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
            # A File *document*, not `file_manager.save_file`: that helper's size
            # check reads `conf.max_file_size` alone and falls back to 10 MB,
            # ignoring System Settings, so importing a pack carrying any sizeable
            # lecture video failed against a limit nobody had configured.
            f = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": fname,
                    "content": blob,
                    # Always private, whatever the manifest says -- as the folder
                    # files below already are. file_policy adopts it onto the new
                    # section when the lesson that embeds it is saved.
                    "is_private": 1,
                }
            ).insert(ignore_permissions=True)
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
    def _mapped_scope(self, original):
        """§2.2b: Course stays Course; Instructor and Section become the
        destination instructor's, or Course when none was chosen; School is
        never in a pack."""
        if original in ("Instructor", "Section"):
            return (
                ("Instructor", self.instructor) if self.instructor else ("Course", None)
            )
        return ("Course", None)

    def import_folders(self):
        from seminary.seminary.doctype.course_folder.course_folder import log_activity

        src = self.m.get("source") or {}
        gen = self.m.get("generator") or {}
        provenance = _("from pack {0} exported {1} by {2}").format(
            src.get("title") or src.get("course") or "?",
            (
                formatdate(self.m.get("generated_at"))
                if self.m.get("generated_at")
                else "?"
            ),
            gen.get("site") or "?",
        )

        for old_key, rec in (self.m.get("folders") or {}).items():
            original_scope = rec.get("scope") or "Course"
            if original_scope == "School":
                self.warnings.append(
                    _(
                        "School folder '{0}' is not carried by a pack; embed your "
                        "own policies folder."
                    ).format(rec.get("foldername"))
                )
                continue
            scope, instructor = self._mapped_scope(original_scope)
            base = rec["foldername"]
            final, n = base, 2
            while frappe.db.exists(
                "Course Folder",
                {
                    "course": self.course,
                    "scope": scope,
                    "instructor": instructor or ["is", "not set"],
                    "course_schedule": ["is", "not set"],
                    "foldername": final,
                },
            ):
                final = f"{base} ({n})"
                n += 1
            cf = frappe.get_doc(
                {
                    "doctype": "Course Folder",
                    "course": self.course,
                    "scope": scope,
                    "instructor": instructor,
                    "foldername": final,
                }
            )
            cf.flags.ignore_permissions = True
            cf.insert(ignore_mandatory=True)
            self._rebuild_folder_tree(
                cf.file_reference, rec.get("files") or [], cf.name
            )
            self.folder_map[old_key] = cf.name
            self.folder_labels[cf.name] = final
            note = provenance
            if original_scope != scope:
                note += _("; scope {0} mapped to {1}").format(original_scope, scope)
            if rec.get("origin_instructor_name"):
                note += _("; originally by {0}").format(rec["origin_instructor_name"])
            log_activity(cf.name, "imported", note=note)
            if final != base:
                self.warnings.append(
                    _("Folder '{0}' imported as '{1}' (name already in use).").format(
                        base, final
                    )
                )

    def _rebuild_folder_tree(self, parent_file, nodes, course_folder):
        for node in nodes:
            if node.get("type") == "folder":
                sub = frappe.get_doc(
                    {
                        "doctype": "File",
                        "file_name": node["file_name"],
                        "is_folder": 1,
                        "folder": parent_file,
                        "is_private": 1,
                        "attached_to_doctype": "Course Folder",
                        "attached_to_name": course_folder,
                    }
                )
                sub.flags.ignore_permissions = True
                sub.insert(ignore_mandatory=True)
                self._rebuild_folder_tree(
                    sub.name, node.get("children") or [], course_folder
                )
            else:
                meta = (self.m.get("media") or {}).get(node.get("media"))
                if not meta:
                    continue
                blob = self.zf.read(f"media/{meta['key']}")
                # Always private, whatever the manifest says: folder material is
                # read through the folder's scope rule, never by URL (§2.2b).
                f = frappe.get_doc(
                    {
                        "doctype": "File",
                        "file_name": node["file_name"],
                        "is_folder": 0,
                        "folder": parent_file,
                        "is_private": 1,
                        "content": blob,
                        "attached_to_doctype": "Course Folder",
                        "attached_to_name": course_folder,
                    }
                )
                f.flags.ignore_permissions = True
                f.insert(ignore_mandatory=True)

    # --- questions / activities ------------------------------------------
    def import_questions(self):
        for src, rec in (self.m.get("questions") or {}).items():
            allowed = _importable("questions", rec.get("doctype"))
            d = frappe.new_doc(rec["doctype"])
            d.update(self._rw(_only(rec.get("fields"), allowed)))
            if rec["doctype"] == "Question":
                d.course = self.course
                for it in rec.get("matching_items") or []:
                    d.append(
                        "matching_items", _only(it, SCRIPTURE_MATCHING_ITEM_FIELDS)
                    )
            d.flags.ignore_permissions = True
            d.insert(ignore_mandatory=True)
            self.q_map[src] = d.name

    def import_activities(self):
        for src, rec in (self.m.get("activities") or {}).items():
            dt = rec.get("doctype")
            allowed = _importable("activities", dt)
            d = frappe.new_doc(dt)
            d.update(self._rw(_only(rec.get("fields"), allowed)))
            if self._has_field(dt, "course"):
                d.course = self.course
            if dt == "Quiz":
                for qq in rec.get("questions") or []:
                    d.append(
                        "questions",
                        {
                            **_only(qq.get("fields"), QUIZ_QUESTION_FIELDS),
                            "question": self.q_map.get(qq.get("question")),
                        },
                    )
            elif dt == "Exam Activity":
                for eq in rec.get("questions") or []:
                    d.append(
                        "questions",
                        {
                            **_only(eq.get("fields"), EXAM_QUESTION_FIELDS),
                            "question": self.q_map.get(eq.get("question")),
                        },
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
                    # The pack's fields go FIRST and filtered: spread last and
                    # unfiltered, as they were, a manifest could override
                    # `doctype` and `parent` here -- a second way to instantiate
                    # any doctype, which p005 A01-7 did not list.
                    **_only(rec.get("fields"), SCAC_FIELDS),
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
                    "course_competency": self.competency_map.get(
                        rec.get("competency_code")
                    ),
                }
            )
            row.flags.ignore_permissions = True
            row.insert(ignore_mandatory=True)
            self.scac_map[rec["src_name"]] = row.name
            for w in rec.get("dimension_weights") or []:
                weight = frappe.new_doc("Assessment Dimension Weight")
                weight.update(_only(w, ASSESSMENT_DIMENSION_WEIGHT_FIELDS))
                weight.assess_criteria = row.name
                weight.flags.ignore_permissions = True
                weight.insert(ignore_mandatory=True)

    # --- chapters + lessons ----------------------------------------------
    def import_chapters_and_lessons(self, cs):
        n_chapters = n_lessons = 0
        for cidx, chrec in enumerate(self.m.get("chapters") or [], start=1):
            ch = frappe.new_doc("Course Schedule Chapter")
            ch.coursesc = cs.name
            ch.update(self._rw(_only(chrec.get("fields"), CHAPTER_FIELDS)))
            ch.course_competency = self.competency_map.get(chrec.get("competency_code"))
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
                les.update(
                    self._rewrite_lesson_fields(
                        _only(lrec.get("fields"), LESSON_FIELDS)
                    )
                )
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
            content = editorjs.rewrite_content_refs(out.get(f), self.a_map)
            content = editorjs.rewrite_folder_refs(
                content, self.folder_map, self.folder_labels
            )
            out[f] = editorjs.rewrite_urls(content, self.url_map)
        body_map = {**self.a_map, **self.folder_map}
        for f in ("body", "instructor_notes"):
            out[f] = editorjs.rewrite_urls(
                editorjs.rewrite_body_refs(out.get(f), body_map), self.url_map
            )
        return out

    def _reextract_scorm(self, ch):
        """Kept under its old name for the call site; it no longer extracts.

        This used to unpack the package into public/scorm/<course>/<title>/ with
        the title taken from the PACK'S MANIFEST -- a remote file write for
        anyone who could get a pack imported (p005a A05-8). Packages are stored,
        not unpacked (p008 F8): pin the File to its new chapter and clear the
        three path fields a manifest may have carried."""
        if not (ch.get("is_scorm_package") and ch.get("scorm_package")):
            return
        from seminary.seminary.api import pin_scorm_package

        pin_scorm_package(ch.name, ch.scorm_package)
        frappe.db.set_value(
            "Course Schedule Chapter",
            ch.name,
            {"scorm_package_path": None, "manifest_file": None, "launch_file": None},
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
        self._warn_same_site()
        for w in self.m.get("warnings") or []:
            self.warnings.append(_("Exporter noted: {0}").format(w))
        if self.instructor and not frappe.db.exists("Instructor", self.instructor):
            frappe.throw(_("Instructor {0} does not exist.").format(self.instructor))
        self.grading_scale = self.resolve_grading_scale()
        self.resolve_assessment_criteria()
        self.course = self.resolve_course()
        # Before SCAC: assessments link to a competency, so the competencies
        # have to exist for import_scac to remap onto them.
        self.import_competencies(self.course)
        self.import_media()
        self.import_questions()
        self.import_activities()
        self.import_folders()
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
            "activities": len(self.a_map),
            "questions": len(self.q_map),
            "folders": len(self.folder_map),
            "media": len(self.url_map),
            "warnings": self.warnings,
        }

    def _warn_same_site(self):
        """Same-site reuse through export → import duplicates storage and
        detaches the copy — the opposite of the folder model's purpose. Point
        at Import Course Template instead (§2.2b)."""
        gen = self.m.get("generator") or {}
        if gen.get("site") and gen.get("site") == frappe.local.site:
            src = self.m.get("source") or {}
            self.warnings.append(
                _(
                    "This pack was exported from this site ({0}, from {1}). To build "
                    "a section from an existing one here, use Import Course Template "
                    "on the Course Schedule instead: it reuses the folders rather "
                    "than copying every file."
                ).format(
                    gen.get("site"), src.get("course_schedule") or src.get("course")
                )
            )


def _cap(key, default):
    return int(frappe.conf.get(key) or default)


def _require_import_role():
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(IMPORT_ROLES):
        frappe.throw(
            _(
                "Only Program Chair, Seminary Manager, or Registrar can import course packs."
            ),
            frappe.PermissionError,
        )


def _read_pack_bytes(file_url):
    """The pack's bytes, from a File the caller may read.

    p005a A08-6: this used to resolve ANY File by URL with no permission check,
    and it ran before the role check -- so any logged-in user could have the
    importer read any file on the site in full into worker memory (and, with
    object storage, stream a multi-gigabyte object back to do it). The size is
    checked from the File row before a byte is read."""
    name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not name:
        frappe.throw(_("Uploaded Course Pack file not found."))
    doc = frappe.get_doc("File", name)
    doc.check_permission("read")
    if doc.is_folder or not (doc.file_name or "").lower().endswith(".zip"):
        frappe.throw(_("A Course Pack is a .zip file."))
    limit = _cap("course_pack_max_bytes", MAX_PACK_BYTES)
    if (doc.file_size or 0) > limit:
        frappe.throw(_("This Course Pack is larger than this site accepts."))
    content = doc.get_content(encodings=[])
    if isinstance(content, str):
        content = content.encode("utf-8")
    return content


def _check_zip_bounds(zf, compressed_size):
    """Refuse a decompression bomb BEFORE anything in the archive is read
    (p005 A10-3). Sizes come from the central directory, so this costs nothing."""
    infos = zf.infolist()
    if len(infos) > _cap("course_pack_max_entries", MAX_PACK_ENTRIES):
        frappe.throw(_("This Course Pack has too many files."))
    total = sum(i.file_size for i in infos)
    if total > _cap("course_pack_max_uncompressed_bytes", MAX_PACK_UNCOMPRESSED_BYTES):
        frappe.throw(_("This Course Pack is too large once unpacked."))
    # The total above is a sum, so one enormous member passed it (p008 F17b).
    # Every member is read whole -- `zf.read` into a bytes, then a File document
    # holding the same bytes -- so a single entry is what actually sizes the
    # worker, not the archive.
    member_cap = _cap("course_pack_max_member_bytes", MAX_PACK_MEMBER_BYTES)
    if any(i.file_size > member_cap for i in infos):
        frappe.throw(_("This Course Pack contains a file that is too large."))
    if total > PACK_RATIO_FLOOR_BYTES and compressed_size:
        if total / compressed_size > MAX_PACK_RATIO:
            frappe.throw(_("This Course Pack does not look like a course pack."))
    try:
        manifest = zf.getinfo("manifest.json")
    except KeyError:
        frappe.throw(_("This file is not a Course Pack (no manifest)."))
    if manifest.file_size > _cap(
        "course_pack_max_manifest_bytes", MAX_PACK_MANIFEST_BYTES
    ):
        frappe.throw(_("This Course Pack's manifest is too large."))


def _validate_pack(manifest):
    _require_import_role()
    if not isinstance(manifest, dict):
        frappe.throw(_("This Course Pack's manifest is not valid."))
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
    instructor=None,
):
    """Core import from raw zip bytes — reusable in tests.

    Order matters (p005 A10-3): the role, then the archive's bounds, and only
    then is anything inside it read or parsed. The role is checked here as well
    as in the whitelisted wrapper so the console path is not a way round it."""
    _require_import_role()
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        frappe.throw(_("This file is not a Course Pack (not a zip archive)."))
    with archive as zf:
        _check_zip_bounds(zf, len(content))
        manifest = json.loads(zf.read("manifest.json"))
        _validate_pack(manifest)
        return _Importer(
            manifest,
            zf,
            target_mode,
            course,
            course_name,
            academic_term,
            section,
            instructor=instructor,
        ).run()


@frappe.whitelist()
def import_course_pack(
    file_url,
    target_mode,
    course=None,
    course_name=None,
    academic_term=None,
    section=None,
    instructor=None,
):
    """Import an uploaded Course Pack. `file_url` is a prior /api/method/upload_file
    result. `target_mode` is 'new' or 'existing'. `instructor` is the destination
    Instructor: the pack's Instructor- and Section-scope folders become that
    professor's Instructor folders (Course folders when it is left empty)."""
    _require_import_role()  # before any I/O (p005 A10-3, p005a A08-6)
    content = _read_pack_bytes(file_url)
    return import_pack_from_bytes(
        content,
        target_mode,
        course=course,
        course_name=course_name,
        academic_term=academic_term,
        section=section,
        instructor=instructor,
    )
