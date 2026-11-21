# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Group meetings for oral activities (decisions/100d-a).

A Conversation or presentation captured from virtual meetings can give each
group its own meeting instead of using a class meeting everyone sees. The
instructor makes the groups (the section's student groups, or groups for this
activity only), gives the scheduling constraints, and Seminary proposes one
slot per group:

- hard limits: a member's other class or group meetings (038), free meeting
  accounts (051a, counted with class meetings) and, when the instructor
  attends, their own classes and the other slots;
- with the instructor not attending, the daily hours are read in each member's
  time zone (§9) and the slot with the least total time outside them is taken,
  with a note saying who is outside and by how much.

Each group meeting is an Oral Activity Meeting of kind *Group* with its own
date, times, link and members. Only its members see it (§6).
"""

import json
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.utils import (
    cint,
    get_datetime,
    get_system_timezone,
    get_time,
    getdate,
)

from seminary.seminary import oral_meetings
from seminary.seminary.time_zones import own_zone, zone_or_site

OAM = oral_meetings.OAM
ROW = "Course Schedule Meeting Dates"
STEP = timedelta(minutes=15)
MAX_DAYS = 62
LIVE = ["not in", ["Cancelled", "Failed"]]
# A member on a day the instructor did not allow counts as a full day out.
OFF_DAY = 24 * 60


# ------------------------------------------------------------------ helpers


def _staff(course, activity):
    oral_meetings._staff(course)
    scac = oral_meetings._scac(course, activity)
    act = oral_meetings._activity(activity)
    if act.capture != "Virtual meeting":
        frappe.throw(_("This activity is not captured from virtual meetings."))
    return scac, act


def _json(value, default):
    if isinstance(value, str):
        return json.loads(value or "null") or default
    return value or default


def _site_zone():
    return ZoneInfo(get_system_timezone())


def _in_zone(site_dt, tz):
    """A naive site-local datetime in another zone (naive)."""
    aware = site_dt.replace(tzinfo=_site_zone())
    return aware.astimezone(ZoneInfo(tz)).replace(tzinfo=None)


def _utc_iso(site_dt):
    return (
        site_dt.replace(tzinfo=_site_zone())
        .astimezone(ZoneInfo("UTC"))
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _from_utc(text):
    """A UTC ISO time from the portal, as a naive site-local datetime."""
    at = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    if not at.tzinfo:
        at = at.replace(tzinfo=ZoneInfo("UTC"))
    return at.astimezone(_site_zone()).replace(tzinfo=None)


def _slot_of(s):
    if s.get("start_utc") and s.get("end_utc"):
        return (_from_utc(s["start_utc"]), _from_utc(s["end_utc"]))
    if s.get("start") and s.get("end"):
        return (get_datetime(s["start"]), get_datetime(s["end"]))
    return None


def _hm(text):
    t = get_time(text)
    return t.hour * 60 + t.minute


def roster(course):
    """The section's active, non-audit students with their own time zones."""
    out = []
    for r in frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": course, "active": 1, "audit_bool": 0},
        fields=["student", "stuname_roster"],
        order_by="stuname_roster asc",
    ):
        user = frappe.db.get_value("Student", r.student, "user") if r.student else None
        if not user:
            continue
        tz = own_zone(user)
        out.append(
            {
                "student": r.student,
                "name": r.stuname_roster or r.student,
                "user": user,
                "time_zone": tz,
                "offset": _offset(tz),
            }
        )
    return out


def _offset(tz):
    if not tz:
        return None
    now = datetime.now(ZoneInfo(tz))
    return int(now.utcoffset().total_seconds() // 60)


def group_meetings(course, activity, include_cancelled=False):
    filters = {"course_schedule": course, "oral_activity": activity, "kind": "Group"}
    if not include_cancelled:
        filters["status"] = ["!=", "Cancelled"]
    rows = frappe.get_all(
        OAM,
        filters=filters,
        fields=[
            "name",
            "group_label",
            "meeting_date",
            "from_time",
            "to_time",
            "status",
            "error",
            "method",
            "link",
            "meeting_status",
            "meeting_error",
            "host_key",
            "schedule_note",
        ],
        order_by="meeting_date asc, from_time asc",
    )
    for r in rows:
        r["members"] = frappe.get_all(
            "Oral Activity Meeting Member",
            filters={"parent": r.name, "parenttype": OAM},
            fields=["student", "student_name", "time_zone"],
            order_by="idx asc",
        )
        r["from_time"], r["to_time"] = str(r.from_time or ""), str(r.to_time or "")
        if r.meeting_date and r.from_time and r.to_time:
            r["start_utc"] = _utc_iso(
                _interval(r.meeting_date, r.from_time, r.to_time)[0]
            )
            r["end_utc"] = _utc_iso(
                _interval(r.meeting_date, r.from_time, r.to_time)[1]
            )
    return rows


# ------------------------------------------------------------ configure page


@frappe.whitelist()
def configure_state(course, activity):
    _scac, act = _staff(course, activity)
    from seminary.seminary.oral_activities import _section_groups
    from seminary.seminary.school_meetings import providers

    people = roster(course)
    known = {p["student"] for p in people}
    groups = [
        {
            "label": frappe.db.get_value("Student Group", g, "group_name") or g,
            "students": [s for s in members if s in known],
        }
        for g, members in _section_groups(course).items()
    ]
    accounts = frappe.get_all(
        "Web Meeting Account",
        filters={"enabled": 1, "provider": ["in", list(providers()) or [""]]},
        pluck="name",
    )
    methods = []
    for name in oral_meetings.capture_methods():
        try:
            obj = oral_meetings.method(name)
        except Exception:
            frappe.log_error(title=f"Capture method {name} could not be loaded")
            continue
        methods.append(
            {
                "method": name,
                "label": _(oral_meetings.METHOD_LABELS.get(name, name)),
                "needs_managed": bool(getattr(obj, "needs_managed", False)),
            }
        )
    return {
        "title": act.title,
        "mode": act.mode,
        "students": people,
        "section_groups": [g for g in groups if g["students"]],
        "meetings": group_meetings(course, activity),
        "school_accounts": len(accounts),
        "methods": methods,
        "my_time_zone": zone_or_site(frappe.session.user),
        "site_time_zone": get_system_timezone(),
    }


@frappe.whitelist()
def propose_groups(course, activity, size, keep_zones=1):
    """Groups of ``size`` from the roster; with ``keep_zones``, students in
    nearby time zones are kept together (sorted by UTC offset)."""
    _staff(course, activity)
    size = cint(size)
    if size < 1:
        frappe.throw(_("A group needs at least one student."))
    people = roster(course)
    if cint(keep_zones):
        people.sort(
            key=lambda p: (p["offset"] is None, p["offset"] or 0, p["name"].casefold())
        )
    else:
        # A fair, repeatable shuffle for grouping, not a secret.
        random.Random(f"{course}|{activity}").shuffle(people)  # nosec B311
    chunks = [people[i : i + size] for i in range(0, len(people), size)]
    if len(chunks) > 1 and len(chunks[-1]) == 1 and size > 1:
        chunks[-2].extend(chunks.pop())
    return [
        {"label": _("Group {0}").format(n), "students": [p["student"] for p in chunk]}
        for n, chunk in enumerate(chunks, start=1)
    ]


# -------------------------------------------------------------- busy times


def _rows_in(course_schedules, date_from, date_to):
    if not course_schedules:
        return []
    return frappe.get_all(
        ROW,
        filters={
            "parenttype": "Course Schedule",
            "parent": ["in", list(course_schedules)],
            "cs_meetdate": ["between", [date_from, date_to]],
        },
        fields=["parent", "cs_meetdate", "cs_fromtime", "cs_totime"],
    )


def _interval(day, start, end):
    s = datetime.combine(getdate(day), get_time(start))
    e = datetime.combine(getdate(day), get_time(end))
    return (s, e)


def _student_busy(students, date_from, date_to, exclude=None):
    """{student: [(start, end)]}: class meetings and other group meetings."""
    busy = {s: [] for s in students}
    if not students:
        return busy
    sections = {}
    for r in frappe.get_all(
        "Scheduled Course Roster",
        filters={"student": ["in", list(students)], "active": 1},
        fields=["student", "course_sc"],
    ):
        sections.setdefault(r.course_sc, set()).add(r.student)
    for row in _rows_in(sections, date_from, date_to):
        if row.cs_fromtime is None or row.cs_totime is None:
            continue
        for s in sections.get(row.parent, ()):
            busy[s].append(_interval(row.cs_meetdate, row.cs_fromtime, row.cs_totime))
    for m in frappe.db.sql(
        """select o.name, o.meeting_date, o.from_time, o.to_time, m.student
        from `tabOral Activity Meeting` o
        join `tabOral Activity Meeting Member` m on m.parent = o.name
        where o.kind = 'Group' and o.status not in ('Cancelled', 'Failed')
          and m.student in %(students)s
          and o.meeting_date between %(a)s and %(b)s""",
        {"students": tuple(students), "a": date_from, "b": date_to},
        as_dict=True,
    ):
        if m.name == exclude or m.from_time is None or m.to_time is None:
            continue
        busy[m.student].append(_interval(m.meeting_date, m.from_time, m.to_time))
    return busy


def _instructor_busy(user, date_from, date_to, exclude=None):
    sections = set(
        frappe.get_all(
            "Course Schedule Instructors",
            filters={"user": user, "parenttype": "Course Schedule"},
            pluck="parent",
        )
    )
    out = [
        _interval(r.cs_meetdate, r.cs_fromtime, r.cs_totime)
        for r in _rows_in(sections, date_from, date_to)
        if r.cs_fromtime is not None and r.cs_totime is not None
    ]
    for m in frappe.get_all(
        OAM,
        filters={
            "kind": "Group",
            "owner": user,
            "status": LIVE,
            "meeting_date": ["between", [date_from, date_to]],
        },
        fields=["name", "meeting_date", "from_time", "to_time"],
    ):
        if m.name != exclude and m.from_time is not None and m.to_time is not None:
            out.append(_interval(m.meeting_date, m.from_time, m.to_time))
    return out


def _accounts():
    from seminary.seminary.school_meetings import providers

    return {
        a.name: max(1, cint(a.max_concurrent))
        for a in frappe.get_all(
            "Web Meeting Account",
            filters={"enabled": 1, "provider": ["in", list(providers()) or [""]]},
            fields=["name", "max_concurrent"],
            order_by="name asc",
        )
    }


def _account_bookings(accounts, date_from, date_to, exclude=None):
    """[(account, start, end)] from class, group and cohort meetings."""
    if not accounts:
        return []
    out = []
    for r in frappe.db.sql(
        """select m.cs_meeting_account a, m.cs_meetdate d, m.cs_fromtime f, m.cs_totime t
        from `tabCourse Schedule Meeting Dates` m
        join `tabCourse Schedule` cs on cs.name = m.parent
        where m.parenttype = 'Course Schedule'
          and coalesce(cs.workflow_state, '') != 'Cancelled'
          and m.cs_meeting_account in %(acc)s
          and m.cs_meetdate between %(a)s and %(b)s""",
        {"acc": tuple(accounts), "a": date_from, "b": date_to},
        as_dict=True,
    ):
        if r.f is not None and r.t is not None:
            out.append((r.a, *_interval(r.d, r.f, r.t)))
    for m in frappe.get_all(
        OAM,
        filters={
            "kind": "Group",
            "status": LIVE,
            "meeting_account": ["in", list(accounts)],
            "meeting_date": ["between", [date_from, date_to]],
        },
        fields=["name", "meeting_account", "meeting_date", "from_time", "to_time"],
    ):
        if m.name != exclude and m.from_time is not None and m.to_time is not None:
            out.append(
                (m.meeting_account, *_interval(m.meeting_date, m.from_time, m.to_time))
            )
    # Cohort meetings on a school account are rooms too (decisions/101 s. 4.4).
    from seminary.seminary.discipleship.meetings import account_bookings

    out.extend(account_bookings(accounts, date_from, date_to, exclude=exclude))
    return out


NO_GAP = timedelta(0)


def _overlaps(a, b, gap=NO_GAP):
    return a[0] < b[1] + gap and b[0] < a[1] + gap


def _free_account(accounts, bookings, slot):
    for account, limit in accounts.items():
        used = sum(
            1 for a, s, e in bookings if a == account and _overlaps((s, e), slot)
        )
        if used < limit:
            return account
    return None


# ---------------------------------------------------------------- suggesting


def _constraints(raw):
    c = _json(raw, {})
    date_from, date_to = getdate(c.get("date_from")), getdate(c.get("date_to"))
    if not (date_from and date_to) or date_to < date_from:
        frappe.throw(_("Give a date range."))
    if (date_to - date_from).days > MAX_DAYS:
        frappe.throw(_("Choose a range of at most {0} days.").format(MAX_DAYS))
    length = cint(c.get("length"))
    if length < 5:
        frappe.throw(_("A meeting lasts at least 5 minutes."))
    start_min, end_min = _hm(c.get("hours_from") or "09:00"), _hm(
        c.get("hours_to") or "17:00"
    )
    if end_min - start_min < length:
        frappe.throw(_("The daily hours are shorter than one meeting."))
    weekdays = [cint(d) for d in c.get("weekdays") or [0, 1, 2, 3, 4]]
    return frappe._dict(
        date_from=date_from,
        date_to=date_to,
        length=timedelta(minutes=length),
        gap=timedelta(minutes=max(0, cint(c.get("gap")))),
        start_min=start_min,
        end_min=end_min,
        weekdays=set(weekdays),
        attend=bool(cint(c.get("attend", 1))),
        use_accounts=bool(cint(c.get("use_accounts", 1))),
    )


def _deviation(local_start, local_end, c):
    """Minutes a member's meeting lies outside their hours (§5)."""
    if local_start.weekday() not in c.weekdays:
        return OFF_DAY
    day = datetime.combine(local_start.date(), datetime.min.time())
    window_start = day + timedelta(minutes=c.start_min)
    window_end = day + timedelta(minutes=c.end_min)
    before = max(0, (window_start - local_start).total_seconds() // 60)
    after = max(0, (local_end - window_end).total_seconds() // 60)
    return int(before + after)


def _candidates(c, instructor_tz):
    """Site-local starts every 15 minutes whose date, in the instructor's own
    zone, is in the range; with the instructor attending, only inside their
    hours on their allowed days."""
    first = datetime.combine(c.date_from, datetime.min.time()) - timedelta(days=1)
    last = datetime.combine(c.date_to, datetime.min.time()) + timedelta(days=2)
    at = first
    while at + c.length <= last:
        local = _in_zone(at, instructor_tz)
        end = local + c.length
        if not (c.date_from <= local.date() <= c.date_to):
            at += STEP
            continue
        if c.attend:
            if (
                local.weekday() in c.weekdays
                and local.hour * 60 + local.minute >= c.start_min
                and end.date() == local.date()
                and end.hour * 60 + end.minute <= c.end_min
            ):
                yield at
        else:
            yield at
        at += STEP


def _note(costs, names, zones, total):
    parts = []
    for student, (minutes, local) in costs.items():
        if not minutes:
            continue
        if minutes >= OFF_DAY:
            parts.append(
                _("{0} for {1} ({2}), on a day outside the chosen weekdays").format(
                    local.strftime("%H:%M"), names[student], zones[student]
                )
            )
            continue
        h, m = divmod(int(minutes), 60)
        span = f"{h} h {m:02d} min" if h and m else (f"{h} h" if h else f"{m} min")
        parts.append(
            _("{0} for {1} ({2}), {3} outside their hours").format(
                local.strftime("%H:%M"), names[student], zones[student], span
            )
        )
    if not parts:
        return None
    return "; ".join(parts) + ". " + _("No time fits all {0}.").format(total)


@frappe.whitelist()
def suggest(course, activity, groups, constraints):
    _staff(course, activity)
    c = _constraints(constraints)
    groups = [g for g in _json(groups, []) if g.get("students")]
    if not groups:
        frappe.throw(_("Make the groups first."))
    people = {p["student"]: p for p in roster(course)}
    for g in groups:
        for s in g["students"]:
            if s not in people:
                frappe.throw(
                    _("{0} is not an active student on this section.").format(s)
                )
    instructor_tz = zone_or_site(frappe.session.user)
    students = [s for g in groups for s in g["students"]]
    busy = _student_busy(students, c.date_from, c.date_to)
    mine = (
        _instructor_busy(frappe.session.user, c.date_from, c.date_to)
        if c.attend
        else []
    )
    accounts = _accounts() if c.use_accounts else {}
    bookings = _account_bookings(accounts, c.date_from, c.date_to) if accounts else []
    starts = list(_candidates(c, instructor_tz))
    chosen = []
    out = []
    for g in groups:
        best = None
        for start in starts:
            slot = (start, start + c.length)
            if any(_overlaps(slot, b) for s in g["students"] for b in busy[s]):
                continue
            if c.attend and (
                any(_overlaps(slot, b, c.gap) for b in mine)
                or any(_overlaps(slot, x, c.gap) for x in chosen)
            ):
                continue
            if accounts and not _free_account(accounts, bookings, slot):
                continue
            costs = {}
            for s in g["students"]:
                tz = people[s]["time_zone"]
                if c.attend or not tz:
                    costs[s] = (0, _in_zone(start, tz or get_system_timezone()))
                    continue
                local = _in_zone(start, tz)
                costs[s] = (_deviation(local, local + c.length, c), local)
            total = sum(v[0] for v in costs.values())
            if best is None or total < best[0]:
                best = (total, slot, costs)
                if total == 0:
                    break
        if not best:
            out.append(
                {
                    "label": g.get("label"),
                    "students": g["students"],
                    "start": None,
                    "reason": _("No free time in the range: widen it or the hours."),
                }
            )
            continue
        total, slot, costs = best
        chosen.append(slot)
        if accounts:
            account = _free_account(accounts, bookings, slot)
            bookings.append((account, *slot))
        names = {s: people[s]["name"] for s in g["students"]}
        zones = {s: people[s]["time_zone"] or _("unknown") for s in g["students"]}
        out.append(
            {
                "label": g.get("label"),
                "students": g["students"],
                "start": slot[0].strftime("%Y-%m-%d %H:%M:%S"),
                "end": slot[1].strftime("%Y-%m-%d %H:%M:%S"),
                "start_utc": _utc_iso(slot[0]),
                "end_utc": _utc_iso(slot[1]),
                "cost": total,
                "note": _note(costs, names, zones, len(g["students"])),
                "local": [
                    {
                        "student": s,
                        "name": names[s],
                        "time_zone": people[s]["time_zone"],
                        "local_start": costs[s][1].strftime("%Y-%m-%d %H:%M"),
                    }
                    for s in g["students"]
                ],
            }
        )
    return out


# ---------------------------------------------------------------- creating


def _check(slot, students, accounts, exclude=None):
    """Why this slot cannot be booked now, or None; and the account it gets."""
    day_from = day_to = slot[0].date()
    busy = _student_busy(students, day_from, day_to, exclude=exclude)
    names = {
        s: frappe.db.get_value("Student", s, "student_name") or s for s in students
    }
    clash = [names[s] for s in students if any(_overlaps(slot, b) for b in busy[s])]
    if clash:
        return _("{0} has another meeting then.").format(", ".join(clash)), None
    if accounts:
        account = _free_account(
            accounts,
            _account_bookings(accounts, day_from, day_to, exclude=exclude),
            slot,
        )
        if not account:
            return _("No school meeting account is free then."), None
        return None, account
    return None, None


@frappe.whitelist(methods=["POST"])
def create_meetings(course, activity, slots, capture_method, link=None):
    """Create a group meeting for each slot; one that now clashes is skipped
    and named, the rest are made (§5)."""
    scac, _act = _staff(course, activity)
    slots = _json(slots, [])
    obj = oral_meetings.method(capture_method)
    accounts = _accounts()
    if getattr(obj, "needs_managed", False) and not accounts:
        frappe.throw(
            _("This method records only meetings on a school meeting account; add one.")
        )
    if not accounts and not link:
        frappe.throw(_("Give the meetings' link: there is no school meeting account."))
    people = {p["student"]: p for p in roster(course)}
    # One scheduler at a time on this section.
    frappe.db.sql(
        "select name from `tabCourse Schedule` where name = %s for update", (course,)
    )
    created, skipped = [], []
    for s in slots:
        students = [x for x in s.get("students") or [] if x in people]
        slot = _slot_of(s)
        if not (students and slot):
            continue
        if slot[1] <= slot[0] or slot[0].date() != slot[1].date():
            skipped.append({"label": s.get("label"), "reason": _("Invalid time.")})
            continue
        reason, account = _check(slot, students, accounts)
        if reason:
            skipped.append({"label": s.get("label"), "reason": reason})
            continue
        doc = frappe.get_doc(
            {
                "doctype": OAM,
                "kind": "Group",
                "group_label": (s.get("label") or "")[:140],
                "course_schedule": course,
                "course_assess": scac,
                "oral_activity": activity,
                "meeting_date": slot[0].date(),
                "from_time": slot[0].time(),
                "to_time": slot[1].time(),
                "method": capture_method,
                "status": "Scheduled",
                "link": None if account else link,
                "meeting_account": account,
                "meeting_status": "Pending" if account else None,
                "schedule_note": (s.get("note") or "")[:1000] or None,
                "members": [
                    {"student": x, "time_zone": people[x]["time_zone"]}
                    for x in students
                ],
            }
        ).insert(ignore_permissions=True)
        created.append(doc.name)
        _enqueue("sync_meeting", name=doc.name, notify="created")
    return {"created": created, "skipped": skipped}


def _enqueue(fn, **kwargs):
    frappe.enqueue(
        f"seminary.seminary.oral_groups.{fn}",
        queue="short",
        enqueue_after_commit=True,
        now=bool(frappe.flags.in_test),
        **kwargs,
    )


def sync_meeting(name, notify=None):
    """Create or move the provider's meeting, then arm the capture and tell the group."""
    from seminary.seminary import school_meetings

    doc = frappe.get_doc(OAM, name)
    if doc.status not in oral_meetings.ACTIVE:
        return
    if doc.meeting_account:
        acc = school_meetings._account(doc.meeting_account)
        try:
            if not acc:
                frappe.throw(_("The meeting account is gone or disabled."))
            meeting = _provider_meeting(doc)
            provider = school_meetings.connector(acc["provider"])
            if doc.provider_meeting_id:
                out = provider.update(acc, doc.provider_meeting_id, meeting) or {}
            else:
                out = provider.create(acc, meeting) or {}
                if not (out.get("join_url") and out.get("meeting_id")):
                    frappe.throw(_("The provider returned no meeting."))
        except Exception as e:
            frappe.log_error(title=f"Group meeting failed: {name}")
            doc.db_set(
                {"meeting_status": "Failed", "meeting_error": oral_meetings._message(e)}
            )
            return
        values = {"meeting_status": "Created", "meeting_error": None}
        if out.get("join_url"):
            values["link"] = out["join_url"]
        if out.get("meeting_id"):
            values["provider_meeting_id"] = str(out["meeting_id"])
        if "host_key" in out:
            values["host_key"] = out.get("host_key") or None
        doc.db_set(values)
    oral_meetings.rearm(name)
    if notify:
        tell_members(name, notify)


def _provider_meeting(doc):
    from seminary.seminary.school_meetings import _instructor_emails

    start = datetime.combine(getdate(doc.meeting_date), get_time(doc.from_time))
    end = datetime.combine(getdate(doc.meeting_date), get_time(doc.to_time))
    title = frappe.db.get_value("Course Schedule", doc.course_schedule, "title")
    activity = frappe.db.get_value("Oral Activity", doc.oral_activity, "title")
    return {
        "topic": f"{title or doc.course_schedule}: {activity} ({doc.group_label or _('group')})",
        "date": str(start.date()),
        "from_time": start.strftime("%H:%M"),
        "to_time": end.strftime("%H:%M"),
        "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration": max(1, int((end - start).total_seconds() // 60)),
        "timezone": get_system_timezone(),
        "alternative_hosts": _instructor_emails(doc.course_schedule),
    }


def delete_provider_meeting(account, meeting_id):
    from seminary.seminary import school_meetings

    try:
        acc = school_meetings._account(account)
        if acc:
            school_meetings.connector(acc["provider"]).delete(acc, meeting_id)
    except Exception:
        frappe.log_error(title=f"Group meeting delete failed: {meeting_id}")


# ------------------------------------------------------------------ changes


def _group(name):
    doc = oral_meetings._staff_capture(name)
    if doc.kind != "Group":
        frappe.throw(_("This is not a group meeting."))
    if doc.status not in oral_meetings.ACTIVE + ("Failed",):
        frappe.throw(_("This meeting has already taken place."))
    return doc


@frappe.whitelist(methods=["POST"])
def move_meeting(name, start=None, end=None, start_utc=None, end_utc=None):
    doc = _group(name)
    slot = _slot_of(
        {"start": start, "end": end, "start_utc": start_utc, "end_utc": end_utc}
    )
    if not slot:
        frappe.throw(_("Give the new time."))
    if slot[1] <= slot[0] or slot[0].date() != slot[1].date():
        frappe.throw(_("Invalid time."))
    students = [m.student for m in doc.members]
    accounts = _accounts() if doc.meeting_account else {}
    reason, account = _check(slot, students, accounts, exclude=doc.name)
    if reason:
        frappe.throw(reason)
    old = (doc.meeting_account, doc.provider_meeting_id)
    doc.meeting_date, doc.from_time, doc.to_time = (
        slot[0].date(),
        slot[0].time(),
        slot[1].time(),
    )
    if account and account != doc.meeting_account:
        doc.meeting_account, doc.provider_meeting_id, doc.link = account, None, None
    if doc.status == "Failed":
        doc.status, doc.error = "Scheduled", None
    if doc.meeting_account:
        doc.meeting_status = "Pending"
    doc.schedule_note = None
    doc.save(ignore_permissions=True)
    if old[1] and old[0] != doc.meeting_account:
        _enqueue("delete_provider_meeting", account=old[0], meeting_id=old[1])
    _enqueue("sync_meeting", name=doc.name, notify="moved")
    return doc.name


@frappe.whitelist(methods=["POST"])
def move_student(student, from_meeting, to_meeting):
    src, dst = _group(from_meeting), _group(to_meeting)
    if (src.course_schedule, src.oral_activity) != (
        dst.course_schedule,
        dst.oral_activity,
    ):
        frappe.throw(_("Both meetings must be for the same activity."))
    row = next((m for m in src.members if m.student == student), None)
    if not row:
        frappe.throw(_("{0} is not in that meeting.").format(student))
    slot = _interval(dst.meeting_date, dst.from_time, dst.to_time)
    reason, _account = _check(slot, [student], {}, exclude=dst.name)
    if reason:
        frappe.throw(reason)
    tz = row.time_zone
    src.remove(row)
    src.save(ignore_permissions=True)
    dst.append("members", {"student": student, "time_zone": tz})
    dst.save(ignore_permissions=True)
    _enqueue("tell_members", name=dst.name, change="joined", only=[student])
    return dst.name


@frappe.whitelist(methods=["POST"])
def cancel_meeting(name):
    doc = _group(name)
    account, meeting_id = doc.meeting_account, doc.provider_meeting_id
    oral_meetings._cancel(doc)
    if meeting_id:
        _enqueue("delete_provider_meeting", account=account, meeting_id=meeting_id)
    _enqueue("tell_members", name=doc.name, change="cancelled")
    return "Cancelled"


# ------------------------------------------------------- telling students (§6)


def my_meetings(user, course=None, activity=None):
    """The group meetings this student is in, with their own link: never another's."""
    student = frappe.db.get_value("Student", {"user": user}, "name")
    if not student:
        return []
    params = {"student": student}
    where = ""
    if course:
        where += " and o.course_schedule = %(course)s"
        params["course"] = course
    if activity:
        where += " and o.oral_activity = %(activity)s"
        params["activity"] = activity
    rows = frappe.db.sql(
        f"""select o.name, o.course_schedule, o.oral_activity, o.group_label,
            o.meeting_date, o.from_time, o.to_time, o.link, o.status
        from `tabOral Activity Meeting` o
        join `tabOral Activity Meeting Member` m on m.parent = o.name
        where o.kind = 'Group' and m.student = %(student)s
          and o.status != 'Cancelled' {where}
        order by o.meeting_date, o.from_time""",  # nosec B608: fixed fragments, values bound
        params,
        as_dict=True,
    )
    out = []
    for r in rows:
        start = datetime.combine(getdate(r.meeting_date), get_time(r.from_time))
        end = datetime.combine(getdate(r.meeting_date), get_time(r.to_time))
        out.append(
            {
                "name": r.name,
                "course_schedule": r.course_schedule,
                "oral_activity": r.oral_activity,
                "activity_title": frappe.db.get_value(
                    "Oral Activity", r.oral_activity, "title"
                ),
                "group": r.group_label,
                "start_utc": _utc_iso(start),
                "end_utc": _utc_iso(end),
                "link": r.link if r.status in oral_meetings.ACTIVE else None,
                "status": r.status,
            }
        )
    return out


def _ics(doc, title, start, end, link, cancelled=False):
    from ics import Calendar, Event

    event = Event()
    event.uid = f"{doc.name}@seminary"
    event.name = title
    event.begin = start.replace(tzinfo=_site_zone())
    event.end = end.replace(tzinfo=_site_zone())
    event.location = link or _("Online")
    event.description = _(
        "This meeting is recorded for an oral assessment. Join: {0}"
    ).format(link or _("the link will follow"))
    if cancelled:
        event.status = "CANCELLED"
    cal = Calendar()
    cal.events.add(event)
    return cal.serialize()


def tell_members(name, change="created", only=None):
    """A portal notice and an email with an invite to each member (§6)."""
    doc = frappe.get_doc(OAM, name)
    activity = frappe.db.get_value("Oral Activity", doc.oral_activity, "title")
    title = _("{0}: your group meeting").format(activity)
    start = datetime.combine(getdate(doc.meeting_date), get_time(doc.from_time))
    end = datetime.combine(getdate(doc.meeting_date), get_time(doc.to_time))
    subject = (
        {
            "created": _("Your meeting for {0} is scheduled"),
            "moved": _("Your meeting for {0} has moved"),
            "joined": _("You have a meeting for {0}"),
            "cancelled": _("Your meeting for {0} is cancelled"),
        }
        .get(change, _("Your meeting for {0}"))
        .format(activity)
    )
    ics = _ics(doc, title, start, end, doc.link, cancelled=change == "cancelled")
    for m in doc.members:
        if only and m.student not in only:
            continue
        user = frappe.db.get_value("Student", m.student, "user")
        if not user:
            continue
        tz = own_zone(user) or get_system_timezone()
        local = _in_zone(start, tz)
        when = _("{0} at {1} ({2})").format(
            frappe.format(local.date(), "Date"), local.strftime("%H:%M"), tz
        )
        try:
            frappe.get_doc(
                {
                    "doctype": "Notification Log",
                    "for_user": user,
                    "type": "Alert",
                    "document_type": OAM,
                    "document_name": doc.name,
                    "subject": f"{subject}: {when}",
                }
            ).insert(ignore_permissions=True)
            email = frappe.db.get_value("User", user, "email")
            if email:
                frappe.sendmail(
                    recipients=[email],
                    subject=subject,
                    message=_(
                        "<p>{0}</p><p>It is recorded for an oral assessment.</p>"
                    ).format(frappe.utils.escape_html(when))
                    + (
                        f'<p><a href="{frappe.utils.escape_html(doc.link)}">'
                        + _("Join the meeting")
                        + "</a></p>"
                        if doc.link and change != "cancelled"
                        else ""
                    ),
                    attachments=[{"fname": "meeting.ics", "fcontent": ics}],
                    reference_doctype=OAM,
                    reference_name=doc.name,
                )
        except Exception:
            frappe.log_error(title=f"Group meeting notice for {m.student} failed")
