"""Role gates shared by seminary's whitelisted endpoints (privatedocs p006 §2.0).

Three gates wrap the role sets that already exist in ``api.py`` so doctype
controllers can import them without importing ``api.py``. Each raises
``frappe.PermissionError``. ``Administrator`` passes every gate through its
roles; no new roles are introduced.
"""

import frappe
from frappe import _

# Who may grade, record attendance, and read gradebooks (api._GRADER_ROLES).
GRADER_ROLES = {"Instructor", "Program Chair", "Seminary Manager", "System Manager"}
# Who may add/delete chapters and lessons (api.OUTLINE_EDIT_ROLES).
OUTLINE_EDIT_ROLES = {
    "Instructor",
    "Program Chair",
    "Seminary Manager",
    "System Manager",
}
# Who may act on enrollment, standing and separation (api.GRADE_SEND_ROLES minus Instructor).
REGISTRAR_ROLES = {"Program Chair", "Registrar", "Seminary Manager", "System Manager"}


def _roles(user=None):
    return set(frappe.get_roles(user or frappe.session.user))


def _deny(message, gate, **context):
    """Log the denial, then throw it (p010 H1).

    Every gate in this module is a *deliberate* refusal -- the app decided this
    actor may not do this -- which makes these the denials most worth counting.
    Frappe's own `PermissionError` path is caught separately by
    `security_log.log_denied_response`; the request-local flag in that module
    keeps a denial that passes through both from being counted twice.
    """
    from seminary.seminary import security_log

    security_log.record_denial("permission", gate=gate, **context)
    frappe.throw(message, frappe.PermissionError)


def registrar_has_academic_records() -> bool:
    """Seminary Settings switch: may the Registrar record attendance and open
    gradebooks? On by default; a school where a student acts as registrar turns
    it off (p006 §2.4)."""
    value = frappe.db.get_single_value(
        "Seminary Settings", "registrar_academic_records"
    )
    # A Single that was never saved after the field was added reads None: the
    # field's default (on) applies until an administrator turns it off.
    return True if value is None else bool(value)


def is_grader(user=None, include_registrar=False) -> bool:
    roles = _roles(user)
    if roles & GRADER_ROLES:
        return True
    if include_registrar and "Registrar" in roles and registrar_has_academic_records():
        return True
    return False


def require_grader(include_registrar=False):
    if not is_grader(include_registrar=include_registrar):
        _deny(_("Only teaching staff can do this."), "require_grader")


def require_outline_editor():
    if not _roles() & OUTLINE_EDIT_ROLES:
        _deny(
            _("Only teaching staff can edit the course outline."),
            "require_outline_editor",
        )


def require_registrar():
    if not _roles() & REGISTRAR_ROLES:
        _deny(
            _("Only the registrar or academic administration can do this."),
            "require_registrar",
        )


# ---------------------------------------------------------------------------
# p007 Phase 1: which record, not just which role (privatedocs p007 §2.0, §2.8)
# ---------------------------------------------------------------------------

# Roles that bypass row scoping outright. Instructor is deliberately absent:
# an Instructor's reach is a tier (see instructor_tier).
SCHOOL_ROLES = {"Program Chair", "Registrar", "Seminary Manager", "System Manager"}

_READ_PTYPES = {"read", "select", "report", "export", "print", "email", "share"}


def _cache():
    """Per-request memo so the hooks do not re-query the tier on every row."""
    if not hasattr(frappe.local, "p007_cache"):
        frappe.local.p007_cache = {}
    return frappe.local.p007_cache


def _memo(key, fn):
    cache = _cache()
    if key not in cache:
        cache[key] = fn()
    return cache[key]


def _user(user=None):
    return user or frappe.session.user


def is_school_role(user=None) -> bool:
    u = _user(user)
    return u == "Administrator" or bool(_roles(u) & SCHOOL_ROLES)


def current_student(user=None):
    """The user's Student docname, or None. `Student.user` first, then the
    legacy `student_email_id` match."""
    u = _user(user)
    if not u or u in ("Guest", "Administrator"):
        return None

    def _lookup():
        return frappe.db.get_value(
            "Student", {"user": u}, "name"
        ) or frappe.db.get_value("Student", {"student_email_id": u}, "name")

    return _memo(("student", u), _lookup)


def current_instructor(user=None):
    u = _user(user)
    if not u or u in ("Guest", "Administrator"):
        return None
    return _memo(
        ("instructor", u),
        lambda: frappe.db.get_value("Instructor", {"user": u}, "name"),
    )


def own_course_schedules(user=None) -> list:
    """Sections where the user is listed on `Course Schedule.instructor1`."""
    u = _user(user)

    def _lookup():
        from seminary.seminary.utils import get_own_course_schedules

        return list(get_own_course_schedules(u) or [])

    return _memo(("own_cs", u), _lookup)


def _of_record_categories() -> set:
    return _memo(
        ("record_cats",),
        lambda: set(
            frappe.get_all(
                "Instructor Category",
                filters={"is_instructor_of_record": 1},
                pluck="name",
            )
        ),
    )


def instructor_tier(user=None):
    """``"record"``: an Instructor whose default category, or a category on any
    of their non-cancelled section rows, is flagged instructor of record.
    ``"section"``: any other Instructor (grader, GTA, mentor). ``None``: not an
    Instructor. An empty default category is not a grader: it means "no
    restriction recorded", and the tier then comes from the section rows only
    (p007 §2.8, decision 8)."""
    u = _user(user)
    if not u or u == "Guest":
        return None
    if "Instructor" not in _roles(u):
        return None

    def _tier():
        inst = current_instructor(u)
        if not inst:
            return "section"
        cats = _of_record_categories()
        if not cats:
            return "section"
        default = frappe.db.get_value("Instructor", inst, "default_inst_category")
        if default and default in cats:
            return "record"
        rows = frappe.get_all(
            "Course Schedule Instructors",
            filters={
                "instructor": inst,
                "parenttype": "Course Schedule",
                "instructor_category": ["in", list(cats)],
            },
            pluck="parent",
        )
        if rows and frappe.db.exists(
            "Course Schedule",
            {"name": ["in", rows], "workflow_state": ["!=", "Cancelled"]},
        ):
            return "record"
        return "section"

    return _memo(("tier", u), _tier)


def faculty_read_scope() -> str:
    value = frappe.db.get_single_value("Seminary Settings", "faculty_read_scope")
    return value or "School"


def _unit_closure(units) -> set:
    """A unit, its ancestors, and every interdepartment it constitutes."""
    out = set()
    todo = list(units)
    while todo:
        unit = todo.pop()
        if not unit or unit in out:
            continue
        out.add(unit)
        parent = frappe.db.get_value("Academic Unit", unit, "parent_unit")
        if parent:
            todo.append(parent)
        for inter in frappe.get_all(
            "Academic Unit Constituent",
            filters={"member_unit": unit, "parenttype": "Academic Unit"},
            pluck="parent",
        ):
            todo.append(inter)
    return out


def unit_scope_option(fieldname: str) -> str:
    """One of the two Academic-Unit fallback switches (ADR 059 §2.1).

    Both default to ``"School"`` — the behaviour that existed before the
    switches did — so an existing site sees no change until someone tightens
    one deliberately."""
    return frappe.db.get_single_value("Seminary Settings", fieldname) or "School"


def _unit_sections(user) -> list | None:
    """Sections a record-tier instructor may read under the Academic Unit scope:
    courses owned by a unit in their closure, plus — unless the school says
    otherwise — courses with no unit at all. ``None`` means no restriction.

    Two fallbacks reach School, and each is now a setting rather than a fixed
    rule (ADR 059 §2.1), because leaving both open means the scope can restrict
    nothing while appearing to be on (p005a A01-20):

    - no active membership → ``unit_scope_no_membership``
    - a Course with no ``academic_unit`` → ``unit_scope_unassigned_course``
    """
    inst = current_instructor(user)
    person = frappe.db.get_value("Instructor", inst, "person") if inst else None
    units = (
        frappe.get_all(
            "Academic Unit Membership",
            filters={"person": person, "is_active": 1},
            pluck="unit",
        )
        if person
        else []
    )
    if not units:
        # p007 §2.8 read as School unconditionally; that is still the default.
        if unit_scope_option("unit_scope_no_membership") == "School":
            return None
        return sorted(set(own_course_schedules(user)))
    closure = _unit_closure(units)
    or_filters = [["academic_unit", "in", list(closure)]]
    if unit_scope_option("unit_scope_unassigned_course") == "School":
        or_filters.append(["academic_unit", "is", "not set"])
    courses = frappe.get_all("Course", or_filters=or_filters, pluck="name")
    # Under "Exclude" the closure can match nothing; an empty ``in`` list is
    # not a filter worth sending, and the union below is still correct.
    sections = (
        frappe.get_all(
            "Course Schedule", filters={"course": ["in", courses]}, pluck="name"
        )
        if courses
        else []
    )
    return sorted(set(sections) | set(own_course_schedules(user)))


def readable_course_schedules(user=None):
    """Which sections this user may read. ``None`` means every section
    (school roles, and record-tier instructors under the School scope)."""
    u = _user(user)
    if is_school_role(u):
        return None
    tier = instructor_tier(u)

    def _lookup():
        if tier == "record":
            if faculty_read_scope() == "Academic Unit":
                return _unit_sections(u)
            return None
        if tier == "section":
            return sorted(set(own_course_schedules(u)))
        return []

    return _memo(("readable", u), _lookup)


def enrolled_sections(user=None) -> list:
    """Sections where the user's Student record has a roster row."""
    u = _user(user)

    def _lookup():
        student = current_student(u)
        if not student:
            return []
        return sorted(
            set(
                frappe.get_all(
                    "Scheduled Course Roster",
                    filters={"student": student},
                    pluck="course_sc",
                )
            )
        )

    return _memo(("enrolled", u), _lookup)


def student_sections(user=None) -> list:
    """Sections a student may open: on the roster **and** published (p007
    §8.1). Students are enrolled weeks before a term and the instructor keeps
    editing until the day they publish, so a roster row alone opens nothing."""
    u = _user(user)

    def _lookup():
        enrolled = enrolled_sections(u)
        if not enrolled:
            return []
        return sorted(
            frappe.get_all(
                "Course Schedule",
                filters={"name": ["in", enrolled], "published": 1},
                pluck="name",
            )
        )

    return _memo(("student_sections", u), _lookup)


def may_read_course_schedule(course_schedule, user=None) -> bool:
    """Instructor-side read reach (school roles, record tier, or a section the
    user is listed on), or the user's own enrolment."""
    readable = readable_course_schedules(user)
    if readable is None or course_schedule in readable:
        return True
    return course_schedule in student_sections(user)


def is_course_staff(course_schedule, include_registrar=False, user=None) -> bool:
    """May this user act on this section: a school role (Registrar only when
    the caller says so and the p006 §2.4 switch is on), or an Instructor
    listed on the section, whatever their tier."""
    u = _user(user)
    if u == "Administrator":
        return True
    roles = _roles(u)
    if roles & {"Program Chair", "Seminary Manager", "System Manager"}:
        return True
    if include_registrar and "Registrar" in roles and registrar_has_academic_records():
        return True
    if "Instructor" in roles and course_schedule:
        return course_schedule in own_course_schedules(u)
    return False


def require_course_staff(course_schedule, include_registrar=False):
    """School roles pass even when the section could not be resolved (a
    missing record fails later on its own terms); an Instructor needs a
    section they are listed on."""
    if not is_course_staff(course_schedule, include_registrar=include_registrar):
        _deny(
            _("You are not on the teaching staff of this section."),
            "require_course_staff",
            course_schedule=course_schedule,
        )


def is_enrolled(course_schedule, user=None) -> bool:
    """Course staff, a reader of the section, or a student on the active
    roster of a published section."""
    u = _user(user)
    if not course_schedule:
        return False
    if is_course_staff(course_schedule, include_registrar=True, user=u):
        return True
    if instructor_tier(u) == "record" and may_read_course_schedule(course_schedule, u):
        return True
    # A student: on the active roster of a published section (p007 §8.1).
    return bool(
        is_published(course_schedule)
        and frappe.db.exists(
            "Scheduled Course Roster",
            {"course_sc": course_schedule, "stuemail_rc": u, "active": 1},
        )
    )


def require_enrolled(course_schedule):
    if not is_enrolled(course_schedule):
        _deny(
            _("You are not enrolled in this section."),
            "require_enrolled",
            course_schedule=course_schedule,
        )


def is_published(course_schedule) -> bool:
    return bool(
        course_schedule
        and frappe.db.get_value("Course Schedule", course_schedule, "published")
    )


def require_own_student(student):
    """The target is the caller's own Student record, or the caller is staff."""
    if is_school_role() or instructor_tier() == "record":
        return
    if not student or student != current_student():
        _deny(
            _("You can only view your own record."),
            "require_own_student",
            target=student,
        )


def require_own_enrollment(program_enrollment):
    if is_school_role() or instructor_tier() == "record":
        return
    owner = frappe.db.get_value("Program Enrollment", program_enrollment, "student")
    student = current_student()
    if not (owner and student and owner == student):
        _deny(
            _("You can only view your own enrollment."),
            "require_own_enrollment",
            target=program_enrollment,
        )


def own_or_staff(value, kind="student"):
    """Rewrite a caller-supplied target to the session's own record unless the
    caller is staff. ``kind``: "student" (Student docname) or "user" (email)."""
    if is_school_role() or instructor_tier() == "record":
        return value
    if kind == "user":
        return frappe.session.user
    return current_student()


# Which field names the section for a document of each doctype.
COURSE_FIELD = {
    "Course Schedule": "name",
    "Course Schedule Chapter": "coursesc",
    "Course Lesson": "course_sc",
    "Scheduled Course Roster": "course_sc",
    "Student Attendance": "course_schedule",
    "Assignment Submission": "course",
    "Exam Submission": "course",
    "Discussion Submission": "coursesc",
    "Quiz Submission": "course",
    "Course Schedule Progress": "course",
    "Course Enrollment Individual": "coursesc_ce",
    "Course Folder": "course_schedule",
}


def course_of(doc):
    """The Course Schedule a document belongs to, or None."""
    if doc is None:
        return None
    doctype = doc.doctype if hasattr(doc, "doctype") else doc.get("doctype")
    field = COURSE_FIELD.get(doctype)
    if not field:
        return None
    return doc.get(field) if hasattr(doc, "get") else getattr(doc, field, None)


def is_read_ptype(ptype) -> bool:
    return (ptype or "read") in _READ_PTYPES
