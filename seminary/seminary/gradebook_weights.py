# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Weighted categories, dropped scores and excused assessments (decisions/096).

One function, ``compute``, says how much each assessment counts for one
student. The final grade, the current and projected grades and the gradebook
all read it, so they cannot disagree:

* a section with no categories weighs each row by its own ``weight_scac``, as
  before; an excused row's weight spreads over the others in proportion;
* with categories, each category's weight is split among its rows by the
  rubric rule (095 section 3): a typed weight is a fixed percent of the
  category, rows left at 0 share what is left;
* a category's lowest ``drop_lowest`` rows leave the student's grade, then the
  rows still counting share the category again; a category with nothing left
  gives its weight to the others in proportion (section 5).

``maximum_score`` on each result card is this function's output for that
student, rewritten by ``refresh_roster`` until grades are sent.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from seminary.seminary.rubrics import shares, slug

DROPPED = "Dropped"
EXCUSED = "Excused"

ROW_FIELDS = [
    "name",
    "title",
    "weight_scac",
    "extracredit_scac",
    "category_code",
    "never_drop",
    "due_date",
]
CATEGORY_FIELDS = ["category_code", "title", "weight", "drop_lowest"]


# --- arithmetic (no frappe) ----------------------------------------------------


def _scored(row):
    return bool(row.get("graded")) or flt(row.get("score")) > 0


def _spread(weights, total):
    """Scale ``{key: weight}`` so it sums to ``total``."""
    present = sum(weights.values())
    if not present:
        return {k: 0.0 for k in weights}
    return {k: w * total / present for k, w in weights.items()}


def _drops(members, drop_lowest, final):
    """Names of the rows dropped from one category for one student.

    Ranked by score (already net of any late deduction), ties dropping the
    earlier due date. Before grades are sent only scored rows can drop: an
    ungraded quiz is not yet the student's lowest. At least one row counts."""
    n = min(cint(drop_lowest), len(members) - 1)
    if n <= 0:
        return set()
    candidates = [
        r for r in members if not cint(r.get("never_drop")) and (final or _scored(r))
    ]
    candidates.sort(key=lambda r: (flt(r.get("score")), str(r.get("due_date") or "")))
    return {r["name"] for r in candidates[:n]}


def compute(rows, categories, final=False):
    """``{row name: {"weight": percent of the final grade, "status": None |
    DROPPED | EXCUSED}}`` for one student's regular (non extra credit) rows.

    ``rows`` carry ``name``, ``weight_scac``, ``extracredit_scac``,
    ``category_code``, ``never_drop``, ``due_date`` and, for the student,
    ``excused``, ``graded`` and ``score``. ``final`` is True at Send Grades,
    when an ungraded row counts as 0 and can be dropped."""
    regular = [r for r in rows if not cint(r.get("extracredit_scac"))]
    out = {}
    excused = {r["name"] for r in regular if cint(r.get("excused"))}
    for name in excused:
        out[name] = {"weight": 0.0, "status": EXCUSED}

    if not categories:
        counting = {
            r["name"]: flt(r.get("weight_scac"))
            for r in regular
            if r["name"] not in excused
        }
        total = sum(flt(r.get("weight_scac")) for r in regular)
        for name, w in _spread(counting, total).items():
            out[name] = {"weight": w, "status": None}
        return out

    by_code = {c.get("category_code"): c for c in categories}
    counting = {}  # category code -> {row name: share of the category}
    for code, cat in by_code.items():
        members = [
            r
            for r in regular
            if r.get("category_code") == code and r["name"] not in excused
        ]
        dropped = _drops(members, cat.get("drop_lowest"), final)
        for name in dropped:
            out[name] = {"weight": 0.0, "status": DROPPED}
        left = [r for r in members if r["name"] not in dropped]
        if left:
            counting[code] = shares(
                [
                    {"criterion_code": r["name"], "weight": r.get("weight_scac")}
                    for r in left
                ]
            )

    weights = _spread(
        {code: flt(by_code[code].get("weight")) for code in counting},
        sum(flt(c.get("weight")) for c in categories),
    )
    for code, row_shares in counting.items():
        for name, share in row_shares.items():
            out[name] = {"weight": weights[code] * share, "status": None}
    # A row naming no category the section has counts for nothing; validation
    # refuses that on save, so this is only a stale row mid-edit.
    for r in regular:
        out.setdefault(r["name"], {"weight": 0.0, "status": None})
    return out


def nominal(rows, categories):
    """Each row's share of the final grade before any drop or excuse: what the
    assessment page shows beside the weight."""
    bare = [{**r, "excused": 0, "graded": 0, "score": 0} for r in rows]
    return {k: v["weight"] for k, v in compute(bare, categories, final=False).items()}


def final_share(scheduled_assess_criteria):
    """One row's share of the final grade (a percent) before any drop or
    excuse. For other apps: with categories ``weight_scac`` is a share of the
    category, not of the grade."""
    parent = frappe.db.get_value(
        "Scheduled Course Assess Criteria", scheduled_assess_criteria, "parent"
    )
    if not parent:
        return 0.0
    return flt(
        nominal(section_rows(parent), section_categories(parent)).get(
            scheduled_assess_criteria
        )
    )


def validate(categories, rows):
    """Refuse a category setup the arithmetic cannot honour. ``categories`` are
    the section's category rows (codes filled), ``rows`` its criteria rows."""
    if not categories:
        return
    codes = [c.category_code for c in categories]
    dupes = sorted({c for c in codes if codes.count(c) > 1})
    if dupes:
        frappe.throw(
            _("Two categories have the code {0}. Give each its own.").format(dupes[0])
        )
    total = sum(flt(c.weight) for c in categories)
    if abs(total - 100) > 0.01:
        frappe.throw(
            _("The category weights total {0}%. They must total 100%.").format(
                flt(total, 2)
            )
        )
    by_code = {c.category_code: c for c in categories}
    regular = [r for r in rows if not cint(r.extracredit_scac)]
    for r in regular:
        if r.category_code not in by_code:
            frappe.throw(
                _(
                    "{0} has no category. Choose one of this section's categories for it."
                ).format(r.title or _("(untitled)"))
            )
    for cat in categories:
        members = [r for r in regular if r.category_code == cat.category_code]
        fixed = sum(flt(r.weight_scac) for r in members if flt(r.weight_scac) > 0)
        blank = any(flt(r.weight_scac) <= 0 for r in members)
        if blank and fixed >= 100:
            frappe.throw(
                _(
                    "In {0}, the typed weights already reach {1}%, leaving nothing for "
                    "the assessments left at 0. Lower them, or give each a weight."
                ).format(cat.title, flt(fixed, 2))
            )
        droppable = sum(1 for r in members if not cint(r.never_drop))
        if cint(cat.drop_lowest) and cint(cat.drop_lowest) >= droppable:
            frappe.throw(
                _(
                    "{0} drops the lowest {1}, but has only {2} assessment(s) that can be "
                    "dropped. At least one must still count."
                ).format(cat.title, cint(cat.drop_lowest), droppable)
            )


def fill_codes(categories):
    """A blank code takes the slug of the title, kept unique in the section."""
    taken = {c.category_code for c in categories if c.category_code}
    for c in categories:
        if c.category_code:
            continue
        base = slug(c.title) or "category"
        code, n = base, 2
        while code in taken:
            code, n = f"{base}-{n}", n + 1
        c.category_code = code
        taken.add(code)


# --- reading a section --------------------------------------------------------


def section_categories(course_schedule):
    return frappe.get_all(
        "Scheduled Course Assess Category",
        filters={"parent": course_schedule, "parenttype": "Course Schedule"},
        fields=CATEGORY_FIELDS,
        order_by="idx asc",
    )


def section_rows(course_schedule):
    return frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": course_schedule, "parenttype": "Course Schedule"},
        fields=ROW_FIELDS,
        order_by="idx asc",
    )


def student_rows(criteria, cards):
    """Criteria rows joined with one student's cards (``{criteria name: card}``)."""
    out = []
    for c in criteria:
        card = cards.get(c["name"]) or {}
        out.append(
            {
                **c,
                "excused": cint(card.get("excused")),
                "graded": cint(card.get("graded_card")),
                "score": flt(card.get("rawscore_card")),
            }
        )
    return out


def for_rosters(course_schedule, rosters, final=False):
    """``{roster name: compute(...)}`` for several students of one section."""
    if not rosters:
        return {}
    categories = section_categories(course_schedule)
    criteria = section_rows(course_schedule)
    cards = {}
    for c in frappe.get_all(
        "Course Assess Results Detail",
        filters={"parent": ("in", list(rosters))},
        fields=[
            "parent",
            "assessment_criteria",
            "rawscore_card",
            "graded_card",
            "excused",
        ],
    ):
        cards.setdefault(c.parent, {})[c.assessment_criteria] = c
    return {
        roster: compute(
            student_rows(criteria, cards.get(roster, {})), categories, final
        )
        for roster in rosters
    }


# --- writing the cards --------------------------------------------------------


def apply_to_roster_doc(csr, final=True):
    """Set ``maximum_score`` and ``dropped_card`` on a loaded roster's cards in
    memory, for ``_grade_thisstudent`` to score and save."""
    categories = section_categories(csr.course_sc)
    criteria = section_rows(csr.course_sc)
    cards = {row.assessment_criteria: row for row in csr.stdroster_grade}
    weights = compute(student_rows(criteria, cards), categories, final)
    for name, row in cards.items():
        w = weights.get(name)
        if not w:
            continue
        row.maximum_score = flt(w["weight"], 4)
        row.dropped_card = 1 if w["status"] == DROPPED else 0


def _write(course_schedule, rosters):
    """Rewrite the card weights of these active rosters from the live rules,
    touching only the cards whose weight or drop changed."""
    if not rosters:
        return
    weights = for_rosters(course_schedule, rosters)
    for card in frappe.get_all(
        "Course Assess Results Detail",
        filters={"parent": ("in", list(rosters))},
        fields=[
            "name",
            "parent",
            "assessment_criteria",
            "maximum_score",
            "dropped_card",
        ],
    ):
        w = (weights.get(card.parent) or {}).get(card.assessment_criteria)
        if not w:
            continue
        values = {
            "maximum_score": flt(w["weight"], 4),
            "dropped_card": 1 if w["status"] == DROPPED else 0,
        }
        if (
            abs(flt(card.maximum_score) - values["maximum_score"]) > 0.00005
            or cint(card.dropped_card) != values["dropped_card"]
        ):
            frappe.db.set_value(
                "Course Assess Results Detail", card.name, values, update_modified=False
            )


def _skip():
    return (
        frappe.flags.in_install
        or frappe.flags.in_migrate
        or frappe.flags.seminary_grading
        or frappe.flags.seminary_weights_batch
    )


def refresh_roster(roster):
    """One student's card weights. Skips a roster whose grades were sent: Send
    Grades froze its weights."""
    if _skip():
        return
    info = frappe.db.get_value(
        "Scheduled Course Roster", roster, ["course_sc", "active"], as_dict=True
    )
    if info and info.active:
        _write(info.course_sc, [roster])


def refresh_section(course_schedule):
    if _skip():
        return
    _write(
        course_schedule,
        frappe.get_all(
            "Scheduled Course Roster",
            filters={"course_sc": course_schedule, "active": 1},
            pluck="name",
        ),
    )


# --- doc events ---------------------------------------------------------------

CARD_FIELDS = ("rawscore_card", "graded_card", "excused")
ROW_WEIGHT_FIELDS = ("weight_scac", "extracredit_scac", "category_code", "never_drop")


def on_card_update(doc, method=None):
    """Course Assess Results Detail on_update: a new score can change which
    score is lowest."""
    if doc.parenttype != "Scheduled Course Roster" or not doc.parent:
        return
    if doc.is_new() or any(doc.has_value_changed(f) for f in CARD_FIELDS):
        refresh_roster(doc.parent)


def on_roster_update(doc, method=None):
    """Scheduled Course Roster on_update: the gradebook saves cards through the
    roster, and a parent save writes back the weights it loaded."""
    refresh_roster(doc.name)


def on_row_update(doc, method=None):
    """Scheduled Course Assess Criteria on_update, after ``update_card`` has
    copied the row's own weight onto every card: that copy is only right in a
    section with no categories and no excuses."""
    if doc.parenttype == "Course Schedule" and doc.parent:
        refresh_section(doc.parent)


def on_section_update(doc):
    """Called from Course Schedule.on_update: categories added, changed or
    removed."""
    refresh_section(doc.name)


# --- endpoints ----------------------------------------------------------------


def _require_staff(course_schedule):
    from seminary.seminary.guards import require_course_staff

    require_course_staff(course_schedule, include_registrar=True)


@frappe.whitelist()
def get_categories(course):
    """The section's categories and each row's share of the final grade, for
    the assessment page."""
    _require_staff(course)
    categories = section_categories(course)
    rows = section_rows(course)
    return {
        "categories": categories,
        "shares": nominal(rows, categories),
    }


@frappe.whitelist()
def set_excused(card=None, excused=1, reason=None, course_assess=None, student=None):
    """Excuse one student from one assessment, or take the excuse back. Course
    staff and the registrar; never once grades are sent. The card is named,
    or found from the assessment and the student (the attendance page)."""
    if not card and course_assess and student:
        card = frappe.db.get_value(
            "Course Assess Results Detail",
            {"assessment_criteria": course_assess, "student_card": student},
            "name",
        )
    row = (
        frappe.db.get_value(
            "Course Assess Results Detail",
            card,
            ["name", "parent", "extracredit_card"],
            as_dict=True,
        )
        if card
        else None
    )
    roster = (
        frappe.db.get_value(
            "Scheduled Course Roster", row.parent, ["course_sc", "active"], as_dict=True
        )
        if row
        else None
    )
    _require_staff(roster.course_sc if roster else None)
    if not roster:
        frappe.throw(_("That grade no longer exists."))
    if not roster.active:
        frappe.throw(
            _(
                "Grades for this student were already sent, so this can no longer change."
            )
        )
    if row.extracredit_card:
        frappe.throw(_("Extra credit cannot be excused: it only ever adds to a grade."))
    excused = cint(excused)
    reason = (reason or "").strip()
    if excused and not reason:
        frappe.throw(_("Give a reason for excusing the student."))
    frappe.db.set_value(
        "Course Assess Results Detail",
        card,
        {"excused": excused, "excused_reason": reason if excused else None},
    )
    refresh_roster(row.parent)
    return frappe.db.get_value(
        "Course Assess Results Detail",
        card,
        ["excused", "excused_reason", "maximum_score", "dropped_card"],
        as_dict=True,
    )
