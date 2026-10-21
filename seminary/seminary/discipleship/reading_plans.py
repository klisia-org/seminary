"""Reading plans for cohorts (ADR 087).

A Reading Plan is content with no dates. A Cohort Reading Plan is one cohort
running it on the weekdays it chose; every step's date is computed from the
start date and those days, never stored. Members mark steps as read (Reading
Plan Progress), leaders see who is behind, and a daily job writes once to a
member on the day they fall behind.

Portal reads and writes go through the whitelisted functions at the bottom,
which check cohort membership or leadership themselves and then write with
ignore_permissions -- the same posture as the rest of the community API.
"""

from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime, today

from seminary.seminary.discipleship.api import _assert_not_archived, _require_leader
from seminary.seminary.discipleship.feed_api import _is_member, _is_staff, _my_person
from seminary.seminary.discipleship.permissions import (
    _in_clause,
    _should_restrict,
    led_cohorts,
    visible_cohorts,
)
from seminary.seminary.integrations.bible_books import BOOK_NAMES, verse_ordinal
from seminary.seminary.person import find_person

# Index = date.weekday().
WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
BIBLE_FIELDS = (
    "from_book",
    "from_chapter",
    "from_verse",
    "to_book",
    "to_chapter",
    "to_verse",
)
OTHER_FIELDS = ("reading_text", "attachment", "link_url")
# What a step reads. Locked once a cohort has started the plan; `message` is not
# in it, so a leader can keep writing questions while the cohort reads.
LOCKED_STEP_FIELDS = BIBLE_FIELDS + OTHER_FIELDS
INT_FIELDS = {"from_chapter", "from_verse", "to_chapter", "to_verse"}
MAX_STEPS = 400
# A schedule never looks further ahead than this, whatever the days say.
MAX_SCHEDULE_DAYS = 3660


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #
def book_name(osis):
    return _(BOOK_NAMES.get(osis, osis))


def format_reference(fb, fc, fv, tb, tc, tv, name=book_name):
    """'Romans 3', 'Romans 3:21–26', 'Romans 1–2', 'Romans 1:18–3:20',
    'Philemon 1 – Hebrews 2'. An empty verse is a chapter boundary."""
    left = f"{name(fb)} {fc}" + (f":{fv}" if fv else "")
    if tb == fb and tc == fc:
        if fv and tv:
            return left if tv == fv else f"{left}–{tv}"
        if tv:
            return f"{left}:1–{tv}"
        if fv:
            return _("{0} to the end of the chapter").format(left)
        return left
    right = f"{tc}" + (f":{tv}" if tv else "")
    if tb == fb:
        return f"{left}–{right}"
    return f"{left} – {name(tb)} {right}"


def _bible_step(row):
    fb = row.from_book
    fc = cint(row.from_chapter)
    if not fb or fc < 1:
        frappe.throw(
            _("Step {0}: choose the book and chapter to start from.").format(row.step)
        )
    tb = row.to_book or fb
    tc = cint(row.to_chapter) or (fc if tb == fb else 0)
    if tc < 1:
        frappe.throw(_("Step {0}: choose the chapter to end at.").format(row.step))
    fv = cint(row.from_verse) or None
    tv = cint(row.to_verse) or None
    for value in (fc, tc, fv, tv):
        if value is not None and not 0 < value < 1000:
            frappe.throw(
                _("Step {0}: chapters and verses run from 1 to 999.").format(row.step)
            )
    start = verse_ordinal(fb, fc, fv or 0)
    end = verse_ordinal(tb, tc, tv or 999)
    if end < start:
        frappe.throw(_("Step {0} ends before it starts.").format(row.step))

    start_id = f"{fb}.{fc}" + (f".{fv}" if fv else "")
    end_id = f"{tb}.{tc}" + (f".{tv}" if tv else "")
    row.update(
        {
            "to_book": tb,
            "to_chapter": tc,
            "from_verse": fv,
            "to_verse": tv,
            "verse_start_ord": start,
            "verse_end_ord": end,
            "resolved_ref": start_id if start_id == end_id else f"{start_id}-{end_id}",
            # Stored in the canonical (English) names for Desk lists; the portal
            # renders its own label in the reader's language.
            "reference": format_reference(
                fb, fc, fv, tb, tc, tv, name=lambda o: BOOK_NAMES.get(o, o)
            ),
        }
    )
    for field in OTHER_FIELDS:
        row.set(field, None)


def _other_label(row):
    if row.reading_text:
        first = row.reading_text.strip().splitlines()[0]
        return first if len(first) <= 120 else first[:117] + "…"
    if row.attachment:
        return row.attachment.rsplit("/", 1)[-1].split("?", 1)[0]
    return urlparse(row.link_url).netloc or row.link_url


def _other_step(row):
    from seminary.seminary.url_policy import require_safe_url

    row.reading_text = (row.reading_text or "").strip() or None
    row.link_url = (row.link_url or "").strip() or None
    if not (row.reading_text or row.attachment or row.link_url):
        frappe.throw(
            _(
                "Step {0}: add something to read — a text, an attachment or a link."
            ).format(row.step)
        )
    if row.link_url:
        require_safe_url(row.link_url, _("Step {0} link").format(row.step))
    row.reference = _other_label(row)
    for field in BIBLE_FIELDS + ("resolved_ref", "verse_start_ord", "verse_end_ord"):
        row.set(field, None)


def _step_signature(row):
    return tuple(
        cint(row.get(f)) if f in INT_FIELDS else (row.get(f) or "")
        for f in LOCKED_STEP_FIELDS
    )


def plan_in_use(plan):
    return bool(frappe.db.exists("Cohort Reading Plan", {"reading_plan": plan}))


def validate_plan(doc):
    from seminary.seminary.content_safety import clean_rich

    if (
        doc.is_standard
        and not doc.flags.allow_standard_edit
        and (
            doc.is_new() or frappe.db.get_value("Reading Plan", doc.name, "is_standard")
        )
    ):
        frappe.throw(
            _("A standard reading plan cannot be changed. Duplicate it instead.")
        )
    if not doc.author and doc.is_new():
        doc.author = find_person(user=frappe.session.user)
    if len(doc.steps) > MAX_STEPS:
        frappe.throw(_("A reading plan can have at most {0} steps.").format(MAX_STEPS))

    for i, row in enumerate(doc.steps, start=1):
        row.idx = row.step = i
        if doc.plan_type == "Bible":
            _bible_step(row)
        else:
            _other_step(row)
        # Child rows do not get the wildcard `before_validate` sanitiser.
        if row.message:
            row.message = clean_rich(row.message)

    _guard_step_attachments(doc)

    if not doc.is_new() and plan_in_use(doc.name):
        before = doc.get_doc_before_save()
        if before and (
            before.plan_type != doc.plan_type
            or [_step_signature(r) for r in before.steps]
            != [_step_signature(r) for r in doc.steps]
        ):
            frappe.throw(
                _(
                    "A cohort has started this plan, so its readings can no longer "
                    "change. You can still edit the messages, or duplicate the plan "
                    "to change the readings."
                )
            )


def _guard_step_attachments(doc):
    """The Attach guard in file_policy only walks the parent's fields, so the
    same rule is applied to step rows here: you may name a file you can already
    read, and no other."""
    from seminary.seminary.file_policy import _may_adopt, _rows_for
    from seminary.storage.backend import normalize_file_url

    if frappe.session.user == "Administrator" or frappe.flags.in_install:
        return
    before = (
        {}
        if doc.is_new()
        else {
            r.name: r.attachment
            for r in (doc.get_doc_before_save() or frappe._dict(steps=[])).steps
        }
    )
    for row in doc.steps:
        if not row.attachment or before.get(row.name) == row.attachment:
            continue
        rows = _rows_for(normalize_file_url(row.attachment))
        if rows and not _may_adopt(rows, doc.flags.attachment_source):
            frappe.throw(
                _("You cannot attach a file you do not have access to."),
                frappe.PermissionError,
            )


def adopt_step_attachments(doc):
    """Attach each step's file to the plan, so whoever may read the plan may
    open it (file_policy reads private files through their host)."""
    from seminary.seminary.file_policy import adopt

    for row in doc.steps:
        if row.attachment:
            adopt(
                row.attachment,
                ("Reading Plan", doc.name),
                source_host=doc.flags.attachment_source,
            )


def guard_plan_delete(doc):
    if doc.is_standard and not doc.flags.allow_standard_edit:
        frappe.throw(_("A standard reading plan cannot be deleted."))
    if plan_in_use(doc.name):
        frappe.throw(_("A cohort has used this plan, so it cannot be deleted."))


# --------------------------------------------------------------------------- #
# Schedule
# --------------------------------------------------------------------------- #
def validate_run(doc):
    if not any(cint(doc.get(f)) for f in WEEKDAYS):
        frappe.throw(_("Choose at least one reading day."))
    if not frappe.db.count(
        "Reading Plan Step", {"parent": doc.reading_plan, "parenttype": "Reading Plan"}
    ):
        frappe.throw(_("This reading plan has no steps yet."))
    if doc.is_new():
        if not doc.started_by:
            doc.started_by = find_person(user=frappe.session.user)
    else:
        for field in ("cohort", "reading_plan"):
            if doc.has_value_changed(field):
                frappe.throw(
                    _("Start a new run to read another plan or with another cohort.")
                )


def delete_run_progress(doc):
    frappe.db.delete("Reading Plan Progress", {"cohort_reading_plan": doc.name})


class _Holidays:
    """Public holidays of the site's country, one calendar per year."""

    def __init__(self):
        from seminary.seminary.utils import country_code

        self.code = country_code(frappe.db.get_default("country"))
        self.years = {}

    def __contains__(self, d):
        if not self.code:
            return False
        if d.year not in self.years:
            from seminary.seminary.holidays import _calendar

            self.years[d.year] = _calendar(self.code, d.year)
        cal = self.years[d.year]
        return cal is not None and d in cal


def step_dates(run, count):
    """The date of each of `count` steps: the first reading day on or after the
    start date, then each next reading day, skipping public holidays when asked."""
    days = {i for i, f in enumerate(WEEKDAYS) if cint(run.get(f))}
    if not days or not run.get("start_date"):
        return []
    holidays = _Holidays() if cint(run.get("skip_public_holidays")) else ()
    d, out = getdate(run.start_date), []
    for _i in range(MAX_SCHEDULE_DAYS):
        if len(out) >= count:
            break
        if d.weekday() in days and d not in holidays:
            out.append(d)
        d = add_days(d, 1)
    return out


def _plan_steps(plan):
    return frappe.get_all(
        "Reading Plan Step",
        filters={"parent": plan, "parenttype": "Reading Plan"},
        fields=[
            "step",
            "reference",
            "from_book",
            "from_chapter",
            "from_verse",
            "to_book",
            "to_chapter",
            "to_verse",
            "resolved_ref",
            "reading_text",
            "attachment",
            "link_url",
            "message",
        ],
        order_by="idx asc",
    )


def _step_label(step, plan_type):
    if plan_type == "Bible" and step.from_book:
        return format_reference(
            step.from_book,
            step.from_chapter,
            step.from_verse or None,
            step.to_book or step.from_book,
            step.to_chapter or step.from_chapter,
            step.to_verse or None,
        )
    return step.reference


def _reads(run):
    """{person: {step: read_on}} for a run."""
    out = {}
    for r in frappe.get_all(
        "Reading Plan Progress",
        filters={"cohort_reading_plan": run},
        fields=["person", "step", "read_on"],
    ):
        out.setdefault(r.person, {})[r.step] = r.read_on
    return out


def _members(cohort):
    return frappe.get_all(
        "Cohort Membership",
        filters={"cohort": cohort, "active": 1},
        fields=["person", "role", "is_leader"],
        order_by="is_leader desc, role asc",
    )


def _behind(dates, read, on=None):
    """Steps whose date has passed (before `on`, default today) and are unread."""
    on = getdate(on or today())
    return [i for i, d in enumerate(dates, start=1) if d < on and i not in read]


# --------------------------------------------------------------------------- #
# Who may do what
# --------------------------------------------------------------------------- #
def _leads_any(user=None):
    return bool(led_cohorts(user))


def _require_author_role():
    """Staff, or the active leader of a live cohort (ADR 087 §3)."""
    if _is_staff() or _leads_any():
        return
    frappe.throw(
        _("Only cohort leaders can write reading plans."), frappe.PermissionError
    )


def _can_edit_plan(plan_doc):
    if plan_doc.is_standard:
        return False
    if _is_staff():
        return True
    me = find_person(user=frappe.session.user)
    return bool(me and plan_doc.author == me and _leads_any())


def plans_visible_to(user=None):
    """None means every plan; otherwise the set of plan names."""
    user = user or frappe.session.user
    if not _should_restrict(user) or _leads_any(user):
        return None
    cohorts = visible_cohorts(user)
    if not cohorts:
        return set()
    return set(
        frappe.get_all(
            "Cohort Reading Plan",
            filters={"cohort": ["in", list(cohorts)]},
            pluck="reading_plan",
        )
    )


def _require_plan_visible(plan):
    if not frappe.db.exists("Reading Plan", plan):
        frappe.throw(_("Reading plan not found."), frappe.DoesNotExistError)
    visible = plans_visible_to()
    if visible is not None and plan not in visible:
        frappe.throw(_("You cannot see this reading plan."), frappe.PermissionError)


def _require_run_member(run_doc):
    """A member of the run's cohort (or someone who sees it as a leader up the
    tree, or staff). Returns the caller's Person."""
    person = find_person(user=frappe.session.user)
    if _is_staff() or run_doc.cohort in visible_cohorts():
        return person
    frappe.throw(_("You are not in this cohort."), frappe.PermissionError)


# --- permission hooks (hooks.py) -------------------------------------------
def plan_query(user=None):
    visible = plans_visible_to(user)
    if visible is None:
        return ""
    return _in_clause("Reading Plan", "name", visible) if visible else "1=0"


def plan_has(doc, ptype=None, user=None):
    if ptype not in (None, "read", "print"):
        return not _should_restrict(user or frappe.session.user)
    visible = plans_visible_to(user)
    return visible is None or doc.name in visible


def run_query(user=None):
    if not _should_restrict(user):
        return ""
    names = visible_cohorts(user)
    return _in_clause("Cohort Reading Plan", "cohort", names) if names else "1=0"


def run_has(doc, ptype=None, user=None):
    if not _should_restrict(user):
        return True
    return ptype in (None, "read", "print") and doc.cohort in visible_cohorts(user)


def progress_query(user=None):
    if not _should_restrict(user):
        return ""
    user = user or frappe.session.user
    clauses = []
    person = find_person(user=user)
    if person:
        clauses.append(
            f"(`tabReading Plan Progress`.`person` = {frappe.db.escape(person)})"
        )
    led = led_cohorts(user)
    if led:
        runs = frappe.get_all(
            "Cohort Reading Plan", filters={"cohort": ["in", list(led)]}, pluck="name"
        )
        if runs:
            clauses.append(
                _in_clause("Reading Plan Progress", "cohort_reading_plan", runs)
            )
    return "(" + " OR ".join(clauses) + ")" if clauses else "1=0"


def progress_has(doc, ptype=None, user=None):
    if not _should_restrict(user):
        return True
    if ptype not in (None, "read", "print"):
        return False
    user = user or frappe.session.user
    if doc.person and doc.person == find_person(user=user):
        return True
    cohort = frappe.db.get_value(
        "Cohort Reading Plan", doc.cohort_reading_plan, "cohort"
    )
    return cohort in led_cohorts(user)


# --------------------------------------------------------------------------- #
# Library (plans)
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def bible_books():
    from seminary.seminary.integrations.bible_books import BOOK_ORDER

    return [
        {"osis": o, "name": book_name(o)}
        for o in sorted(BOOK_ORDER, key=BOOK_ORDER.get)
    ]


@frappe.whitelist()
def list_plans():
    """Every plan, for leaders and staff choosing one to read or to edit."""
    _require_author_role()
    plans = frappe.get_all(
        "Reading Plan",
        fields=["name", "title", "plan_type", "description", "is_standard", "author"],
        order_by="is_standard desc, title asc",
    )
    counts = dict(
        frappe.db.sql(
            """select parent, count(*) from `tabReading Plan Step`
            where parenttype = 'Reading Plan' group by parent"""
        )
    )
    used = set(
        frappe.get_all("Cohort Reading Plan", pluck="reading_plan", distinct=True)
    )
    me = find_person(user=frappe.session.user)
    staff = _is_staff()
    names = _person_names({p.author for p in plans if p.author})
    for p in plans:
        p.step_count = counts.get(p.name, 0)
        p.in_use = p.name in used
        p.author_name = names.get(p.author)
        p.can_edit = not p.is_standard and (staff or (me and p.author == me))
        p.can_delete = p.can_edit and not p.in_use
    return plans


def _person_names(persons):
    if not persons:
        return {}
    return dict(
        frappe.get_all(
            "Person",
            filters={"name": ["in", list(persons)]},
            fields=["name", "full_name"],
            as_list=True,
        )
    )


@frappe.whitelist()
def get_plan(plan):
    _require_plan_visible(plan)
    doc = frappe.get_doc("Reading Plan", plan)
    steps = _plan_steps(plan)
    for s in steps:
        s.label = _step_label(s, doc.plan_type)
    in_use = plan_in_use(plan)
    return {
        "name": doc.name,
        "title": doc.title,
        "plan_type": doc.plan_type,
        "description": doc.description,
        "is_standard": doc.is_standard,
        "author": doc.author,
        "author_name": (
            _person_names({doc.author}).get(doc.author) if doc.author else None
        ),
        "in_use": in_use,
        "can_edit": _can_edit_plan(doc),
        "steps": steps,
    }


def _clean_steps(steps):
    allowed = set(LOCKED_STEP_FIELDS) | {"message"}
    out = []
    for s in frappe.parse_json(steps) if isinstance(steps, str) else (steps or []):
        out.append({k: v for k, v in (s or {}).items() if k in allowed})
    return out


@frappe.whitelist()
def save_plan(title, plan_type="Bible", description=None, steps=None, plan=None):
    """Create a plan, or update one the caller wrote. Once a cohort has started a
    plan only the step messages may change; the controller enforces it."""
    _require_author_role()
    if plan:
        doc = frappe.get_doc("Reading Plan", plan)
        if not _can_edit_plan(doc):
            frappe.throw(
                _("Only the author or staff can edit this plan."),
                frappe.PermissionError,
            )
    else:
        doc = frappe.new_doc("Reading Plan")
        doc.author = find_person(user=frappe.session.user)
    doc.title = (title or "").strip()
    doc.plan_type = plan_type
    doc.description = description
    rows = _clean_steps(steps)
    # Keep existing rows (and their names) in place, so an unchanged step is
    # recognisably the same step.
    existing = list(doc.steps)
    doc.set("steps", [])
    for i, values in enumerate(rows):
        if i < len(existing):
            row = existing[i]
            for field in LOCKED_STEP_FIELDS + ("message",):
                row.set(field, values.get(field))
            doc.append("steps", row)
        else:
            doc.append("steps", values)
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def duplicate_plan(plan):
    _require_author_role()
    _require_plan_visible(plan)
    src = frappe.get_doc("Reading Plan", plan)
    doc = frappe.new_doc("Reading Plan")
    doc.update(
        {
            "title": _unique_title(_("{0} (copy)").format(src.title)),
            "plan_type": src.plan_type,
            "description": src.description,
            "author": find_person(user=frappe.session.user),
        }
    )
    for row in src.steps:
        doc.append("steps", {f: row.get(f) for f in LOCKED_STEP_FIELDS + ("message",)})
    doc.flags.attachment_source = ("Reading Plan", src.name)
    doc.insert(ignore_permissions=True)
    return doc.name


def _unique_title(title):
    title = (title or "").strip()[:130] or _("Reading plan")
    candidate, n = title, 2
    while frappe.db.exists("Reading Plan", {"title": candidate}):
        candidate = f"{title} ({n})"
        n += 1
    return candidate


@frappe.whitelist()
def delete_plan(plan):
    _require_author_role()
    doc = frappe.get_doc("Reading Plan", plan)
    if not _can_edit_plan(doc):
        frappe.throw(
            _("Only the author or staff can delete this plan."), frappe.PermissionError
        )
    doc.delete(ignore_permissions=True)


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #
def _apply_days(doc, days):
    days = frappe.parse_json(days) if isinstance(days, str) else days
    if days is None:
        return
    chosen = {d for d in days if d in WEEKDAYS}
    for f in WEEKDAYS:
        doc.set(f, 1 if f in chosen else 0)


@frappe.whitelist()
def start_plan(cohort, reading_plan, start_date, days=None, skip_public_holidays=0):
    _require_leader(cohort)
    _assert_not_archived(cohort)
    _require_plan_visible(reading_plan)
    doc = frappe.new_doc("Cohort Reading Plan")
    doc.update(
        {
            "cohort": cohort,
            "reading_plan": reading_plan,
            "start_date": getdate(start_date),
            "skip_public_holidays": cint(skip_public_holidays),
            "status": "Active",
        }
    )
    _apply_days(doc, days if days is not None else list(WEEKDAYS))
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def update_run(run, start_date=None, days=None, skip_public_holidays=None, status=None):
    doc = frappe.get_doc("Cohort Reading Plan", run)
    _require_leader(doc.cohort)
    if start_date:
        doc.start_date = getdate(start_date)
    _apply_days(doc, days)
    if skip_public_holidays is not None:
        doc.skip_public_holidays = cint(skip_public_holidays)
    if status:
        if status not in ("Active", "Completed", "Cancelled"):
            frappe.throw(_("Unknown status."))
        doc.status = status
    doc.save(ignore_permissions=True)
    return doc.name


def _run_view(run, person, plan_cache):
    plan = plan_cache.get(run.reading_plan)
    if plan is None:
        plan = plan_cache[run.reading_plan] = {
            "plan_type": frappe.db.get_value(
                "Reading Plan", run.reading_plan, "plan_type"
            ),
            "steps": _plan_steps(run.reading_plan),
        }
    dates = step_dates(run, len(plan["steps"]))
    read = _reads(run.name).get(person, {}) if person else {}
    now = getdate(today())
    steps = []
    for i, s in enumerate(plan["steps"], start=1):
        d = dates[i - 1] if i <= len(dates) else None
        steps.append(
            {
                "step": i,
                "label": _step_label(s, plan["plan_type"]),
                "resolved_ref": s.resolved_ref,
                "reading_text": s.reading_text,
                "attachment": s.attachment,
                "link_url": s.link_url,
                "message": s.message,
                "date": d,
                "is_today": d == now,
                "read": i in read,
                "read_on": read.get(i),
            }
        )
    current = next((s["step"] for s in steps if s["date"] and s["date"] >= now), None)
    return {
        "name": run.name,
        "cohort": run.cohort,
        "cohort_name": frappe.db.get_value("Cohort", run.cohort, "cohort_name"),
        "reading_plan": run.reading_plan,
        "title": run.plan_title,
        "plan_type": plan["plan_type"],
        "status": run.status,
        "start_date": run.start_date,
        "days": [f for f in WEEKDAYS if cint(run.get(f))],
        "skip_public_holidays": cint(run.skip_public_holidays),
        "can_manage": _is_staff() or run.cohort in led_cohorts(),
        "is_member": bool(person and _is_member(run.cohort, person)),
        "current_step": current,
        "behind": len(_behind(dates, read)) if person else 0,
        "read_count": len(read),
        "steps": steps,
    }


_RUN_FIELDS = [
    "name",
    "cohort",
    "reading_plan",
    "plan_title",
    "status",
    "start_date",
    "skip_public_holidays",
    *WEEKDAYS,
]


@frappe.whitelist()
def my_reading_plans(cohort=None, include_cancelled=0):
    """The runs of my cohorts (or of one cohort), with my own marks."""
    person = find_person(user=frappe.session.user)
    if cohort:
        if not (_is_staff() or cohort in visible_cohorts()):
            frappe.throw(_("You are not in this cohort."), frappe.PermissionError)
        cohorts = [cohort]
    else:
        cohorts = list(visible_cohorts())
    if not cohorts:
        return []
    filters = {"cohort": ["in", cohorts]}
    if not cint(include_cancelled):
        filters["status"] = ["!=", "Cancelled"]
    runs = frappe.get_all(
        "Cohort Reading Plan",
        filters=filters,
        fields=_RUN_FIELDS,
        order_by="start_date desc",
    )
    order = {"Active": 0, "Completed": 1, "Cancelled": 2}
    runs.sort(key=lambda r: order.get(r.status, 3))
    cache = {}
    return [_run_view(r, person, cache) for r in runs]


@frappe.whitelist()
def get_run(run):
    doc = frappe.get_doc("Cohort Reading Plan", run)
    person = _require_run_member(doc)
    row = frappe.get_all(
        "Cohort Reading Plan", filters={"name": run}, fields=_RUN_FIELDS
    )[0]
    return _run_view(row, person, {})


@frappe.whitelist()
def mark_step(run, step, read=1):
    doc = frappe.get_doc("Cohort Reading Plan", run)
    person = _my_person()
    if not _is_member(doc.cohort, person):
        frappe.throw(
            _("Only members of this cohort can mark steps."), frappe.PermissionError
        )
    if doc.status == "Cancelled":
        frappe.throw(_("This reading plan was cancelled."))
    step = cint(step)
    count = frappe.db.count(
        "Reading Plan Step", {"parent": doc.reading_plan, "parenttype": "Reading Plan"}
    )
    if not 1 <= step <= count:
        frappe.throw(_("There is no step {0} in this plan.").format(step))
    key = {"cohort_reading_plan": run, "person": person, "step": step}
    existing = frappe.db.get_value("Reading Plan Progress", key)
    if cint(read) and not existing:
        frappe.get_doc(
            {"doctype": "Reading Plan Progress", **key, "read_on": now_datetime()}
        ).insert(ignore_permissions=True)
    elif not cint(read) and existing:
        frappe.delete_doc("Reading Plan Progress", existing, ignore_permissions=True)
    return {"step": step, "read": bool(cint(read))}


@frappe.whitelist()
def run_progress(run):
    """The leader's grid: every active member against every step."""
    doc = frappe.get_doc("Cohort Reading Plan", run)
    _require_leader(doc.cohort)
    count = frappe.db.count(
        "Reading Plan Step", {"parent": doc.reading_plan, "parenttype": "Reading Plan"}
    )
    dates = step_dates(doc, count)
    reads = _reads(run)
    members = _members(doc.cohort)
    names = _person_names({m.person for m in members})
    rows = []
    for m in members:
        read = reads.get(m.person, {})
        behind = _behind(dates, read)
        rows.append(
            {
                "person": m.person,
                "full_name": names.get(m.person) or m.person,
                "role": m.role,
                "is_leader": m.is_leader,
                "read": sorted(read),
                "behind": len(behind),
                "last_read_on": max(read.values()) if read else None,
            }
        )
    rows.sort(key=lambda r: (-r["behind"], r["full_name"]))
    return {
        "steps": [{"step": i, "date": d} for i, d in enumerate(dates, start=1)],
        "members": rows,
    }


@frappe.whitelist()
def discussion_draft(run, step):
    """What the composer opens with when a member discusses a step (ADR 087 §9).
    Nothing is posted here; the member edits and publishes."""
    doc = frappe.get_doc("Cohort Reading Plan", run)
    _require_run_member(doc)
    step = cint(step)
    steps = _plan_steps(doc.reading_plan)
    if not 1 <= step <= len(steps):
        frappe.throw(_("There is no step {0} in this plan.").format(step))
    s = steps[step - 1]
    plan_type = frappe.db.get_value("Reading Plan", doc.reading_plan, "plan_type")
    label = _step_label(s, plan_type)
    scripture = []
    if plan_type == "Bible" and s.resolved_ref:
        scripture = _scripture_tags(s)
    return {
        "cohort": doc.cohort,
        "title": _("{0} · Step {1}: {2}").format(doc.plan_title, step, label),
        "content": s.message or "",
        "scripture": scripture,
        "reference_doctype": "Cohort Reading Plan",
        "reference_name": doc.name,
    }


def _scripture_tags(s):
    """References the post's scripture parser reads back to (at least) the step's
    passage. It takes one book and one verse range per segment, and reads
    'Romans 1-2' as chapter 1 only, so whole chapters go one segment each."""
    fb, fc, fv = s.from_book, cint(s.from_chapter), cint(s.from_verse)
    tb, tc, tv = s.to_book or fb, cint(s.to_chapter) or fc, cint(s.to_verse)
    name = BOOK_NAMES.get(fb, fb)
    if tb != fb:
        tc = fc  # one book per segment: tag where the reading starts
        tv = 0
    if fv and tv:
        return [f"{name} {fc}:{fv}-{tc}:{tv}" if tc != fc else f"{name} {fc}:{fv}-{tv}"]
    return [f"{name} {c}" for c in range(fc, tc + 1)][:30]


# --------------------------------------------------------------------------- #
# Daily: reminders and completion
# --------------------------------------------------------------------------- #
def daily():
    send_behind_reminders()
    complete_finished_runs()


def send_behind_reminders(on=None):
    """ADR 087 §8: write to a member on the day after a step's date when they
    have not read it and had read every step before it -- the moment they fall
    behind. Someone already behind is not written to again."""
    yesterday = getdate(add_days(on or today(), -1))
    sent = 0
    for run in frappe.get_all(
        "Cohort Reading Plan", filters={"status": "Active"}, fields=_RUN_FIELDS
    ):
        count = frappe.db.count(
            "Reading Plan Step",
            {"parent": run.reading_plan, "parenttype": "Reading Plan"},
        )
        dates = step_dates(run, count)
        if yesterday not in dates:
            continue
        step = dates.index(yesterday) + 1
        reads = _reads(run.name)
        for m in _members(run.cohort):
            read = reads.get(m.person, {})
            if step in read or any(i not in read for i in range(1, step)):
                continue
            try:
                _notify_behind(run, m.person, step, _behind(dates, read, on=on))
                sent += 1
            except Exception:  # noqa: BLE001 -- one bad address must not stop the rest
                frappe.log_error(frappe.get_traceback(), "reading plan reminder failed")
    return sent


def _notify_behind(run, person, step, unread):
    from seminary.seminary import comms

    person_doc = frappe.get_doc("Person", person)
    cohort_name = frappe.db.get_value("Cohort", run.cohort, "cohort_name") or run.cohort
    url = frappe.utils.get_url(f"/seminary/reading-plans?run={run.name}")
    subject = _("Catch up on {0}").format(run.plan_title)
    message = _(
        "You have {0} unread step(s) in <b>{1}</b> with {2}: {3}. "
        '<a href="{4}">Open the plan</a>.'
    ).format(
        len(unread),
        frappe.utils.escape_html(run.plan_title),
        frappe.utils.escape_html(cohort_name),
        ", ".join(str(i) for i in unread),
        url,
    )
    common = {
        "subject": subject,
        "message": message,
        "person": person_doc.name,
        "category": "Community",
        "reference_doctype": "Cohort Reading Plan",
        "reference_name": run.name,
    }
    if person_doc.user:
        comms.send_message(
            channel="In-App",
            dedupe_key=f"rp-behind-{run.name}-{person}-{step}-app",
            **common,
        )
    if person_doc.primary_email:
        comms.send_message(
            channel="Email",
            to_address=person_doc.primary_email,
            dedupe_key=f"rp-behind-{run.name}-{person}-{step}-email",
            **common,
        )


def complete_finished_runs(on=None):
    """A run is Completed once the reminder for its last step has gone out."""
    yesterday = getdate(add_days(on or today(), -1))
    for run in frappe.get_all(
        "Cohort Reading Plan", filters={"status": "Active"}, fields=_RUN_FIELDS
    ):
        count = frappe.db.count(
            "Reading Plan Step",
            {"parent": run.reading_plan, "parenttype": "Reading Plan"},
        )
        dates = step_dates(run, count)
        if dates and len(dates) == count and dates[-1] <= yesterday:
            frappe.db.set_value("Cohort Reading Plan", run.name, "status", "Completed")
