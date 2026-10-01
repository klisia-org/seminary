# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Two doors into the official academic record, for other apps to extend.

A student's official record is the Program Enrollment Course rows on their
Program Enrollment plus the denormalized credit total. The parent is submitted,
so those rows are written with frappe.db.set_value, and set_value fires no
doc_events: an app that must react to a grade (an audit trail, a sync to a
finance system, a notification) had no way to see it without editing
SeminaryERP. The plan a student graduates under is read straight off the
Program for the same reason: nothing could substitute another one.

1. Writes. Every write to the result of a transcript row, and every write of an
   enrollment's credit total, goes through ``write_grade``,
   ``set_total_credits`` or ``announce_new_row``. After the write, each hook
   registered as ``seminary_record_write`` is called with one ``frappe._dict``:

       program_enrollment, row, course, course_schedule, academic_term,
       before, after          -- dicts of GRADE_FIELDS ({} before a new row)
       credits_before, credits_after,
       changed                -- False when the write repeated what was there
       action, reason, source -- what happened, why, and which code path

   Hooks run in the same transaction; raising aborts the write. A hook may add
   keys to the dict, and the caller gets the dict back.

2. The plan. ``get_curriculum(pe, program)`` returns the courses and graduation
   thresholds that bind an enrollment. By default that is the Program as it
   stands. Hooks registered as ``seminary_curriculum_resolver`` are asked
   first, last registered first; the first one that returns a value wins
   (e.g. a plan frozen when the student enrolled).

``test_record_writes.TestNothingWritesAroundTheDoor`` fails the build if a
direct write to these fields appears anywhere else in the app.
"""

import frappe
from frappe.utils import cint, flt

ROW = "Program Enrollment Course"

# The fields that make up the official result of one attempt.
GRADE_FIELDS = ("pec_finalgradecode", "pec_finalgradenum", "status", "count_in_gpa")

# What happened. Free text for hooks; these are the ones SeminaryERP emits.
POSTED = "Grade Posted"
CHANGED = "Grade Changed"
FAILED_FOR_ABSENCE = "Failed for Absence"
ABSENCE_REVERSED = "Absence Failure Reversed"
WITHDRAWN = "Withdrawn"
TRANSFER = "Transfer Credit"
CREDITS_RECOMPUTED = "Credits Recomputed"

WRITE_HOOK = "seminary_record_write"
CURRICULUM_HOOK = "seminary_curriculum_resolver"


def write_grade(row, values, *, source, action=None, reason=None, total_credits=None):
    """Apply ``values`` to a transcript row, and ``total_credits`` (when given)
    to its enrollment, then tell the hooks.

    ``action`` defaults to Grade Posted for a row with no grade yet and Grade
    Changed otherwise."""
    head = frappe.db.get_value(
        ROW,
        row,
        ["parent", "course", "course_name", "academic_term", *GRADE_FIELDS],
        as_dict=True,
    )
    if not head:
        frappe.throw(frappe._("Transcript row {0} not found.").format(row))

    before = {f: head.get(f) for f in GRADE_FIELDS}
    after = dict(before, **{f: values[f] for f in GRADE_FIELDS if f in values})

    credits_before = cint(
        frappe.db.get_value("Program Enrollment", head.parent, "totalcredits")
    )
    credits_after = credits_before if total_credits is None else cint(total_credits)

    frappe.db.set_value(ROW, row, values)
    if credits_after != credits_before:
        frappe.db.set_value(
            "Program Enrollment", head.parent, "totalcredits", credits_after
        )

    return _announce(
        program_enrollment=head.parent,
        row=row,
        course=head.course_name,
        course_schedule=head.course,
        academic_term=head.academic_term,
        before=before,
        after=after,
        credits_before=credits_before,
        credits_after=credits_after,
        changed=not _same(before, after) or credits_after != credits_before,
        action=action or (CHANGED if before["pec_finalgradecode"] else POSTED),
        reason=reason,
        source=source,
    )


def announce_new_row(row, *, source, action=TRANSFER, reason=None):
    """A transcript row created already carrying a result (transfer credit) was
    saved through its parent document; tell the hooks. There is no before."""
    head = frappe.db.get_value(
        ROW,
        row,
        ["parent", "course", "course_name", "academic_term", *GRADE_FIELDS],
        as_dict=True,
    )
    if not head:
        return None
    credits = cint(frappe.db.get_value("Program Enrollment", head.parent, "totalcredits"))
    return _announce(
        program_enrollment=head.parent,
        row=row,
        course=head.course_name,
        course_schedule=head.course,
        academic_term=head.academic_term,
        before={},
        after={f: head.get(f) for f in GRADE_FIELDS},
        credits_before=credits,
        credits_after=credits,
        changed=True,
        action=action,
        reason=reason,
        source=source,
    )


def set_total_credits(program_enrollment, total, *, source, reason=None):
    """Write an enrollment's credit total on its own (a recomputation, not the
    consequence of one grade), then tell the hooks."""
    before = cint(
        frappe.db.get_value("Program Enrollment", program_enrollment, "totalcredits")
    )
    total = cint(total)
    frappe.db.set_value(
        "Program Enrollment",
        program_enrollment,
        "totalcredits",
        total,
        update_modified=False,
    )
    return _announce(
        program_enrollment=program_enrollment,
        row=None,
        course=None,
        course_schedule=None,
        academic_term=None,
        before={},
        after={},
        credits_before=before,
        credits_after=total,
        changed=total != before,
        action=CREDITS_RECOMPUTED,
        reason=reason,
        source=source,
    )


def _announce(**change):
    change = frappe._dict(change)
    for path in frappe.get_hooks(WRITE_HOOK):
        frappe.get_attr(path)(change)
    return change


def _same(before, after):
    return (
        (before.get("pec_finalgradecode") or "") == (after.get("pec_finalgradecode") or "")
        and flt(before.get("pec_finalgradenum")) == flt(after.get("pec_finalgradenum"))
        and (before.get("status") or "") == (after.get("status") or "")
        and cint(before.get("count_in_gpa")) == cint(after.get("count_in_gpa"))
    )


def get_curriculum(pe, program=None):
    """The plan that binds this enrollment.

    ``pe`` is a Program Enrollment document or a bare dict from db.get_value.
    Returns a ``frappe._dict`` with ``frozen``, ``frozen_on``, ``courses``
    (rows carrying course, course_name, required, repeatable, credits,
    course_term), ``credits_complete``, ``terms_complete`` and
    ``min_graduation_gpa``. ``credits`` is ``Program Course.pgmcourse_credits``.
    """
    for path in reversed(frappe.get_hooks(CURRICULUM_HOOK)):
        curriculum = frappe.get_attr(path)(pe, program)
        if curriculum is not None:
            return curriculum
    return program_curriculum(program or frappe.get_cached_doc("Program", pe.program))


def program_curriculum(program):
    """The Program as it stands today, in the shape ``get_curriculum`` returns."""
    return frappe._dict(
        frozen=False,
        frozen_on=None,
        courses=[
            frappe._dict(
                course=pc.course,
                course_name=pc.course_name,
                required=cint(pc.required),
                repeatable=cint(pc.repeatable),
                credits=cint(pc.pgmcourse_credits),
                course_term=cint(pc.course_term),
            )
            for pc in program.courses
            if not pc.disabled
        ],
        credits_complete=cint(program.credits_complete),
        terms_complete=cint(program.terms_complete),
        min_graduation_gpa=flt(program.get("min_graduation_gpa")),
    )
