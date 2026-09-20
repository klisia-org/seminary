# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Course Folder: a private File folder scoped to a Course, an Instructor, a
Section or the School (p006 F2, ADR §2.2a).

This module is the single authority on who may read or write a folder.
`CourseFolder.has_permission`, `seminary.api.folder_upload` and the Course Pack
exporter all call `user_may_read` / `user_may_write` here rather than keeping a
rule of their own, so the four-scope table in the ADR is written down exactly
once.

Read rule (any grader role reads every folder; Administrator always):

| scope      | may read                                                       |
|------------|----------------------------------------------------------------|
| School     | any Student / Alumni / Cohort Participant / grader role        |
| Course     | active roster of any offering of `course` or of a `shared_with`|
| Instructor | active roster of an offering of `course` taught by `instructor`|
|            | or by anyone in `shared_with_instructors`                      |
| Section    | active roster of `course_schedule`                             |

Write rule: doctype write roles, narrowed by scope — an Instructor folder by
its own instructor, a Section folder by that section's instructors; chairs and
managers write everywhere.

A School folder that has been superseded resolves to the newest folder in its
`supersedes` chain before either rule runs (`resolve_latest`).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

SCOPES = ("Course", "Instructor", "Section", "School")

#: Any of these (or Administrator) reads every folder: a professor may look at
#: a colleague's Section or Instructor folder to copy from it (ADR §5.10).
GRADER_ROLES = {"Instructor", "Program Chair", "Seminary Manager", "System Manager"}

#: Chairs and managers write to any folder regardless of scope.
CHAIR_ROLES = {"Program Chair", "Seminary Manager", "System Manager"}

#: Doctype write roles; narrowed per scope in `user_may_write`.
WRITE_ROLES = {"Instructor", "Program Chair", "Seminary Manager", "System Manager"}

#: School-scope readers: everyone with a seat in the institution.
SCHOOL_READER_ROLES = {"Student", "Alumni", "Cohort Participant"} | GRADER_ROLES

COURSE_FOLDERS_ROOT = "Course Folders"
INSTRUCTOR_SUBFOLDER = "by-instructor"
SCHOOL_SUBFOLDER = "School"


# --- File-folder plumbing ---------------------------------------------------


def _ensure_file_folder(folder_name: str, parent_file: str | None = None) -> str:
    """Ensure a File doc exists for the given folder name under the specified parent."""
    parent = parent_file or "Home"
    existing = frappe.db.get_value(
        "File",
        {
            "file_name": folder_name,
            "folder": parent,
            "is_folder": 1,
        },
        "name",
    )
    if existing:
        return existing

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": folder_name,
            "folder": parent,
            "is_folder": 1,
            "is_private": 1,
        }
    )
    file_doc.insert(ignore_permissions=True)
    return file_doc.name


def _ensure_course_root(course: str | None) -> str:
    root = _ensure_file_folder(COURSE_FOLDERS_ROOT, "Home")
    if course:
        return _ensure_file_folder(course, root)
    return root


def _scope_parent(
    scope: str,
    course: str | None,
    instructor: str | None = None,
    course_schedule: str | None = None,
) -> str:
    """The File folder a Course Folder of this scope lives under (ADR §2.2a).

    Course:     Home/Course Folders/<Course>
    Instructor: Home/Course Folders/<Course>/by-instructor/<Instructor>
    Section:    Home/Course Folders/<Course>/<Course Schedule>
    School:     Home/Course Folders/School
    """
    if scope == "School":
        return _ensure_file_folder(SCHOOL_SUBFOLDER, _ensure_course_root(None))
    if not course:
        frappe.throw(_("A {0} folder needs a Course.").format(_(scope)))
    course_root = _ensure_course_root(course)
    if scope == "Instructor":
        if not instructor:
            frappe.throw(_("An Instructor folder needs an Instructor."))
        return _ensure_file_folder(
            instructor, _ensure_file_folder(INSTRUCTOR_SUBFOLDER, course_root)
        )
    if scope == "Section":
        if not course_schedule:
            frappe.throw(_("A Section folder needs a Course Schedule."))
        return _ensure_file_folder(course_schedule, course_root)
    return course_root


# --- identity helpers -------------------------------------------------------


def _as_doc(folder) -> Document | None:
    """Accept a docname or a Course Folder document; None when it does not exist."""
    if isinstance(folder, Document):
        return folder
    if not folder or not frappe.db.exists("Course Folder", folder):
        return None
    return frappe.get_doc("Course Folder", folder)


def _roles(user: str) -> set[str]:
    return set(frappe.get_roles(user))


def _student_for(user: str) -> str | None:
    """The enabled Student behind a User: by `Student.user`, then by email."""
    return frappe.db.get_value(
        "Student", {"user": user, "enabled": 1}, "name"
    ) or frappe.db.get_value(
        "Student", {"student_email_id": user, "enabled": 1}, "name"
    )


def _instructors_for(user: str) -> list[str]:
    if not user or user == "Guest":
        return []
    return frappe.get_all("Instructor", {"user": user}, pluck="name")


def _on_active_roster(student: str, course_schedules: list[str]) -> bool:
    if not student or not course_schedules:
        return False
    return bool(
        frappe.get_all(
            "Scheduled Course Roster",
            filters={
                "student": student,
                "course_sc": ["in", list(course_schedules)],
                "active": 1,
            },
            limit=1,
        )
    )


def _sections_of_course(courses) -> list[str]:
    courses = [c for c in courses if c]
    if not courses:
        return []
    return frappe.get_all(
        "Course Schedule", filters={"course": ["in", courses]}, pluck="name"
    )


def section_instructors(course_schedule: str) -> list[str]:
    """Instructor names listed on a Course Schedule's `instructor1` table."""
    if not course_schedule:
        return []
    return frappe.get_all(
        "Course Schedule Instructors",
        filters={"parent": course_schedule, "parenttype": "Course Schedule"},
        pluck="instructor",
        order_by="idx asc",
    )


def _sections_taught_by(instructors, course: str | None) -> list[str]:
    instructors = [i for i in instructors if i]
    if not instructors or not course:
        return []
    parents = frappe.get_all(
        "Course Schedule Instructors",
        filters={"parenttype": "Course Schedule", "instructor": ["in", instructors]},
        pluck="parent",
        distinct=True,
    )
    if not parents:
        return []
    return frappe.get_all(
        "Course Schedule",
        filters={"name": ["in", parents], "course": course},
        pluck="name",
    )


# --- public rule functions --------------------------------------------------


def resolve_latest(name: str) -> str:
    """Follow the `supersedes` chain forward and return the newest docname.

    A lesson that embeds an old School folder resolves to the folder that
    replaced it, and so on; cycle-safe, and a name with no successor returns
    itself.
    """
    if not name:
        return name
    seen = {name}
    current = name
    while True:
        successor = frappe.db.get_value(
            "Course Folder",
            {"supersedes": current},
            "name",
            order_by="creation desc",
        )
        if not successor or successor in seen:
            return current
        seen.add(successor)
        current = successor


def user_may_read(folder, user: str | None = None) -> bool:
    """The read rule of ADR §2.2a. `folder` is a docname or a Course Folder doc."""
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False
    if user == "Administrator":
        return True
    doc = _as_doc(folder)
    if doc is None:
        return False

    scope = doc.scope or "Course"
    roles = _roles(user)

    if scope == "School":
        latest = resolve_latest(doc.name)
        if latest != doc.name:
            doc = _as_doc(latest) or doc
        return bool(roles & SCHOOL_READER_ROLES)

    # p007 §2.8: chairs, managers and instructors of record read every folder
    # (to copy from it); a grader or assistant reads the folders of the
    # sections they are listed on; a student reads through the roster.
    from seminary.seminary.guards import instructor_tier, own_course_schedules

    if roles & CHAIR_ROLES or instructor_tier(user) == "record":
        return True

    if scope == "Course":
        courses = {doc.course} | {r.course for r in (doc.get("shared_with") or [])}
        sections = _sections_of_course(courses)
    elif scope == "Instructor":
        instructors = {doc.instructor} | {
            r.instructor for r in (doc.get("shared_with_instructors") or [])
        }
        sections = _sections_taught_by(instructors, doc.course)
    elif scope == "Section":
        sections = [doc.course_schedule] if doc.course_schedule else []
    else:
        return False

    if "Instructor" in roles and set(sections) & set(own_course_schedules(user)):
        return True

    student = _student_for(user)
    if not student:
        return False
    return _on_active_roster(student, sections)


# --- row-level hooks (registered in hooks.py) --------------------------------
#
# p008a G8 / p005a A01-15. The controller's has_permission override below makes
# a per-document read follow `user_may_read`, but a LIST is not a per-document
# read: frappe.client.get_list applied the DocPerm alone, so a student could list
# every Course Folder in the school -- name, scope, owning instructor, File
# reference -- including personal Instructor-scope folders that the same student
# gets 403 on when opening. The register called this "half-wired"; this is the
# other half. The condition mirrors `user_may_read` clause by clause, so the
# list shows exactly the folders a per-document read would allow
# (test_p008a_course_folder_list asserts the two agree).

_READ_LIKE = {"read", "select", "print", "email", "report", "export"}


def has_permission(doc, ptype=None, user=None):
    """Module-level twin of the controller override, for callers that go through
    ``frappe.has_permission(..., doc=)`` instead of ``doc.has_permission`` -- a
    File read that resolves through its host folder, for one. Deny-only: True
    defers to the DocPerm."""
    user = user or frappe.session.user
    ptype = ptype or "read"
    if ptype in _READ_LIKE:
        return user_may_read(doc, user)
    if ptype == "write":
        return user_may_write(doc, user)
    return True


def _in(values) -> str:
    return ", ".join(frappe.db.escape(v) for v in values)


def get_permission_query_conditions(user=None):
    from seminary.seminary.guards import instructor_tier, own_course_schedules

    user = user or frappe.session.user
    if not user or user == "Guest":
        return "1=0"
    if user == "Administrator":
        return ""
    roles = _roles(user)
    if roles & CHAIR_ROLES or instructor_tier(user) == "record":
        return ""

    cf = "`tabCourse Folder`"
    parts = []
    if roles & SCHOOL_READER_ROLES:
        parts.append(f"{cf}.scope = 'School'")

    # The sections this user reaches: listed on them as an instructor, or on
    # their active roster as a student -- the same two legs as user_may_read.
    sections = set()
    if "Instructor" in roles:
        sections |= set(own_course_schedules(user) or [])
    student = _student_for(user)
    if student:
        sections |= set(
            frappe.get_all(
                "Scheduled Course Roster",
                filters={"student": student, "active": 1},
                pluck="course_sc",
            )
        )
    sections = {s for s in sections if s}
    if sections:
        sec = _in(sorted(sections))
        courses = {
            c
            for c in frappe.get_all(
                "Course Schedule",
                filters={"name": ["in", list(sections)]},
                pluck="course",
            )
            if c
        }
        parts.append(f"({cf}.scope = 'Section' and {cf}.course_schedule in ({sec}))")
        if courses:
            crs = _in(sorted(courses))
            parts.append(
                f"({cf}.scope = 'Course' and ({cf}.course in ({crs}) or exists ("
                f"select 1 from `tabCourse Folder Share` sh where sh.parent = {cf}.name "
                f"and sh.parenttype = 'Course Folder' and sh.course in ({crs}))))"
            )
        # Instructor scope: the folder's instructor (or one it is shared with)
        # teaches one of MY sections of the folder's own course.
        parts.append(
            f"({cf}.scope = 'Instructor' and exists ("
            f"select 1 from `tabCourse Schedule Instructors` csi "
            f"join `tabCourse Schedule` cs on cs.name = csi.parent "
            f"where csi.parenttype = 'Course Schedule' and csi.parent in ({sec}) "
            f"and cs.course = {cf}.course "
            f"and (csi.instructor = {cf}.instructor or csi.instructor in ("
            f"select ish.instructor from `tabCourse Folder Instructor Share` ish "
            f"where ish.parent = {cf}.name and ish.parenttype = 'Course Folder'))))"
        )
    if not parts:
        return "1=0"
    return "(" + " or ".join(parts) + ")"


def user_may_write(folder, user: str | None = None) -> bool:
    """The write rule of ADR §2.2a: doctype write roles, narrowed by scope."""
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False
    if user == "Administrator":
        return True
    doc = _as_doc(folder)
    if doc is None:
        return False

    roles = _roles(user)
    if not roles & WRITE_ROLES:
        return False
    if roles & CHAIR_ROLES:
        return True

    # From here on the user is an Instructor without a chair/manager role.
    from seminary.seminary.guards import instructor_tier, own_course_schedules

    scope = doc.scope or "Course"
    if scope == "School":
        return instructor_tier(user) == "record"
    if scope == "Course":
        # p007 §2.8: an instructor writes a Course folder only for a course
        # they teach a section of (any tier).
        return bool(
            set(_sections_of_course([doc.course])) & set(own_course_schedules(user))
        )
    mine = set(_instructors_for(user))
    if not mine:
        return False
    if scope == "Instructor":
        return doc.instructor in mine
    if scope == "Section":
        return bool(mine & set(section_instructors(doc.course_schedule)))
    return False


def log_activity(
    folder_name: str,
    action: str,
    file_name: str | None = None,
    section: str | None = None,
    note: str | None = None,
    user: str | None = None,
) -> str | None:
    """Append one `Course Folder Activity` row by direct child insert.

    No parent save (the folder's own `modified` is untouched, so a log line
    never races an open form) and no commit: the row rides the caller's
    transaction, so a failed upload leaves no "added" line behind.
    """
    if not folder_name or not frappe.db.exists("Course Folder", folder_name):
        return None
    if section and not frappe.db.exists("Course Schedule", section):
        section = None
    idx = (
        frappe.db.count(
            "Course Folder Activity",
            {"parent": folder_name, "parenttype": "Course Folder"},
        )
        + 1
    )
    row = frappe.get_doc(
        {
            "doctype": "Course Folder Activity",
            "parent": folder_name,
            "parenttype": "Course Folder",
            "parentfield": "activity",
            "idx": idx,
            "when": now_datetime(),
            "who": user or frappe.session.user,
            "action": action,
            "file_name": file_name,
            "section": section,
            "note": note,
        }
    )
    row.flags.ignore_permissions = True
    row.insert()
    return row.name


def rescope(
    folder_name: str,
    new_scope: str,
    instructor: str | None = None,
    course_schedule: str | None = None,
    note: str | None = None,
    section: str | None = None,
) -> Document:
    """Change a folder's scope and move its File row under the new disk path.

    The move is a `File.folder` update — the bytes stay where they are and the
    File docname is kept, so every `file_reference` and every link to the
    files inside stays valid. Logs one "re-scoped" activity row.
    """
    if new_scope not in SCOPES:
        frappe.throw(_("Unknown folder scope {0}.").format(new_scope))
    doc = frappe.get_doc("Course Folder", folder_name)
    old_scope = doc.scope or "Course"
    old_owner = doc.instructor or doc.course_schedule

    if new_scope == "Section":
        if not course_schedule:
            frappe.throw(_("A Section folder needs a Course Schedule."))
        doc.course = frappe.db.get_value("Course Schedule", course_schedule, "course")
    if new_scope == "Instructor" and not instructor:
        frappe.throw(_("An Instructor folder needs an Instructor."))

    doc.scope = new_scope
    doc.instructor = instructor if new_scope == "Instructor" else None
    doc.course_schedule = course_schedule if new_scope == "Section" else None
    if new_scope != "School":
        doc.supersedes = None
    doc._validate_scope_fields()
    doc._validate_unique_key()

    new_parent = _scope_parent(
        new_scope, doc.course, doc.instructor, doc.course_schedule
    )
    if doc.file_reference and new_parent != doc.parent_folder:
        frappe.db.set_value(
            "File", doc.file_reference, "folder", new_parent, update_modified=False
        )
    doc.parent_folder = new_parent
    doc.flags.ignore_permissions = True
    doc.save()

    detail = f"from {old_scope}"
    if old_owner:
        detail += f" ({old_owner})"
    detail += f" to {new_scope}"
    if doc.instructor or doc.course_schedule:
        detail += f" ({doc.instructor or doc.course_schedule})"
    log_activity(
        doc.name,
        "re-scoped",
        section=section,
        note=f"{detail}; {note}" if note else detail,
    )
    return doc


def copy_file_tree(source_folder: str, target_folder: str, course_folder: str) -> int:
    """Copy every File under `source_folder` into `target_folder` as new rows.

    Each file is re-stored from its bytes as a new private File attached to the
    new Course Folder. Sharing the stored `file_url` the way Frappe's
    `create_attachment_copy` does would be cheaper, but `File.before_insert`
    then requires the *copying* user to be able to read the source row, which a
    Registrar running a template import cannot; and a folder copy is by
    definition a second, independently owned set of files (ADR §2.2b).
    Returns the number of files (not folders) copied.
    """
    copied = 0
    for entry in frappe.get_all(
        "File",
        filters={"folder": source_folder},
        fields=["name", "file_name", "is_folder"],
        order_by="is_folder desc, file_name asc",
        ignore_permissions=True,
    ):
        if entry.is_folder:
            sub = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": entry.file_name,
                    "folder": target_folder,
                    "is_folder": 1,
                    "is_private": 1,
                    "attached_to_doctype": "Course Folder",
                    "attached_to_name": course_folder,
                }
            )
            sub.insert(ignore_permissions=True)
            copied += copy_file_tree(entry.name, sub.name, course_folder)
            continue
        src = frappe.get_doc("File", entry.name)
        content = src.get_content(encodings=[])
        if isinstance(content, str):
            content = content.encode("utf-8")
        frappe.get_doc(
            {
                "doctype": "File",
                "file_name": src.file_name,
                "folder": target_folder,
                "is_private": 1,
                "content": content,
                "attached_to_doctype": "Course Folder",
                "attached_to_name": course_folder,
            }
        ).insert(ignore_permissions=True)
        copied += 1
    return copied


# --- controller -------------------------------------------------------------


class CourseFolder(Document):
    def validate(self):
        self.scope = self.scope or "Course"
        self._validate_scope_fields()
        self._validate_unique_key()

    def before_insert(self):
        self.scope = self.scope or "Course"
        self._validate_scope_fields()
        parent_file = _scope_parent(
            self.scope, self.course, self.instructor, self.course_schedule
        )
        folder_file = _ensure_file_folder(self.foldername, parent_file)
        self.parent_folder = parent_file
        self.file_reference = folder_file

    def after_insert(self):
        self._sync_file_reference_link()

    def on_update(self):
        self._sync_file_reference_link()

    def has_permission(
        self, permtype: str = "read", user: str | None = None, **kwargs
    ) -> bool:
        # Server-side callers that already authorised the operation (template
        # import, pack import, rescope) set this flag; the base class honours
        # it before any rule, and so must the override.
        if self.flags.ignore_permissions:
            return True
        user = user or frappe.session.user
        if permtype in ("read", "select"):
            return user_may_read(self, user)
        if permtype == "write":
            return user_may_write(self, user)
        return super().has_permission(permtype, user=user, **kwargs)

    # --- validation helpers --------------------------------------------

    def _validate_scope_fields(self) -> None:
        if self.scope not in SCOPES:
            frappe.throw(_("Unknown folder scope {0}.").format(self.scope))
        if self.scope != "Instructor":
            self.instructor = None
        if self.scope != "Section":
            self.course_schedule = None
        if self.scope != "School":
            self.supersedes = None

        if self.scope == "Instructor" and not self.instructor:
            frappe.throw(_("An Instructor folder needs an Instructor."))
        if self.scope == "Section":
            if not self.course_schedule:
                frappe.throw(_("A Section folder needs a Course Schedule."))
            cs_course = frappe.db.get_value(
                "Course Schedule", self.course_schedule, "course"
            )
            if not self.course:
                self.course = cs_course
            elif cs_course and cs_course != self.course:
                frappe.throw(
                    _("Course Schedule {0} belongs to course {1}, not {2}.").format(
                        self.course_schedule, cs_course, self.course
                    )
                )
        if self.scope != "School" and not self.course:
            frappe.throw(_("A {0} folder needs a Course.").format(_(self.scope)))
        if self.supersedes:
            if self.supersedes == self.name:
                frappe.throw(_("A folder cannot supersede itself."))
            older_scope = frappe.db.get_value("Course Folder", self.supersedes, "scope")
            if older_scope and older_scope != "School":
                frappe.throw(_("Only a School folder can be superseded."))

    def _validate_unique_key(self) -> None:
        """One folder per (course, scope, instructor | course_schedule, foldername).

        Two rows with the same key would share one File folder on disk, and
        the folder API resolves a File back to *one* Course Folder.
        """
        filters = {"scope": self.scope, "foldername": self.foldername}
        for field, value in (
            ("course", self.course),
            ("instructor", self.instructor),
            ("course_schedule", self.course_schedule),
        ):
            filters[field] = value if value else ["is", "not set"]
        if self.name:
            filters["name"] = ["!=", self.name]
        clash = frappe.db.get_value("Course Folder", filters, "name")
        if clash:
            frappe.throw(
                _("A {0} folder named '{1}' already exists here ({2}).").format(
                    _(self.scope), self.foldername, clash
                ),
                frappe.DuplicateEntryError,
            )

    def _sync_file_reference_link(self) -> None:
        if not self.file_reference:
            return
        current = frappe.db.get_value(
            "File",
            self.file_reference,
            ["attached_to_doctype", "attached_to_name"],
            as_dict=True,
        )
        if (
            current
            and current.attached_to_doctype == self.doctype
            and current.attached_to_name == self.name
        ):
            return
        frappe.db.set_value(
            "File",
            self.file_reference,
            "attached_to_doctype",
            self.doctype,
            update_modified=False,
        )
        frappe.db.set_value(
            "File",
            self.file_reference,
            "attached_to_name",
            self.name,
            update_modified=False,
        )


# --- whitelisted helpers for the lesson editor ------------------------------


def _course_of(course: str | None, course_schedule: str | None) -> str | None:
    if course:
        return course
    if course_schedule:
        return frappe.db.get_value("Course Schedule", course_schedule, "course")
    return None


@frappe.whitelist()
def folder_context(course: str | None = None, course_schedule: str | None = None):
    """What the folder picker needs to pre-fill its scope selector."""
    user = frappe.session.user
    roles = _roles(user)
    mine = _instructors_for(user)
    return {
        "course": _course_of(course, course_schedule),
        "course_schedule": course_schedule or None,
        "instructor": mine[0] if mine else None,
        "can_school": user == "Administrator" or bool(roles & CHAIR_ROLES),
    }


@frappe.whitelist()
def list_embeddable_folders(
    course: str | None = None, course_schedule: str | None = None
):
    """Folders the session user may embed in a lesson of this section.

    Course folders of the course, the user's own Instructor folders for it and
    those shared with them, Section folders of the section, and every School
    folder that has not been superseded. Graders only.
    """
    user = frappe.session.user
    roles = _roles(user)
    if user != "Administrator" and not roles & GRADER_ROLES:
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    course = _course_of(course, course_schedule)
    fields = [
        "name",
        "foldername",
        "scope",
        "instructor",
        "course_schedule",
        "file_reference",
        "parent_folder",
    ]
    out: dict[str, dict] = {}

    def add(filters):
        for row in frappe.get_all(
            "Course Folder",
            filters=filters,
            fields=fields,
            order_by="foldername asc",
        ):
            out.setdefault(row.name, row)

    if course:
        add({"scope": "Course", "course": course})
        mine = _instructors_for(user)
        if mine:
            add({"scope": "Instructor", "course": course, "instructor": ["in", mine]})
            shared = frappe.get_all(
                "Course Folder Instructor Share",
                filters={"parenttype": "Course Folder", "instructor": ["in", mine]},
                pluck="parent",
                distinct=True,
            )
            if shared:
                add({"scope": "Instructor", "course": course, "name": ["in", shared]})
    if course_schedule:
        add({"scope": "Section", "course_schedule": course_schedule})

    superseded = frappe.get_all(
        "Course Folder",
        filters={"scope": "School", "supersedes": ["is", "set"]},
        pluck="supersedes",
    )
    school_filters = {"scope": "School"}
    if superseded:
        school_filters["name"] = ["not in", superseded]
    add(school_filters)

    return list(out.values())
