# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Graduation requirements engine.

Resolves which Program Graduation Requirement policy applies to a given
Program Enrollment, materializes a snapshot child table at enrollment time,
and reflects status changes from arbitrary linked documents back onto the
student's Student Graduation Requirement rows.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime, today

LINKED_DOC_HOOK_FLAG = "_seminary_grad_link_doctypes"


# ---------------------------------------------------------------------------
# Policy resolution
# ---------------------------------------------------------------------------


def resolve_policy(program, on_date):
    """Return the name of the active Program Graduation Requirement for the
    given program at on_date, or None if no policy applies.

    Picks the policy whose [active_from, active_until] interval covers on_date.
    If multiple match (data-entry bug; PGR.validate prevents this on the same
    program), the one with the latest active_from wins.
    """
    if not program or not on_date:
        return None

    on_date = getdate(on_date)
    candidates = frappe.get_all(
        "Program Graduation Requirement",
        filters={"program_name": program, "active": 1, "docstatus": ("!=", 2)},
        fields=["name", "active_from", "active_until"],
    )

    matches = []
    for cand in candidates:
        start = getdate(cand.active_from) if cand.active_from else None
        end = getdate(cand.active_until) if cand.active_until else None
        if start and on_date < start:
            continue
        if end and on_date > end:
            continue
        matches.append((start or getdate("1900-01-01"), cand.name))

    if not matches:
        return None

    matches.sort(key=lambda x: x[0], reverse=True)
    return matches[0][1]


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def snapshot_graduation_requirements(program_enrollment_doc):
    """Populate Program Enrollment's graduation_requirements child table from
    the resolved policy. Idempotent: skips if already populated."""
    if program_enrollment_doc.get("graduation_requirements"):
        return

    policy_name = resolve_policy(
        program_enrollment_doc.program, program_enrollment_doc.enrollment_date
    )
    if not policy_name:
        return

    policy = frappe.get_doc("Program Graduation Requirement", policy_name)
    program_enrollment_doc.graduation_policy = policy_name

    for pgr_item in policy.pgr_items or []:
        library_type = frappe.db.get_value(
            "Graduation Requirement Item",
            pgr_item.grad_requirement_item,
            "requirement_type",
        )
        if library_type == "Manual Verification":
            quantity = max(int(pgr_item.quantity_required or 1), 1)
        else:
            quantity = 1
        for slot in range(1, quantity + 1):
            row = _build_sgr_row(program_enrollment_doc, pgr_item, slot)
            program_enrollment_doc.append("graduation_requirements", row)


def _build_sgr_row(program_enrollment_doc, pgr_item, slot_index):
    library = frappe.get_cached_doc(
        "Graduation Requirement Item", pgr_item.grad_requirement_item
    )
    row = {
        "requirement_name": library.requirement_name,
        "requirement_type": library.requirement_type,
        "mandatory": pgr_item.mandatory,
        "slot_index": slot_index,
        "status": "Not Started",
        "link_doctype": (
            library.link_doctype
            if library.requirement_type == "Linked Document"
            else None
        ),
        "grad_requirement_item": library.name,
        "pgr_item": pgr_item.name,
    }
    due = compute_due_date(pgr_item, program_enrollment_doc)
    if due:
        row["due_date"] = due
    return row


@frappe.whitelist()
def resnapshot(program_enrollment, preserve_waivers=1):
    """Registrar action: rebuild the snapshot from the currently-resolved
    policy. Preserves waived rows by default."""
    preserve_waivers = int(preserve_waivers or 0)
    enrollment = frappe.get_doc("Program Enrollment", program_enrollment)

    keep = []
    if preserve_waivers:
        keep = [
            row.as_dict() for row in enrollment.graduation_requirements if row.waived
        ]

    enrollment.graduation_requirements = []
    enrollment.graduation_policy = None
    snapshot_graduation_requirements(enrollment)

    if keep:
        _merge_preserved_waivers(enrollment, keep)

    enrollment.save(ignore_permissions=False)
    return {"requirements": len(enrollment.graduation_requirements)}


def _merge_preserved_waivers(enrollment, keep):
    """Re-apply waiver state to matching rows in the new snapshot."""
    by_key = {(k.get("grad_requirement_item"), k.get("slot_index")): k for k in keep}
    for row in enrollment.graduation_requirements:
        preserved = by_key.get((row.grad_requirement_item, row.slot_index))
        if not preserved:
            continue
        row.waived = 1
        row.waiver_reason = preserved.get("waiver_reason")
        row.waived_by = preserved.get("waived_by")
        row.waived_on = preserved.get("waived_on")
        row.status = "Waived"


# ---------------------------------------------------------------------------
# Activation evaluation
# ---------------------------------------------------------------------------


def evaluate_activation(sgr_row, program_enrollment):
    """Return True if the requirement is currently active (i.e. countable
    towards graduation eligibility). Always Active rows return True; others
    consult their activation_mode rules.

    Returns False when the requirement exists but is not yet active. Returns
    True when the source pgr_item can no longer be located (treat as active so
    policy deletes do not silently mute requirements)."""
    if not sgr_row.pgr_item:
        return True

    pgr_item = _load_pgr_item(sgr_row.pgr_item)
    if not pgr_item:
        return True

    mode = pgr_item.get("activation_mode") or "Always Active"

    if mode == "Always Active":
        return True

    if mode == "After Requirement":
        prereqs = pgr_item.get("prerequisite_requirement") or []
        if not prereqs:
            return True
        fulfilled_libs = {
            r.grad_requirement_item
            for r in program_enrollment.graduation_requirements
            if r.status in ("Fulfilled", "Waived")
        }
        needed = {p.graduation_requirement_item for p in prereqs}
        return needed.issubset(fulfilled_libs)

    if mode == "Time Offset":
        anchor_date = _resolve_anchor_date(
            pgr_item.get("offset_anchor"), program_enrollment
        )
        if not anchor_date:
            return True
        due = _apply_offset(
            anchor_date, pgr_item.get("offset_value"), pgr_item.get("offset_unit")
        )
        return getdate(today()) >= getdate(due) if due else True

    if mode == "On Document Status":
        # Activation is event-driven via reflect_linked_doc_status; the row is
        # considered active for display from creation.
        return True

    return True


def compute_due_date(pgr_item, program_enrollment):
    """Return the due date for a Time Offset requirement, or None for other
    activation modes."""
    if not pgr_item or pgr_item.get("activation_mode") != "Time Offset":
        return None

    anchor_date = _resolve_anchor_date(
        pgr_item.get("offset_anchor"), program_enrollment
    )
    if not anchor_date:
        return None
    return _apply_offset(
        anchor_date, pgr_item.get("offset_value"), pgr_item.get("offset_unit")
    )


def _resolve_anchor_date(anchor, program_enrollment):
    if anchor == "Expected Graduation Date":
        return program_enrollment.get("expected_graduation_date")
    if anchor == "Program Starts":
        return program_enrollment.get("enrollment_date")
    if anchor == "Last Term Starts":
        # Walk forward from the enrollment term by Program.terms_complete - 1.
        program = frappe.get_cached_doc("Program", program_enrollment.program)
        terms = int(program.get("terms_complete") or 0) or 1
        start_term = program_enrollment.get("academic_term")
        last_term = _shift_term(start_term, terms - 1) if start_term else None
        return (
            frappe.db.get_value("Academic Term", last_term, "term_start_date")
            if last_term
            else None
        )
    return None


def _apply_offset(anchor_date, value, unit):
    value = int(value or 0)
    if unit == "Days":
        return add_days(anchor_date, value)
    if unit == "Academic Term":
        # Approximate one academic term = 120 days for Time Offset due dates.
        # Replace with a real walk over Academic Term records if registrars
        # need finer accuracy.
        return add_days(anchor_date, value * 120)
    return anchor_date


def _shift_term(term_name, n):
    """Walk n academic terms forward (or backward) from the given term."""
    if not term_name or not n:
        return term_name
    current = frappe.db.get_value(
        "Academic Term", term_name, ["academic_year", "term_start_date"], as_dict=True
    )
    if not current:
        return term_name

    direction_asc = n > 0
    step = 1 if direction_asc else -1
    remaining = abs(n)
    cursor = term_name
    while remaining > 0:
        next_term = _next_term(cursor, ascending=direction_asc)
        if not next_term:
            break
        cursor = next_term
        remaining -= step * (1 if direction_asc else -1)
    return cursor


def _next_term(term_name, ascending=True):
    current_start = frappe.db.get_value("Academic Term", term_name, "term_start_date")
    if not current_start:
        return None
    op = (">", "asc") if ascending else ("<", "desc")
    row = frappe.get_all(
        "Academic Term",
        filters={"term_start_date": (op[0], current_start)},
        order_by=f"term_start_date {op[1]}",
        limit=1,
        pluck="name",
    )
    return row[0] if row else None


def _load_pgr_item(name):
    if not name:
        return None
    row = frappe.db.get_value(
        "Program Grad Req Items",
        name,
        ["activation_mode", "offset_anchor", "offset_value", "offset_unit"],
        as_dict=True,
    )
    if not row:
        return None
    row["prerequisite_requirement"] = frappe.get_all(
        "Grad Req Item Prerequisite",
        filters={"parent": name},
        fields=["graduation_requirement_item"],
    )
    return row


# ---------------------------------------------------------------------------
# Expected graduation date default
# ---------------------------------------------------------------------------


def compute_expected_graduation_date(program_enrollment):
    """Default the expected graduation date.

    Strategy:
    1. If Program.terms_complete is set, walk that many academic terms forward
       from the enrollment term and use the last term's end date.
    2. Otherwise, fall back to enrollment_date + 4 years as a generic seminary
       program length. The registrar can always override.
    """
    if program_enrollment.get("expected_graduation_date"):
        return program_enrollment.expected_graduation_date

    if not program_enrollment.get("program"):
        return None

    program = frappe.get_cached_doc("Program", program_enrollment.program)
    terms = int(program.get("terms_complete") or 0)
    enrollment_date = program_enrollment.get("enrollment_date")

    if terms > 0 and program_enrollment.get("academic_term"):
        last_term = _shift_term(program_enrollment.academic_term, terms - 1)
        if last_term:
            end = frappe.db.get_value("Academic Term", last_term, "term_end_date")
            if end:
                return end

    if enrollment_date:
        return add_days(enrollment_date, 365 * 4)

    return None


# ---------------------------------------------------------------------------
# Linked document → SGR reflection
# ---------------------------------------------------------------------------


def reflect_linked_doc_status(doc, method=None):
    """Generic on_update_after_submit hook. If `doc.doctype` is a Linked
    Document target for any Graduation Requirement Item, look for SGR rows
    whose `linked_doc == doc.name` and update their status to match the
    configured `linked_doc_status`."""
    if doc.doctype not in _linked_doctypes():
        return

    rows = frappe.get_all(
        "Student Graduation Requirement",
        filters={"link_doctype": doc.doctype, "linked_doc": doc.name},
        fields=["name", "parent", "parenttype", "pgr_item", "status", "waived"],
    )
    if not rows:
        return

    current_value = (
        doc.get("workflow_state") if doc.meta.get_field("workflow_state") else None
    ) or doc.get("status")

    for row in rows:
        if row.waived:
            continue
        expected = frappe.db.get_value(
            "Program Grad Req Items", row.pgr_item, "linked_doc_status"
        )
        if expected and current_value == expected and row.status != "Fulfilled":
            _mark_sgr_fulfilled(row.parent, row.parenttype, row.name)


def _mark_sgr_fulfilled(parent, parenttype, sgr_name):
    parent_doc = frappe.get_doc(parenttype, parent)
    for child in parent_doc.graduation_requirements:
        if child.name == sgr_name and child.status != "Fulfilled":
            child.status = "Fulfilled"
            child.fulfilled_on = today()
            parent_doc.save(ignore_permissions=True)
            break


def _linked_doctypes():
    """Cached set of DocTypes that appear as a link_doctype on any library
    requirement item. Cleared by the library item's controller on save."""
    cached = frappe.cache().get_value(LINKED_DOC_HOOK_FLAG)
    if cached is not None:
        return set(cached)

    if not frappe.db.table_exists("Graduation Requirement Item"):
        return set()

    doctypes = frappe.get_all(
        "Graduation Requirement Item",
        filters={"requirement_type": "Linked Document", "link_doctype": ("is", "set")},
        pluck="link_doctype",
    )
    doctypes = list({d for d in doctypes if d})
    frappe.cache().set_value(LINKED_DOC_HOOK_FLAG, doctypes, expires_in_sec=300)
    return set(doctypes)


def invalidate_linked_doctype_cache(doc=None, method=None):
    """Hook fired on Graduation Requirement Item save/delete to refresh the
    linked-doctype cache used by reflect_linked_doc_status."""
    frappe.cache().delete_value(LINKED_DOC_HOOK_FLAG)


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


def all_mandatory_satisfied(program_enrollment):
    """Return True when every active mandatory SGR row is Fulfilled or
    Waived. Inactive (not-yet-due) requirements do not block eligibility."""
    for row in program_enrollment.graduation_requirements or []:
        if not row.mandatory:
            continue
        if row.status in ("Fulfilled", "Waived"):
            continue
        if not evaluate_activation(row, program_enrollment):
            continue
        return False
    return True


# ---------------------------------------------------------------------------
# Whitelisted SGR actions (called from the audit page)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def mark_sgr_verified(program_enrollment, sgr_name, attachment_url=None):
    """Staff action: mark a Manual Verification row Fulfilled, optionally
    attaching staff evidence."""
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    row = _find_sgr(pe, sgr_name)
    if attachment_url:
        row.staff_evidence_attachment = attachment_url
    row.status = "Fulfilled"
    row.fulfilled_on = today()
    row.verified_by = frappe.session.user
    row.verified_on = now_datetime()
    pe.save(ignore_permissions=False)
    return {"status": row.status}


@frappe.whitelist()
def waive_sgr(program_enrollment, sgr_name, reason):
    """Staff action: waive a requirement, recording who and why."""
    if not reason or not reason.strip():
        frappe.throw(_("A waiver reason is required."))
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    row = _find_sgr(pe, sgr_name)
    row.waived = 1
    row.waiver_reason = reason
    row.waived_by = frappe.session.user
    row.waived_on = now_datetime()
    row.status = "Waived"
    pe.save(ignore_permissions=False)
    return {"status": row.status}


@frappe.whitelist()
def submit_student_evidence(program_enrollment, sgr_name, attachment_url):
    """Student-portal action: attach evidence and flip status to Submitted."""
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    row = _find_sgr(pe, sgr_name)
    if pe.student != frappe.db.get_value(
        "User", frappe.session.user, "username"
    ) and not _user_owns_enrollment(pe):
        frappe.throw(
            _("You can only submit evidence for your own enrollment."),
            frappe.PermissionError,
        )
    row.student_evidence_attachment = attachment_url
    if row.status in ("Not Started", "In Progress"):
        row.status = "Submitted"
    pe.save(ignore_permissions=True)
    return {"status": row.status}


def _find_sgr(program_enrollment_doc, sgr_name):
    for row in program_enrollment_doc.graduation_requirements or []:
        if row.name == sgr_name:
            return row
    frappe.throw(_("Requirement {0} not found on this enrollment.").format(sgr_name))


def _user_owns_enrollment(program_enrollment_doc):
    """Return True when the current session user is the student on this enrollment."""
    user_email = frappe.session.user
    student_email = frappe.db.get_value(
        "Student", program_enrollment_doc.student, "student_email_id"
    )
    return user_email == student_email


@frappe.whitelist()
def start_recommendation_letter(
    program_enrollment,
    sgr_name,
    recommender_name,
    recommender_email,
    recommender_role=None,
):
    """Student-portal action: create and submit a Recommendation Letter that
    fulfills the given SGR slot. Triggers the request email to the recommender."""
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    if not _user_owns_enrollment(pe):
        frappe.throw(
            _("You can only request recommendations for your own enrollment."),
            frappe.PermissionError,
        )

    row = _find_sgr(pe, sgr_name)
    if row.link_doctype != "Recommendation Letter":
        frappe.throw(_("This requirement is not a Recommendation Letter slot."))
    if row.linked_doc:
        frappe.throw(_("A recommendation letter already exists for this slot."))

    letter = frappe.get_doc(
        {
            "doctype": "Recommendation Letter",
            "program_enrollment": program_enrollment,
            "student_grad_requirement": sgr_name,
            "slot_index": row.slot_index or 1,
            "recommender_name": recommender_name,
            "recommender_email": recommender_email,
            "recommender_role": recommender_role,
        }
    )
    letter.insert(ignore_permissions=True)
    letter.submit()
    return {"name": letter.name}


@frappe.whitelist()
def start_culminating_project(
    program_enrollment,
    sgr_name,
    project_title,
    advisor,
    project_type=None,
    abstract=None,
):
    """Student-portal action: create a Culminating Project (Draft state) that
    fulfills the given SGR slot."""
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    if not _user_owns_enrollment(pe):
        frappe.throw(
            _("You can only start a project for your own enrollment."),
            frappe.PermissionError,
        )

    row = _find_sgr(pe, sgr_name)
    if row.link_doctype != "Culminating Project":
        frappe.throw(_("This requirement is not a Culminating Project slot."))
    if row.linked_doc:
        frappe.throw(_("A culminating project already exists for this slot."))

    project = frappe.get_doc(
        {
            "doctype": "Culminating Project",
            "program_enrollment": program_enrollment,
            "student_grad_requirement": sgr_name,
            "project_title": project_title,
            "project_type": project_type or "Thesis",
            "advisor": advisor,
            "abstract": abstract,
        }
    )
    project.insert(ignore_permissions=True)
    # Link the SGR row to the draft project so the student can find it from
    # the audit page even before workflow advances.
    row.linked_doc = project.name
    row.link_doctype = "Culminating Project"
    row.status = "In Progress"
    pe.save(ignore_permissions=True)
    return {"name": project.name}
