"""Row-level permission hooks for student-keyed and section-keyed doctypes
(privatedocs p007 §2.2, §2.8).

One factory, registered in ``hooks.py`` per doctype. A DocPerm row decides
whether a role may touch the doctype at all; these hooks decide *which rows*:

* school roles (Program Chair, Registrar, Seminary Manager, System Manager)
  and Administrator: everything the DocPerm allows;
* an Instructor: read within ``readable_course_schedules`` (school-wide for an
  instructor of record, own sections for a grader or assistant), write only on
  sections they are listed on;
* a Student: rows keyed to their own Student record or User;
* someone who is both: the union;
* **any other role the DocPerm grants**: left to the DocPerm. This factory
  scopes the two roles it knows how to scope -- Instructor and Student -- and
  has no opinion about anyone else (p005a A06-4, below).

Hooks can only restrict what a DocPerm grants, so a role with no row on the
doctype is unaffected by anything here.
"""

import frappe

from seminary.seminary.guards import (
    COURSE_FIELD,
    _memo,
    _roles,
    course_of,
    current_student,
    student_sections,
    instructor_tier,
    is_course_staff,
    is_read_ptype,
    is_school_role,
    own_course_schedules,
    readable_course_schedules,
)

# doctype -> (student rule, instructor rule)
#   student rule: ("field", "student") | ("field", "user") | ("name", "student")
#                 | "student_sections" | "student_sections_of" | None
#   instructor rule: "course" (scoped by the section in COURSE_FIELD)
#                 | "students" (Student rows via the roster) | "any" | None
CONFIG = {
    "Student": (("name", "student"), "students"),
    "Scheduled Course Roster": (("stuemail_rc", "user"), "course"),
    "Course Enrollment Individual": (("student_ce", "student"), "course"),
    "Exam Submission": (("member", "user"), "course"),
    "Assignment Submission": (("member", "user"), "course"),
    "Discussion Submission": (("member", "user"), "course"),
    "Quiz Submission": (("member", "user"), "course"),
    "Course Schedule Progress": (("member", "user"), "course"),
    # Same shape as the progress row it sits beside: a student sees their own
    # attempts, an instructor their sections' (p009 §2.11).
    "SCORM Attempt": (("member", "user"), "course"),
    "Withdrawal Request": (("student", "student"), None),
    "Graduation Request": (("student", "student"), None),
    "Recommendation Letter": (("student", "student"), None),
    "Culminating Project": (("student", "student"), "any"),
    "Chapel Attendance": (("student", "student"), None),
    "Course Schedule": ("student_sections", "course"),
    "Course Schedule Chapter": ("student_sections_of", "course"),
    "Course Lesson": ("student_sections_of", "course"),
    "Student Attendance": (None, "course"),
}


def _esc(values):
    return ", ".join(frappe.db.escape(v) for v in values)


# ------------------------------------------------------- roles outside the factory
#
# p005a A06-4. Both hooks used to end in a flat refusal -- ``return False`` /
# ``"1=0"`` -- for anyone who was not a school role, an Instructor or a Student.
# A has_permission hook is deny-only and runs BEFORE the role permissions, so
# that refusal silently overrode the DocPerm for every other role on every
# registered doctype: Withdrawal Request grants Accounts User and Accounts Manager
# read and write at both permlevels, and the hook denied both (p007 §7.1 recorded
# the Accounts exemption in the controller and never mirrored it here). Granting
# a role from the Role Permission Manager appeared to work and did nothing.
#
# The scoped set is what this module is *for*; everything else is the DocPerm's
# business. It is read through get_valid_perms, which honours Custom DocPerm, so
# a grant made on a site is respected without a code change -- the two cannot
# drift. Automatic roles are excluded on purpose: an "All" row is not a
# deliberate grant to a distinct role, and must never switch row scoping off for
# every student at once.

SCOPED_ROLES = {"Instructor", "Student"}
_AUTOMATIC_ROLES = {"Guest", "All", "Desk User", "Administrator"}


def _granted_by_another_role(doctype, ptype, user):
    """True when a role outside the factory's scope grants ``ptype`` on the
    doctype to this user at permlevel 0 (if_owner rows are not a blanket grant
    and are left to the DocPerm evaluation that follows)."""
    ptype = ptype or "read"

    def _compute():
        from frappe.permissions import get_valid_perms

        for perm in get_valid_perms(doctype, user):
            if perm.role in SCOPED_ROLES or perm.role in _AUTOMATIC_ROLES:
                continue
            if perm.get("permlevel") or perm.get("if_owner"):
                continue
            if perm.get(ptype):
                return True
        return False

    return _memo(("other_role", doctype, ptype, user), _compute)


# ------------------------------------------------------------------ has_permission


def _instructor_allows(doctype, doc, ptype, user, rule):
    if rule == "any":
        return True
    tier = instructor_tier(user)
    if not tier:
        return False
    if rule == "students":
        student = doc.name
        if is_read_ptype(ptype):
            readable = readable_course_schedules(user)
            if readable is None:
                return True
            sections = readable
        else:
            sections = own_course_schedules(user)
        if not sections:
            return False
        return bool(
            frappe.db.exists(
                "Scheduled Course Roster",
                {"student": student, "course_sc": ["in", sections]},
            )
        )
    cs = course_of(doc)
    if is_read_ptype(ptype):
        if cs is None:
            return tier == "record"
        readable = readable_course_schedules(user)
        return readable is None or cs in readable
    if cs is None:
        # A new section, or a row that has not been tied to one yet: only an
        # instructor of record may create it.
        return tier == "record"
    return is_course_staff(cs, user=user)


def _student_allows(doctype, doc, ptype, user, rule):
    if rule is None:
        return False
    if rule == "student_sections":
        return doc.name in student_sections(user)
    if rule == "student_sections_of":
        cs = course_of(doc)
        return bool(cs) and cs in student_sections(user)
    field, kind = rule
    if kind == "user":
        return (doc.get(field) or "") == user
    student = current_student(user)
    if not student:
        return False
    value = doc.name if field == "name" else doc.get(field)
    return value == student


def has_for(doctype):
    student_rule, instructor_rule = CONFIG[doctype]

    def has_permission(doc, ptype=None, user=None):
        user = user or frappe.session.user
        if is_school_role(user):
            return True
        if _granted_by_another_role(doctype, ptype, user):
            return True
        roles = _roles(user)
        if "Instructor" in roles and instructor_rule:
            if _instructor_allows(doctype, doc, ptype, user, instructor_rule):
                return True
            # A grader who is also a student still reads their own rows.
        if student_rule is None or "Student" not in roles:
            # The student branch is for students: an instructor reaches a
            # section through their tier, not through the catalogue read.
            return False
        if student_rule in ("student_sections", "student_sections_of") and not (
            is_read_ptype(ptype)
        ):
            return False
        return _student_allows(doctype, doc, ptype, user, student_rule)

    has_permission.__name__ = f"has_permission_{frappe.scrub(doctype)}"
    return has_permission


# ------------------------------------------------------ permission_query_conditions


def _instructor_condition(doctype, user, rule):
    """SQL for the instructor read branch, "" for unrestricted, None for
    nothing readable."""
    if rule == "any":
        return ""
    if not instructor_tier(user):
        return None
    readable = readable_course_schedules(user)
    if readable is None:
        return ""
    if not readable:
        return None
    if rule == "students":
        return (
            f"`tabStudent`.name in (select student from `tabScheduled Course Roster` "
            f"where course_sc in ({_esc(readable)}))"  # nosec B608 -- the value is escaped before it reaches the string
        )
    field = COURSE_FIELD[doctype]
    return f"`tab{doctype}`.`{field}` in ({_esc(readable)})"


def _student_condition(doctype, user, rule):
    if rule is None:
        return None
    if rule == "student_sections":
        enrolled = student_sections(user)
        if not enrolled:
            return None
        return f"`tab{doctype}`.name in ({_esc(enrolled)})"
    if rule == "student_sections_of":
        enrolled = student_sections(user)
        if not enrolled:
            return None
        field = COURSE_FIELD[doctype]
        return f"`tab{doctype}`.`{field}` in ({_esc(enrolled)})"
    field, kind = rule
    if kind == "user":
        return f"`tab{doctype}`.`{field}` = {frappe.db.escape(user)}"
    student = current_student(user)
    if not student:
        return None
    return f"`tab{doctype}`.`{field}` = {frappe.db.escape(student)}"


def query_for(doctype):
    student_rule, instructor_rule = CONFIG[doctype]

    def get_permission_query_conditions(user=None):
        user = user or frappe.session.user
        if is_school_role(user):
            return ""
        if _granted_by_another_role(doctype, "read", user):
            return ""
        parts = []
        roles = _roles(user)
        if "Instructor" in roles and instructor_rule:
            cond = _instructor_condition(doctype, user, instructor_rule)
            if cond == "":
                return ""
            if cond:
                parts.append(cond)
        if "Student" in roles:
            cond = _student_condition(doctype, user, student_rule)
            if cond:
                parts.append(cond)
        if not parts:
            return "1=0"
        return "(" + " or ".join(parts) + ")"

    get_permission_query_conditions.__name__ = (
        f"get_permission_query_conditions_{frappe.scrub(doctype)}"
    )
    return get_permission_query_conditions


# Module-level names for hooks.py (dotted paths must resolve to attributes).
for _dt in CONFIG:
    _key = frappe.scrub(_dt)
    globals()[f"has_permission_{_key}"] = has_for(_dt)
    globals()[f"query_{_key}"] = query_for(_dt)
