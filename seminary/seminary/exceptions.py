# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Course substitutions and waivers with approval (decisions/098).

A Requirement Exception is one request against one Program Enrollment. Its
status moves only through the actions here; an Approved one changes what the
audit and the graduation check count as satisfied, through `satisfied_courses`.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

SUBSTITUTION = "Substitution"
COURSE_WAIVER = "Course Waiver"
REQUIREMENT_WAIVER = "Requirement Waiver"

REQUESTED = "Requested"
APPROVED = "Approved"
DENIED = "Denied"
WITHDRAWN = "Withdrawn"
REVOKED = "Revoked"
OPEN_STATUSES = (REQUESTED, APPROVED)

# Decide for any program. A Program Chair decides only where they are the
# program's director (098 §3).
DECIDER_ROLES = {"Registrar", "Seminary Manager", "System Manager"}
PROGRAM_CHAIR = "Program Chair"


# --------------------------------------------------------------------------- #
# Who may do what
# --------------------------------------------------------------------------- #
def decides_everywhere(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or bool(set(frappe.get_roles(user)) & DECIDER_ROLES)


def directed_programs(user=None):
    user = user or frappe.session.user
    return frappe.get_all("Program", filters={"program_director": user}, pluck="name")


def can_decide(program, user=None):
    user = user or frappe.session.user
    if decides_everywhere(user):
        return True
    if PROGRAM_CHAIR not in frappe.get_roles(user):
        return False
    return bool(program) and program in directed_programs(user)


def require_decider(program):
    if not can_decide(program):
        frappe.throw(
            _(
                "Only the registrar, a Seminary Manager or this program's chair can decide this."
            ),
            frappe.PermissionError,
        )


def is_active_mentor(program_enrollment, user=None):
    from seminary.seminary.guards import current_instructor

    instructor = current_instructor(user)
    if not instructor:
        return False
    return bool(
        frappe.db.exists(
            "Program Enrollment Mentor",
            {
                "parent": program_enrollment,
                "parenttype": "Program Enrollment",
                "instructor": instructor,
                "active": 1,
            },
        )
    )


def _require_requester(program_enrollment):
    from seminary.seminary.guards import current_student

    program, student = frappe.db.get_value(
        "Program Enrollment", program_enrollment, ["program", "student"]
    ) or (None, None)
    if can_decide(program):
        return
    if student and student == current_student():
        return
    if is_active_mentor(program_enrollment):
        return
    frappe.throw(
        _("Only the student, their mentor or the registrar can request this."),
        frappe.PermissionError,
    )


# --------------------------------------------------------------------------- #
# What counts as satisfied
# --------------------------------------------------------------------------- #
def mandatory_courses(pe):
    """Required program courses plus mandatory courses of the student's
    active emphases -- the courses an exception can stand in for."""
    from seminary.seminary.graduation_candidate import (
        _mandatory_emphasis_courses,
        _mandatory_program_courses,
    )

    program = frappe.get_cached_doc("Program", pe.program)
    return _mandatory_program_courses(program) | _mandatory_emphasis_courses(
        pe, program
    )


def passed_courses(pe_name):
    return set(
        frappe.get_all(
            "Program Enrollment Course",
            filters={"parent": pe_name, "status": "Pass"},
            pluck="course_name",
        )
    )


def course_exceptions(pe_name, statuses=OPEN_STATUSES):
    """{required_course: exception row} for the enrollment's open course
    exceptions (Substitution and Course Waiver)."""
    rows = frappe.get_all(
        "Requirement Exception",
        filters={
            "program_enrollment": pe_name,
            "kind": ("in", (SUBSTITUTION, COURSE_WAIVER)),
            "status": ("in", statuses),
        },
        fields=[
            "name",
            "kind",
            "status",
            "required_course",
            "substitute_course",
            "reason",
            "decision_note",
        ],
        order_by="creation asc",
    )
    return {r.required_course: r for r in rows if r.required_course}


def satisfied_courses(pe_name, counted=None):
    """Every course that counts as done for the enrollment: `counted` (the
    passed courses unless the caller passes its own set, e.g. passed plus in
    progress), 058 exemptions, approved course waivers, and approved
    substitutions whose substitute is in `counted` (098 §5)."""
    from seminary.seminary.leveling import leveling_sets

    if counted is None:
        counted = passed_courses(pe_name)
    exempted, _required, _leveling = leveling_sets(pe_name)
    out = set(counted) | exempted
    for course, ex in course_exceptions(pe_name, (APPROVED,)).items():
        if ex.kind == COURSE_WAIVER or ex.substitute_course in counted:
            out.add(course)
    return out


# --------------------------------------------------------------------------- #
# Validation (called from the doctype controller)
# --------------------------------------------------------------------------- #
def validate(doc):
    pe = frappe.get_doc("Program Enrollment", doc.program_enrollment)
    if pe.docstatus != 1:
        frappe.throw(
            _("Exceptions can only be recorded on a submitted Program Enrollment.")
        )
    if not (doc.reason or "").strip():
        frappe.throw(_("A reason is required."))

    if doc.kind == REQUIREMENT_WAIVER:
        doc.required_course = None
        doc.substitute_course = None
        row = next(
            (
                r
                for r in pe.graduation_requirements or []
                if r.name == doc.student_graduation_requirement
            ),
            None,
        )
        if not row:
            if doc.is_new():
                frappe.throw(_("Choose a graduation requirement of this enrollment."))
        else:
            doc.requirement_name = row.requirement_name
        key = {"student_graduation_requirement": doc.student_graduation_requirement}
    else:
        doc.student_graduation_requirement = None
        doc.requirement_name = None
        if not doc.required_course:
            frappe.throw(_("Choose the required course."))
        if doc.kind == COURSE_WAIVER:
            doc.substitute_course = None
        elif not doc.substitute_course:
            frappe.throw(_("Choose the substitute course."))
        if doc.is_new():
            _validate_courses(doc, pe)
        key = {"required_course": doc.required_course}

    if doc.status in OPEN_STATUSES and _open_exists(doc, key):
        frappe.throw(_("This requirement already has an open exception."))


def _validate_courses(doc, pe):
    mandatory = mandatory_courses(pe)
    if doc.required_course not in mandatory:
        frappe.throw(
            _(
                "{0} is not a required course of this program or the student's emphases."
            ).format(doc.required_course)
        )
    if doc.kind != SUBSTITUTION:
        return
    if doc.substitute_course == doc.required_course:
        frappe.throw(_("A course cannot substitute for itself."))
    if doc.substitute_course in mandatory:
        frappe.throw(
            _(
                "{0} is itself a required course and cannot stand in for another."
            ).format(doc.substitute_course)
        )
    if _open_exists(
        doc, {"kind": SUBSTITUTION, "substitute_course": doc.substitute_course}
    ):
        frappe.throw(
            _("{0} already stands in for another requirement.").format(
                doc.substitute_course
            )
        )


def _open_exists(doc, filters):
    filters = dict(filters)
    filters.update(
        {
            "program_enrollment": doc.program_enrollment,
            "status": ("in", OPEN_STATUSES),
            "name": ("!=", doc.name or ""),
        }
    )
    return frappe.db.exists("Requirement Exception", filters)


def before_insert(doc):
    """Whoever may decide records an approved exception in one step; anyone
    else only reaches here through `request` (098 §3)."""
    user = frappe.session.user
    doc.requested_by = user
    doc.program = doc.program or _program_of(doc.program_enrollment)
    if can_decide(doc.program, user):
        doc.status = APPROVED
        doc.decided_by = user
        doc.decided_on = now_datetime()
    elif frappe.flags.requirement_exception_request:
        doc.status = REQUESTED
    else:
        require_decider(None)


def after_insert(doc):
    if doc.status == APPROVED:
        _apply(doc)
        _notify_decision(doc)
    else:
        _notify_request(doc)


def _program_of(program_enrollment):
    return frappe.db.get_value("Program Enrollment", program_enrollment, "program")


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def request(
    program_enrollment,
    kind,
    reason,
    required_course=None,
    substitute_course=None,
    student_graduation_requirement=None,
    supporting_document=None,
):
    _require_requester(program_enrollment)
    if kind == REQUIREMENT_WAIVER and not can_decide(_program_of(program_enrollment)):
        # The portal offers course exceptions only; a requirement waiver is a
        # registrar action on the enrollment.
        kind = None
    if kind not in (SUBSTITUTION, COURSE_WAIVER, REQUIREMENT_WAIVER):
        frappe.throw(_("Choose a substitution or a waiver."))
    doc = frappe.get_doc(
        {
            "doctype": "Requirement Exception",
            "program_enrollment": program_enrollment,
            "kind": kind,
            "reason": reason,
            "required_course": required_course,
            "substitute_course": substitute_course,
            "student_graduation_requirement": student_graduation_requirement,
            "supporting_document": supporting_document,
        }
    )
    frappe.flags.requirement_exception_request = True
    try:
        doc.insert(ignore_permissions=True)
    finally:
        frappe.flags.requirement_exception_request = False
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def decide(name, approve, note=None):
    doc = frappe.get_doc("Requirement Exception", name)
    require_decider(doc.program)
    if doc.status != REQUESTED:
        frappe.throw(_("Only a requested exception can be decided."))
    approve = frappe.utils.cint(approve)
    doc.status = APPROVED if approve else DENIED
    doc.decided_by = frappe.session.user
    doc.decided_on = now_datetime()
    doc.decision_note = note
    doc.save(ignore_permissions=True)
    if approve:
        _apply(doc)
    _notify_decision(doc)
    return {"status": doc.status}


@frappe.whitelist()
def withdraw(name):
    doc = frappe.get_doc("Requirement Exception", name)
    if doc.requested_by != frappe.session.user and not can_decide(doc.program):
        frappe.throw(_("Only the requester can withdraw this."), frappe.PermissionError)
    if doc.status != REQUESTED:
        frappe.throw(_("Only a requested exception can be withdrawn."))
    doc.status = WITHDRAWN
    doc.save(ignore_permissions=True)
    return {"status": doc.status}


@frappe.whitelist()
def revoke(name, note):
    doc = frappe.get_doc("Requirement Exception", name)
    require_decider(doc.program)
    if doc.status != APPROVED:
        frappe.throw(_("Only an approved exception can be revoked."))
    if not (note or "").strip():
        frappe.throw(_("Say why the exception is revoked."))
    doc.status = REVOKED
    doc.decision_note = note
    doc.decided_by = frappe.session.user
    doc.decided_on = now_datetime()
    doc.save(ignore_permissions=True)
    _unapply(doc)
    _notify_decision(doc)
    return {"status": doc.status}


@frappe.whitelist()
def substitute_options(program_enrollment, txt=None):
    """Courses a student may propose as a substitute: enabled courses that are
    not themselves required of them."""
    _require_requester(program_enrollment)
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    excluded = mandatory_courses(pe)
    filters = {"disabled": 0}
    or_filters = None
    if txt:
        like = f"%{txt}%"
        or_filters = {"name": ("like", like), "course_name": ("like", like)}
    rows = frappe.get_all(
        "Course",
        filters=filters,
        or_filters=or_filters,
        fields=["name", "course_name"],
        order_by="course_name asc",
        limit=50 + len(excluded),
    )
    return [r for r in rows if r.name not in excluded][:50]


# --------------------------------------------------------------------------- #
# Effects
# --------------------------------------------------------------------------- #
def _apply(doc):
    """A course exception has no side effect: `satisfied_courses` reads it.
    A requirement waiver is today's SGR waiver, linked back (098 §4)."""
    if doc.kind != REQUIREMENT_WAIVER:
        return
    pe = frappe.get_doc("Program Enrollment", doc.program_enrollment)
    row = _sgr(pe, doc.student_graduation_requirement)
    row.waived = 1
    row.waiver_reason = doc.reason
    row.waived_by = doc.decided_by
    row.waived_on = doc.decided_on
    row.requirement_exception = doc.name
    row.status = "Waived"
    pe.save(ignore_permissions=True)


def _unapply(doc):
    if doc.kind != REQUIREMENT_WAIVER:
        return
    pe = frappe.get_doc("Program Enrollment", doc.program_enrollment)
    row = next(
        (
            r
            for r in pe.graduation_requirements or []
            if r.name == doc.student_graduation_requirement
        ),
        None,
    )
    if not row or row.requirement_exception != doc.name:
        return
    row.waived = 0
    row.waiver_reason = None
    row.waived_by = None
    row.waived_on = None
    row.requirement_exception = None
    row.status = _status_without_waiver(row)
    pe.save(ignore_permissions=True)


def _status_without_waiver(row):
    """What the row was before it was waived, as far as the row can tell."""
    if row.verified_on or row.fulfilled_on:
        return "Fulfilled"
    if row.linked_doc:
        return "In Progress"
    if row.student_evidence_attachment:
        return "Submitted"
    return "Not Started"


def _sgr(pe, sgr_name):
    for row in pe.graduation_requirements or []:
        if row.name == sgr_name:
            return row
    frappe.throw(
        _("Graduation requirement {0} not found on this enrollment.").format(sgr_name)
    )


def relink_after_resnapshot(pe):
    """A rebuild gives the SGR rows new names; point each waiver's exception
    at its new row (098 §6)."""
    for row in pe.graduation_requirements or []:
        if row.requirement_exception:
            frappe.db.set_value(
                "Requirement Exception",
                row.requirement_exception,
                "student_graduation_requirement",
                row.name,
                update_modified=False,
            )


def orphaned(pe_names=None):
    """Open exceptions whose requirement no longer applies to the student: a
    course no longer required of them, or a waived row gone from the
    snapshot (098 §6)."""
    filters = {"status": ("in", OPEN_STATUSES)}
    if pe_names:
        filters["program_enrollment"] = ("in", pe_names)
    rows = frappe.get_all(
        "Requirement Exception",
        filters=filters,
        fields=[
            "name",
            "program_enrollment",
            "student_name",
            "program",
            "kind",
            "status",
            "required_course",
            "student_graduation_requirement",
            "requirement_name",
        ],
    )
    out, cache = [], {}
    for r in rows:
        if r.program_enrollment not in cache:
            pe = frappe.get_doc("Program Enrollment", r.program_enrollment)
            cache[r.program_enrollment] = (
                mandatory_courses(pe),
                {g.name for g in pe.graduation_requirements or []},
            )
        mandatory, sgr_names = cache[r.program_enrollment]
        if r.kind == REQUIREMENT_WAIVER:
            if r.student_graduation_requirement not in sgr_names:
                out.append(r)
        elif r.required_course not in mandatory:
            out.append(r)
    return out


# --------------------------------------------------------------------------- #
# Notices
# --------------------------------------------------------------------------- #
def _what(doc):
    if doc.kind == SUBSTITUTION:
        return _("{0} in place of {1}").format(
            doc.substitute_course, doc.required_course
        )
    if doc.kind == COURSE_WAIVER:
        return _("waiver of {0}").format(doc.required_course)
    return _("waiver of {0}").format(
        doc.requirement_name or doc.student_graduation_requirement
    )


def _notify_request(doc):
    from seminary.seminary.comms import get_role_users

    users = set(get_role_users("Registrar"))
    director = frappe.db.get_value("Program", doc.program, "program_director")
    if director:
        users.add(director)
    users.discard(frappe.session.user)
    subject = _("Exception requested: {0}").format(doc.student_name)
    message = _("{0} asks for {1} ({2}). Reason: {3}").format(
        doc.student_name, _what(doc), doc.program, doc.reason
    )
    for user in users:
        person = frappe.db.get_value("Person", {"user": user}, "name")
        if person:
            _notify(
                person, f"rex-{doc.name}-requested-{user}", subject, message, doc.name
            )


def _notify_decision(doc):
    subject = _("Exception {0}: {1}").format(_(doc.status).lower(), _what(doc))
    message = _("{0} for {1} has been {2}.").format(
        _what(doc), doc.student_name, _(doc.status).lower()
    )
    if doc.decision_note:
        message += " " + _("Note: {0}").format(doc.decision_note)
    people = set()
    student_person = frappe.db.get_value("Student", doc.student, "person")
    if student_person:
        people.add(student_person)
    if doc.requested_by and doc.requested_by != frappe.session.user:
        person = frappe.db.get_value("Person", {"user": doc.requested_by}, "name")
        if person:
            people.add(person)
    for person in people:
        _notify(
            person, f"rex-{doc.name}-{doc.status}-{person}", subject, message, doc.name
        )


def _notify(person, key, subject, message, reference_name):
    from seminary.seminary import comms

    p = frappe.db.get_value(
        "Person", person, ["name", "user", "primary_email"], as_dict=True
    )
    if not p:
        return
    common = {
        "subject": subject,
        "message": message,
        "person": p.name,
        "category": "Transactional",
        "reference_doctype": "Requirement Exception",
        "reference_name": reference_name,
    }
    try:
        if p.user:
            comms.send_message(channel="In-App", dedupe_key=f"{key}-app", **common)
        if p.primary_email:
            comms.send_message(
                channel="Email",
                to_address=p.primary_email,
                dedupe_key=f"{key}-email",
                **common,
            )
    except (
        Exception
    ):  # noqa: BLE001 -- a notice must never undo the decision it reports
        frappe.log_error(frappe.get_traceback(), "requirement exception notice failed")


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #
def query(user=None):
    """A Program Chair lists only the programs they direct; the deciding
    roles list everything."""
    user = user or frappe.session.user
    if decides_everywhere(user):
        return ""
    if PROGRAM_CHAIR not in frappe.get_roles(user):
        return "1=0"
    return (
        "`tabRequirement Exception`.program in "  # nosec B608 -- user is escaped
        f"(select name from `tabProgram` where program_director = {frappe.db.escape(user)})"
    )


def has_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if decides_everywhere(user):
        return True
    if PROGRAM_CHAIR in frappe.get_roles(user):
        return doc.program in directed_programs(user)
    return False
