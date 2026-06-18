# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Leveling & advanced-standing engine (ADR 058).

A per-student Leveling Plan lives on the Program Enrollment (`leveling` child
table), seeded from a reusable `Leveling Profile` and freely overridable. Each
row is one outcome:

- ``Leveling Course``    — a (usually remedial) course the student must pass,
  unless a gating placement exam scores at/above its threshold (then placed out).
- ``Course Exemption``   — a course unconditionally placed out (advanced standing).
- ``Placement Assessment`` — points at a ``Placement Assessment`` whose recorded
  ``score`` (on the PE's ``placement_assessments`` child) gates the leveling
  courses in its group (ADR 060).
- ``Requirement Waiver`` — waive a graduation requirement (advanced standing).

`_resolve_rows` computes each row's ``resolution`` from the exam scores, then
`_apply_effects_inline` materializes the side effects onto the same in-memory
PE doc — ``Exempt`` Program Enrollment Course rows and SGR waivers. Both run in
the PE save hook (`resolve_rows_hook`), so entering the exam Score on the
requirement row and saving applies everything in one shot; the whitelisted
actions below do the same for profile-apply and after hand-edits.

Consumed by `graduation_candidate` (exemptions satisfy, Required leveling blocks),
`graduation.evaluate_activation` (Course Passed treats exemption as satisfied),
and the credit/GPA sums (leveling courses don't count toward the degree).
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, today

LEVELING_COURSE = "Leveling Course"
COURSE_EXEMPTION = "Course Exemption"
PLACEMENT_ASSESSMENT = "Placement Assessment"
REQUIREMENT_WAIVER = "Requirement Waiver"


# ---------------------------------------------------------------------------
# Resolution (pure — sets row.resolution / row.score, no side effects)
# ---------------------------------------------------------------------------


def _exam_scores(pe):
    """Map placement assessment -> recorded score from this PE's placement
    child rows (ADR 060 — score lives here, not on an SGR)."""
    scores = {}
    for row in pe.get("placement_assessments") or []:
        if row.get("score") is not None and row.get("assessment"):
            scores[row.assessment] = flt(row.score)
    return scores


def _ensure_placement_rows(pe):
    """Ensure a placement child row exists for every assessment the plan
    references (Placement Assessment rows and gated Leveling Course rows), so a
    Placement Examiner has something to score and it surfaces in their worklist.
    Idempotent; never removes rows."""
    referenced = {
        row.gating_assessment
        for row in pe.get("leveling") or []
        if row.gating_assessment and row.kind in (PLACEMENT_ASSESSMENT, LEVELING_COURSE)
    }
    existing = {r.assessment for r in pe.get("placement_assessments") or []}
    for assessment in sorted(referenced - existing):
        pe.append(
            "placement_assessments", {"assessment": assessment, "status": "Pending"}
        )


def _resolve_rows(pe):
    """Recompute each leveling row's resolution in place. Skips rows the
    registrar pinned with ``overridden``."""
    scores = _exam_scores(pe)
    for row in pe.get("leveling") or []:
        if row.overridden:
            continue
        if row.kind == COURSE_EXEMPTION:
            row.resolution = "Exempt"
        elif row.kind == REQUIREMENT_WAIVER:
            row.resolution = "Waived"
        elif row.kind == PLACEMENT_ASSESSMENT:
            row.resolution = "Pending"
            row.score = scores.get(row.gating_assessment)
        elif row.kind == LEVELING_COURSE:
            if not row.gating_assessment:
                row.resolution = "Required"
                row.score = None
            else:
                score = scores.get(row.gating_assessment)
                row.score = score
                if score is None:
                    row.resolution = "Pending"  # exam not scored yet
                elif flt(score) >= flt(row.exempt_if_score_at_least):
                    row.resolution = "Exempt"
                else:
                    row.resolution = "Required"


def resolve_rows_hook(pe):
    """PE before_update_after_submit hook: recompute resolutions from current
    exam scores and apply their effects, all within the ongoing save. This is
    what makes entering the exam Score on the requirement row (and saving) place
    the student out / require the leveling course with no extra step."""
    if pe.get("leveling"):
        _ensure_placement_rows(pe)
        _resolve_rows(pe)
        _apply_effects_inline(pe)


# ---------------------------------------------------------------------------
# Effects (mutate the in-memory PE doc — no save of their own)
# ---------------------------------------------------------------------------


def _apply_effects_inline(pe):
    """Materialize the resolved plan onto the in-memory PE doc (no save): an
    ``Exempt`` Program Enrollment Course row per placed-out course, and an SGR
    waiver per Requirement Waiver. Idempotent, and safe to call inside
    before_update_after_submit — the ongoing save persists the mutations, so a
    plain grid edit (e.g. entering the exam Score on the requirement row) applies
    everything in one save, no separate button needed."""
    for row in pe.get("leveling") or []:
        if row.resolution == "Exempt" and row.course:
            _ensure_exempt_pec(pe, row.course)
        elif row.resolution == "Waived" and row.graduation_requirement_item:
            _waive_matching_sgr(pe, row.graduation_requirement_item)


def _ensure_exempt_pec(pe, course):
    """Ensure the placed-out course is represented as an ``Exempt`` Program
    Enrollment Course (no grade, no credit). Returns True if it mutated the doc."""
    for pec in pe.get("courses") or []:
        if pec.course == course:
            if pec.status in ("Pass", "Exempt"):
                return False  # already satisfied / already exempt
            pec.status = "Exempt"
            pec.count_in_gpa = 0
            return True
    course_name = frappe.db.get_value("Course", course, "course_name") or course
    pe.append(
        "courses",
        {
            "course": course,
            "course_name": course_name,
            "status": "Exempt",
            "count_in_gpa": 0,
            "credits": 0,
        },
    )
    return True


def _waive_matching_sgr(pe, grad_requirement_item):
    """Waive every open SGR for the given library requirement. Returns True if
    it changed anything."""
    changed = False
    for sgr in pe.get("graduation_requirements") or []:
        if sgr.grad_requirement_item == grad_requirement_item and sgr.status not in (
            "Fulfilled",
            "Waived",
        ):
            sgr.waived = 1
            sgr.waiver_reason = _("Waived by leveling / advanced-standing plan.")
            sgr.waived_by = frappe.session.user
            sgr.waived_on = now_datetime()
            sgr.status = "Waived"
            changed = True
    return changed


# ---------------------------------------------------------------------------
# Read helpers (consumed by candidacy, activation, credit/GPA sums)
# ---------------------------------------------------------------------------


def leveling_sets(pe_name):
    """Return (exempted_courses, required_leveling_courses, leveling_courses)
    for a Program Enrollment, read straight from the (authoritative) plan.

    - exempted_courses: courses placed out → treated as satisfied.
    - required_leveling_courses: Required leveling courses → must be passed.
    - leveling_courses: every Leveling Course → excluded from degree credit/GPA.
    """
    rows = frappe.get_all(
        "Program Enrollment Leveling",
        filters={"parent": pe_name, "parenttype": "Program Enrollment"},
        fields=["kind", "course", "resolution"],
    )
    exempted, required, leveling_courses = set(), set(), set()
    for r in rows:
        if not r.course:
            continue
        if r.resolution == "Exempt":
            exempted.add(r.course)
        if r.kind == LEVELING_COURSE:
            leveling_courses.add(r.course)
            if r.resolution == "Required":
                required.add(r.course)
    return exempted, required, leveling_courses


def leveling_excluded_courses(pe_name):
    """Courses that must NOT count toward degree credit / GPA (every Leveling
    Course on the plan — remedial by nature)."""
    return leveling_sets(pe_name)[2]


# ---------------------------------------------------------------------------
# Whitelisted actions
# ---------------------------------------------------------------------------


@frappe.whitelist()
def apply_leveling_profile(program_enrollment, profile):
    """Seed (append) a Leveling Profile's items onto a Program Enrollment as an
    editable plan, then resolve. Skips items already present (by kind + course +
    requirement) so re-applying is idempotent."""
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    prof = frappe.get_doc("Leveling Profile", profile)

    existing = {
        (r.kind, r.course, r.graduation_requirement_item, r.gating_assessment)
        for r in (pe.leveling or [])
    }
    added = 0
    for item in prof.items or []:
        key = (
            item.kind,
            item.course,
            item.graduation_requirement_item,
            item.gating_assessment,
        )
        if key in existing:
            continue
        pe.append(
            "leveling",
            {
                "kind": item.kind,
                "course": item.course,
                "graduation_requirement_item": item.graduation_requirement_item,
                "gating_assessment": item.gating_assessment,
                "exempt_if_score_at_least": item.exempt_if_score_at_least,
                "note": item.note,
                "resolution": "Pending",
                "source_profile": prof.name,
            },
        )
        existing.add(key)
        added += 1

    pe.leveling_profile = prof.name
    _ensure_placement_rows(pe)
    _resolve_rows(pe)
    _apply_effects_inline(pe)
    pe.save()
    return {"added": added}


@frappe.whitelist()
def mark_placement_scored(program_enrollment, assessment, score, attachment_url=None):
    """Record a placement assessment's score (ADR 060), then resolve the plan via
    the PE save hook (gated leveling courses place out immediately). Authorized
    for a department Placement Examiner wired to the assessment's Academic Unit
    (ADR 059), or a full-access role. Optionally attaches examiner evidence."""
    from seminary.seminary import faculty

    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    unit = frappe.db.get_value("Placement Assessment", assessment, "academic_unit")
    faculty.require_capability(unit, faculty.PLACEMENT_EXAMINER_ROUTE)

    row = next(
        (r for r in pe.placement_assessments if r.assessment == assessment), None
    )
    if row is None:
        row = pe.append("placement_assessments", {"assessment": assessment})
    row.score = flt(score)
    row.status = "Scored"
    if attachment_url:
        row.staff_evidence_attachment = attachment_url
    row.verified_by = frappe.session.user
    row.verified_on = now_datetime()
    # require_capability above is the authorization; the examiner needn't hold raw
    # PE write permission.
    pe.save(ignore_permissions=True)
    return {"assessment": assessment, "score": flt(score), "status": row.status}


@frappe.whitelist()
def resolve_leveling_plan(program_enrollment):
    """Recompute resolutions from current exam scores and apply effects.
    Mostly redundant now that the PE save hook does the same — kept as an
    explicit button for after hand-edits and for older drafts."""
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    _resolve_rows(pe)
    _apply_effects_inline(pe)
    pe.save()
    return {"rows": len(pe.leveling or [])}
