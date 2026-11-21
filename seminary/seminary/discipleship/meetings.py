# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Cohort meetings (decisions/101 section 4).

A cohort's leader either polls the members (options, Yes / If need be / No,
then picks one) or sets the time directly, once or as a series. A virtual
meeting carries the leader's link, or one Seminary creates on a school meeting
account where the cohort type allows it (051a: an account is a room, counted
with class and group meetings). An in-person one carries a location.

Members are not all students. Invited pastors and staff may have no Student
record, no class and, until they first sign in, no User. Every path here
reads those links as optional: no Student means no class clashes, no User
means no portal notice and an unknown time zone, never an error.

Times are stored naive in the site's zone, like class meetings; the portal
sends and receives UTC.
"""

import hmac
import secrets
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import get_datetime, get_system_timezone, getdate, now_datetime

from seminary.seminary import oral_groups
from seminary.seminary.discipleship.permissions import (
    STAFF_BYPASS,
    led_cohorts,
    mentor_cohorts,
    visible_cohorts,
)
from seminary.seminary.person import find_person
from seminary.seminary.time_zones import own_zone

MEETING = "Cohort Meeting"
VOTE = "Cohort Meeting Vote"
ANSWERS = ("Yes", "If need be", "No")
ATTENDANCE = ("Present", "Absent", "Excused")
MAX_SERIES = 52
FEED_PAST_DAYS = 90
CATEGORY = "Community"


# ------------------------------------------------------------------ access


def _is_staff(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or bool(set(frappe.get_roles(user)) & STAFF_BYPASS)


def _me():
    return find_person(user=frappe.session.user)


def _require_reader(cohort):
    if _is_staff() or cohort in visible_cohorts():
        return
    frappe.throw(_("You cannot see this cohort."), frappe.PermissionError)


def _require_leader(cohort):
    from seminary.seminary.discipleship.api import _require_leader as require

    return require(cohort)


def _can_lead(cohort):
    return _is_staff() or cohort in led_cohorts()


def _sees_attendance(cohort):
    return _can_lead(cohort) or cohort in mentor_cohorts()


def _type_of(cohort):
    cohort_type = frappe.db.get_value("Cohort", cohort, "cohort_type")
    values = (
        frappe.db.get_value(
            "Cohort Type",
            cohort_type,
            ["school_meeting_allowed", "meetings_in_calendar_feed"],
            as_dict=True,
        )
        if cohort_type
        else None
    ) or frappe._dict(school_meeting_allowed=0, meetings_in_calendar_feed=0)
    values.reminders = (
        sorted(
            {
                int(h)
                for h in frappe.get_all(
                    "Cohort Type Meeting Reminder",
                    filters={"parenttype": "Cohort Type", "parent": cohort_type},
                    pluck="hours_before",
                )
                if h is not None and int(h) >= 0
            },
            reverse=True,
        )
        if cohort_type
        else []
    )
    return values


# ------------------------------------------------------------------ members


def members(cohort):
    """Active members with the links they may or may not have."""
    rows = frappe.get_all(
        "Cohort Membership",
        filters={"cohort": cohort, "active": 1},
        fields=["person", "is_leader", "role"],
    )
    out = []
    for r in rows:
        p = frappe.db.get_value(
            "Person", r.person, ["full_name", "user", "primary_email"], as_dict=True
        )
        if not p:
            continue
        student = frappe.db.get_value("Student", {"person": r.person}, "name")
        if not student and p.user:
            student = frappe.db.get_value("Student", {"user": p.user}, "name")
        out.append(
            frappe._dict(
                person=r.person,
                name=p.full_name or r.person,
                user=p.user,
                email=p.primary_email,
                student=student,
                time_zone=own_zone(p.user) if p.user else None,
                is_leader=r.is_leader,
                role=r.role,
            )
        )
    return out


def _busy(people, day_from, day_to):
    """{person: [(start, end)]}: class meetings and oral group meetings for
    students, sections taught for instructors. Someone with neither, such as
    an invited pastor or a staff member, is never busy."""
    busy = {m.person: [] for m in people}
    students = {m.student: m.person for m in people if m.student}
    if students:
        for student, slots in oral_groups._student_busy(
            list(students), day_from, day_to
        ).items():
            busy[students[student]].extend(slots)
    for m in people:
        if m.user:
            busy[m.person].extend(
                oral_groups._instructor_busy(m.user, day_from, day_to)
            )
    return busy


def _clashes(people, start, end):
    busy = _busy(people, start.date(), end.date())
    return [
        m.name
        for m in people
        if any(oral_groups._overlaps((start, end), b) for b in busy[m.person])
    ]


# ------------------------------------------------------------------ times


def _slot(start_utc, end_utc):
    if not (start_utc and end_utc):
        frappe.throw(_("Give the start and the end."))
    start, end = oral_groups._from_utc(start_utc), oral_groups._from_utc(end_utc)
    if end <= start:
        frappe.throw(_("A meeting must end after it starts."))
    if start.date() != end.date():
        frappe.throw(_("A meeting must start and end on the same day."))
    return start, end


def _utc(dt):
    return oral_groups._utc_iso(get_datetime(dt)) if dt else None


def _when(dt, tz):
    local = oral_groups._in_zone(get_datetime(dt), tz)
    return _("{0} at {1} ({2})").format(
        frappe.format(local.date(), "Date"), local.strftime("%H:%M"), tz
    )


# --------------------------------------------------------- meeting accounts


def account_bookings(accounts, date_from, date_to, exclude=None):
    """[(account, start, end)] held by scheduled cohort meetings, for the
    shared count of 051a (class and group meetings call this too)."""
    if not accounts:
        return []
    out = []
    for m in frappe.get_all(
        MEETING,
        filters={
            "status": "Scheduled",
            "meeting_account": ["in", list(accounts)],
            "starts_on": ["between", [f"{date_from} 00:00:00", f"{date_to} 23:59:59"]],
        },
        fields=["name", "meeting_account", "starts_on", "ends_on", "title", "cohort"],
    ):
        if m.name != exclude and m.starts_on and m.ends_on:
            out.append(
                (m.meeting_account, get_datetime(m.starts_on), get_datetime(m.ends_on))
            )
    return out


def class_rows(accounts, dates):
    """Cohort meetings in the row shape school_meetings compares class
    meetings in, so a section's save sees them as booked (051a section 4)."""
    if not (accounts and dates):
        return []
    out = []
    for m in frappe.get_all(
        MEETING,
        filters={"status": "Scheduled", "meeting_account": ["in", list(accounts)]},
        fields=["cohort", "title", "starts_on", "ends_on", "meeting_account"],
    ):
        if not (m.starts_on and m.ends_on):
            continue
        start, end = get_datetime(m.starts_on), get_datetime(m.ends_on)
        if str(start.date()) not in dates:
            continue
        out.append(
            frappe._dict(
                parent=m.cohort,
                title=_("{0}, cohort meeting {1}").format(m.cohort, m.title),
                cs_meetdate=start.date(),
                cs_fromtime=start.time(),
                cs_totime=end.time(),
                cs_meeting_account=m.meeting_account,
            )
        )
    return out


def _book(start, end, exclude=None):
    """A free school meeting account for the slot, under a lock, or a throw."""
    accounts = oral_groups._accounts()
    if not accounts:
        frappe.throw(_("The school has no meeting account set up."))
    frappe.db.sql(
        "select name from `tabWeb Meeting Account` where enabled = 1 for update"
    )
    account = oral_groups._free_account(
        accounts,
        oral_groups._account_bookings(
            accounts, start.date(), end.date(), exclude=exclude
        ),
        (start, end),
    )
    if not account:
        frappe.throw(
            _("No school meeting account is free on {0} from {1} to {2}.").format(
                frappe.format(start.date(), "Date"),
                start.strftime("%H:%M"),
                end.strftime("%H:%M"),
            )
        )
    return account


def _enqueue(fn, **kwargs):
    frappe.enqueue(
        f"seminary.seminary.discipleship.meetings.{fn}",
        queue="short",
        enqueue_after_commit=True,
        now=bool(frappe.flags.in_test),
        **kwargs,
    )


def sync_meeting(name):
    """Create or move the provider's meeting for a school-account meeting."""
    from seminary.seminary import school_meetings

    doc = frappe.get_doc(MEETING, name)
    if doc.status != "Scheduled" or not doc.meeting_account:
        return
    acc = school_meetings._account(doc.meeting_account)
    try:
        if not acc:
            frappe.throw(_("The meeting account is gone or disabled."))
        provider = school_meetings.connector(acc["provider"])
        meeting = _provider_meeting(doc)
        if doc.provider_meeting_id:
            out = provider.update(acc, doc.provider_meeting_id, meeting) or {}
        else:
            out = provider.create(acc, meeting) or {}
            if not (out.get("join_url") and out.get("meeting_id")):
                frappe.throw(_("The provider returned no meeting."))
    except Exception as e:
        frappe.log_error(title=f"Cohort meeting failed: {name}")
        doc.db_set({"meeting_status": "Failed", "meeting_error": str(e)[:500]})
        return
    values = {"meeting_status": "Created", "meeting_error": None}
    if out.get("join_url"):
        values["link"] = out["join_url"]
    if out.get("meeting_id"):
        values["provider_meeting_id"] = str(out["meeting_id"])
    if "host_key" in out:
        values["host_key"] = out.get("host_key") or None
    doc.db_set(values)


def _provider_meeting(doc):
    start, end = get_datetime(doc.starts_on), get_datetime(doc.ends_on)
    cohort_name = frappe.db.get_value("Cohort", doc.cohort, "cohort_name")
    leader = frappe.db.get_value("Cohort", doc.cohort, "leader")
    user = frappe.db.get_value("Person", leader, "user") if leader else None
    email = frappe.db.get_value("User", user, "email") if user else None
    return {
        "topic": f"{cohort_name or doc.cohort}: {doc.title}",
        "date": str(start.date()),
        "from_time": start.strftime("%H:%M"),
        "to_time": end.strftime("%H:%M"),
        "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration": max(1, int((end - start).total_seconds() // 60)),
        "timezone": get_system_timezone(),
        "alternative_hosts": [email] if email else [],
    }


def delete_provider_meeting(account, meeting_id):
    oral_groups.delete_provider_meeting(account, meeting_id)


# ------------------------------------------------------------------ reading


@frappe.whitelist()
def cohort_meetings(cohort):
    """Upcoming and recent meetings and open polls, for one cohort."""
    _require_reader(cohort)
    me = _me()
    lead = _can_lead(cohort)
    sees_attendance = _sees_attendance(cohort)
    since = now_datetime() - timedelta(days=30)
    rows = frappe.get_all(
        MEETING,
        filters={"cohort": cohort},
        or_filters=[
            ["status", "=", "Polling"],
            ["starts_on", ">=", since],
        ],
        fields=["name"],
        order_by="starts_on asc, creation asc",
    )
    people = members(cohort)
    names = {m.person: m.name for m in people}
    out = []
    for r in rows:
        doc = frappe.get_doc(MEETING, r.name)
        out.append(_view(doc, me, lead, sees_attendance, people, names))
    settings = _type_of(cohort)
    return {
        "meetings": out,
        "can_manage": lead,
        "school_meeting_allowed": settings.school_meeting_allowed,
        "calendar_feed": settings.meetings_in_calendar_feed,
        "members": (
            [
                {"person": m.person, "name": m.name, "time_zone": m.time_zone}
                for m in people
            ]
            if lead
            else []
        ),
    }


def _view(doc, me, lead, sees_attendance, people, names):
    started = bool(doc.starts_on and get_datetime(doc.starts_on) <= now_datetime())
    v = {
        "name": doc.name,
        "title": doc.title,
        "status": doc.status,
        "mode": doc.mode,
        "series": doc.series,
        "start_utc": _utc(doc.starts_on),
        "end_utc": _utc(doc.ends_on),
        "poll_closes_utc": _utc(doc.poll_closes_on),
        "location": doc.location if doc.mode == "In person" else None,
        "link": (
            doc.link if doc.mode == "Virtual" and doc.status == "Scheduled" else None
        ),
        "school_meeting": doc.school_meeting,
        "meeting_status": doc.meeting_status if lead else None,
        "meeting_error": doc.meeting_error if lead else None,
        "host_key": doc.host_key if lead else None,
        "started": started,
    }
    if doc.status == "Polling":
        votes = frappe.get_all(
            VOTE, filters={"meeting": doc.name}, fields=["option", "person", "answer"]
        )
        options = []
        for o in doc.options:
            mine = next(
                (x.answer for x in votes if x.option == o.name and x.person == me), None
            )
            row = {
                "name": o.name,
                "start_utc": _utc(o.starts_on),
                "end_utc": _utc(o.ends_on),
                "mine": mine,
                "tally": {
                    a: sum(1 for x in votes if x.option == o.name and x.answer == a)
                    for a in ANSWERS
                },
            }
            if lead:
                row["voters"] = {
                    a: [
                        names.get(x.person, x.person)
                        for x in votes
                        if x.option == o.name and x.answer == a
                    ]
                    for a in ANSWERS
                }
                row["clashes"] = _clashes(
                    people, get_datetime(o.starts_on), get_datetime(o.ends_on)
                )
            options.append(row)
        v["options"] = options
        if lead:
            voted = {x.person for x in votes}
            v["non_voters"] = [m.name for m in people if m.person not in voted]
    if doc.status == "Scheduled":
        rows = {a.person: a.status for a in doc.attendance}
        if sees_attendance:
            v["attendance"] = [
                {"person": p, "name": names.get(p, p), "status": rows.get(p) or ""}
                for p in list(dict.fromkeys([*rows, *names]))
            ]
        elif me:
            v["my_attendance"] = rows.get(me) or None
    return v


# ------------------------------------------------------------------ polling


def _json(value, default):
    return oral_groups._json(value, default)


@frappe.whitelist(methods=["POST"])
def create_poll(
    cohort,
    title,
    options,
    poll_closes_utc,
    mode="Virtual",
    link=None,
    location=None,
    school_meeting=0,
):
    _require_leader(cohort)
    slots = [_slot(o.get("start_utc"), o.get("end_utc")) for o in _json(options, [])]
    if not slots:
        frappe.throw(_("Offer at least one time."))
    closes = oral_groups._from_utc(poll_closes_utc) if poll_closes_utc else None
    if not closes or closes <= now_datetime():
        frappe.throw(_("The poll must close in the future."))
    doc = frappe.get_doc(
        {
            "doctype": MEETING,
            "cohort": cohort,
            "title": (title or "").strip()[:140] or _("Cohort meeting"),
            "status": "Polling",
            "poll_closes_on": closes,
            **_place(cohort, mode, link, location, school_meeting),
            "options": [{"starts_on": s, "ends_on": e} for s, e in sorted(slots)],
        }
    ).insert(ignore_permissions=True)
    _enqueue("tell_members", names=[doc.name], change="poll")
    return doc.name


def _place(cohort, mode, link, location, school_meeting):
    if mode not in ("Virtual", "In person"):
        frappe.throw(_("A meeting is virtual or in person."))
    school = int(school_meeting or 0) and mode == "Virtual"
    if school and not _type_of(cohort).school_meeting_allowed:
        frappe.throw(_("This cohort's meetings cannot use a school meeting account."))
    if mode == "In person" and not (location or "").strip():
        frappe.throw(_("Say where the meeting is."))
    return {
        "mode": mode,
        "school_meeting": 1 if school else 0,
        "link": None if school or mode != "Virtual" else (link or "").strip() or None,
        "location": ((location or "").strip() or None) if mode == "In person" else None,
    }


@frappe.whitelist(methods=["POST"])
def vote(meeting, answers):
    """A member's answers, {option: Yes / If need be / No / ""}; empty clears."""
    doc = frappe.get_doc(MEETING, meeting)
    me = _me()
    if not (
        me
        and frappe.db.exists(
            "Cohort Membership", {"cohort": doc.cohort, "person": me, "active": 1}
        )
    ):
        frappe.throw(_("Only members of the cohort can vote."), frappe.PermissionError)
    if doc.status != "Polling":
        frappe.throw(_("This poll is closed."))
    options = {o.name for o in doc.options}
    for option, answer in _json(answers, {}).items():
        if option not in options:
            continue
        existing = frappe.db.exists(
            VOTE, {"meeting": meeting, "option": option, "person": me}
        )
        if not answer:
            if existing:
                frappe.delete_doc(VOTE, existing, ignore_permissions=True)
            continue
        if answer not in ANSWERS:
            frappe.throw(_("Answer Yes, If need be or No."))
        if existing:
            frappe.db.set_value(VOTE, existing, "answer", answer)
        else:
            frappe.get_doc(
                {
                    "doctype": VOTE,
                    "meeting": meeting,
                    "option": option,
                    "person": me,
                    "answer": answer,
                }
            ).insert(ignore_permissions=True)
    return True


@frappe.whitelist(methods=["POST"])
def choose_option(meeting, option):
    """The leader picks a time, before or after the poll closes."""
    doc = frappe.get_doc(MEETING, meeting)
    _require_leader(doc.cohort)
    if doc.status != "Polling":
        frappe.throw(_("This meeting is not being polled."))
    row = next((o for o in doc.options if o.name == option), None)
    if not row:
        frappe.throw(_("Pick one of the poll's times."))
    start, end = get_datetime(row.starts_on), get_datetime(row.ends_on)
    if doc.school_meeting:
        doc.meeting_account = _book(start, end, exclude=doc.name)
        doc.meeting_status = "Pending"
    doc.starts_on, doc.ends_on, doc.status = start, end, "Scheduled"
    doc.attendance = []
    _fill_attendance(doc)
    doc.save(ignore_permissions=True)
    _after_scheduling([doc.name], "created")
    return doc.name


def _fill_attendance(doc):
    have = {a.person for a in doc.attendance}
    for m in members(doc.cohort):
        if m.person not in have:
            doc.append("attendance", {"person": m.person})


# ---------------------------------------------------------------- scheduling


def _occurrences(start, end, repeat, until=None, count=None):
    """The series' (start, end) pairs: weekly, every two weeks or monthly,
    until a date or for a count, capped at MAX_SERIES."""
    from dateutil.rrule import MONTHLY, WEEKLY, rrule

    if not repeat:
        return [(start, end)]
    freq, interval = {
        "weekly": (WEEKLY, 1),
        "fortnightly": (WEEKLY, 2),
        "monthly": (MONTHLY, 1),
    }.get(repeat, (None, None))
    if freq is None:
        frappe.throw(_("Repeat weekly, every two weeks or monthly."))
    kwargs = {"dtstart": start, "interval": interval}
    if until:
        kwargs["until"] = datetime.combine(getdate(until), end.time())
    else:
        kwargs["count"] = min(int(count or 0) or MAX_SERIES, MAX_SERIES)
    length = end - start
    return [(s, s + length) for s in list(rrule(freq, **kwargs))[:MAX_SERIES]]


@frappe.whitelist(methods=["POST"])
def schedule(
    cohort,
    title,
    start_utc,
    end_utc,
    mode="Virtual",
    link=None,
    location=None,
    school_meeting=0,
    repeat=None,
    until=None,
    count=None,
):
    """Set a meeting, or a series, without a poll. A series meeting that
    finds no free school account is left out and named; the rest are made."""
    _require_leader(cohort)
    start, end = _slot(start_utc, end_utc)
    if start <= now_datetime():
        frappe.throw(_("A meeting must be in the future."))
    place = _place(cohort, mode, link, location, school_meeting)
    occurrences = _occurrences(start, end, repeat or None, until, count)
    series = frappe.generate_hash(length=10) if len(occurrences) > 1 else None
    created, skipped = [], []
    for s, e in occurrences:
        values = dict(place)
        if place["school_meeting"]:
            try:
                values["meeting_account"] = _book(s, e)
                values["meeting_status"] = "Pending"
            except frappe.ValidationError as err:
                skipped.append({"start_utc": _utc(s), "reason": str(err)})
                continue
        doc = frappe.get_doc(
            {
                "doctype": MEETING,
                "cohort": cohort,
                "title": (title or "").strip()[:140] or _("Cohort meeting"),
                "status": "Scheduled",
                "starts_on": s,
                "ends_on": e,
                "series": series,
                **values,
            }
        )
        _fill_attendance(doc)
        doc.insert(ignore_permissions=True)
        created.append(doc.name)
    if not created:
        frappe.throw(
            _("No meeting could be scheduled: {0}").format(skipped[0]["reason"])
        )
    _after_scheduling(created, "created")
    return {"created": created, "skipped": skipped}


def _after_scheduling(names, change):
    for name in names:
        if frappe.db.get_value(MEETING, name, "meeting_account"):
            _enqueue("sync_meeting", name=name)
        _enqueue("queue_reminders", name=name)
    # One notice per member for a whole series, not one per meeting.
    _enqueue("tell_members", names=names, change=change)


@frappe.whitelist(methods=["POST"])
def move_meeting(meeting, start_utc, end_utc):
    doc = frappe.get_doc(MEETING, meeting)
    _require_leader(doc.cohort)
    if doc.status != "Scheduled":
        frappe.throw(_("Only a scheduled meeting can be moved."))
    start, end = _slot(start_utc, end_utc)
    if start <= now_datetime():
        frappe.throw(_("A meeting must be in the future."))
    old = (doc.meeting_account, doc.provider_meeting_id)
    if doc.school_meeting:
        account = _book(start, end, exclude=doc.name)
        if account != doc.meeting_account:
            doc.meeting_account, doc.provider_meeting_id, doc.link = account, None, None
        doc.meeting_status = "Pending"
    doc.starts_on, doc.ends_on = start, end
    doc.save(ignore_permissions=True)
    cancel_reminders(doc.name)
    if old[1] and old[0] != doc.meeting_account:
        _enqueue("delete_provider_meeting", account=old[0], meeting_id=old[1])
    _after_scheduling([doc.name], "moved")
    return doc.name


@frappe.whitelist(methods=["POST"])
def cancel_meeting(meeting, rest_of_series=0):
    """Cancel one meeting, or it and the series' later meetings."""
    doc = frappe.get_doc(MEETING, meeting)
    _require_leader(doc.cohort)
    if doc.status == "Cancelled":
        return []
    docs = [doc]
    if int(rest_of_series or 0) and doc.series and doc.starts_on:
        docs += [
            frappe.get_doc(MEETING, n)
            for n in frappe.get_all(
                MEETING,
                filters={
                    "series": doc.series,
                    "status": "Scheduled",
                    "starts_on": [">", doc.starts_on],
                    "name": ["!=", doc.name],
                },
                pluck="name",
            )
        ]
    cancelled = []
    for d in docs:
        was_scheduled = d.status == "Scheduled"
        account, meeting_id = d.meeting_account, d.provider_meeting_id
        d.status = "Cancelled"
        d.save(ignore_permissions=True)
        cancel_reminders(d.name)
        if meeting_id:
            _enqueue("delete_provider_meeting", account=account, meeting_id=meeting_id)
        if was_scheduled:
            cancelled.append(d.name)
    if cancelled:
        _enqueue("tell_members", names=cancelled, change="cancelled")
    return [d.name for d in docs]


@frappe.whitelist(methods=["POST"])
def mark_attendance(meeting, rows):
    """The leader's record of who came; it touches no class attendance."""
    doc = frappe.get_doc(MEETING, meeting)
    _require_leader(doc.cohort)
    if doc.status != "Scheduled" or get_datetime(doc.starts_on) > now_datetime():
        frappe.throw(_("Attendance is taken once the meeting has started."))
    _fill_attendance(doc)
    given = {r.get("person"): r.get("status") or "" for r in _json(rows, [])}
    for row in doc.attendance:
        if row.person in given:
            status = given[row.person]
            if status and status not in ATTENDANCE:
                frappe.throw(_("Mark Present, Absent or Excused."))
            row.status = status or None
    doc.save(ignore_permissions=True)
    return True


# ---------------------------------------------------------- telling members


def _person_doc(person):
    try:
        return frappe.get_doc("Person", person)
    except frappe.DoesNotExistError:
        return None


def _send(person, subject, message, reference, dedupe_key=None, scheduled_at=None):
    """A portal notice (when the person has an account) and an email, through
    the comms ledger so Community opt-outs hold."""
    from seminary.seminary import comms

    user = frappe.db.get_value("Person", person, "user")
    for channel in (["In-App"] if user else []) + ["Email"]:
        try:
            comms.send_message(
                channel=channel,
                subject=subject,
                message=message,
                person=person,
                category=CATEGORY,
                reference_doctype=MEETING,
                reference_name=reference,
                scheduled_at=scheduled_at,
                dedupe_key=f"{dedupe_key}:{channel}" if dedupe_key else None,
            )
        except Exception:
            frappe.log_error(title=f"Cohort meeting notice failed: {reference}")


def _zone(m):
    return m.time_zone or get_system_timezone()


def _ics(docs, cancelled=False):
    from ics import Calendar, Event

    cal = Calendar()
    zone = oral_groups._site_zone()
    for d in docs:
        event = Event()
        event.uid = f"{d.name}@seminary"
        event.name = d.title
        event.begin = get_datetime(d.starts_on).replace(tzinfo=zone)
        event.end = get_datetime(d.ends_on).replace(tzinfo=zone)
        event.location = (
            d.location if d.mode == "In person" else (d.link or _("Online"))
        )
        if d.mode == "Virtual" and d.link:
            event.description = _("Join: {0}").format(d.link)
        if cancelled or d.status == "Cancelled":
            event.status = "CANCELLED"
        cal.events.add(event)
    return cal.serialize()


def tell_members(names, change="created"):
    """One notice per member for these meetings (a series is one notice). A
    scheduled or moved meeting's email carries a calendar invite."""
    from seminary.seminary import comms

    docs = [frappe.get_doc(MEETING, n) for n in names]
    if not docs:
        return
    cohort = docs[0].cohort
    cohort_name = frappe.db.get_value("Cohort", cohort, "cohort_name") or cohort
    title = docs[0].title
    subject = (
        {
            "poll": _("{0}: when can you meet?"),
            "created": _("{0}: meeting scheduled"),
            "moved": _("{0}: meeting moved"),
            "cancelled": _("{0}: meeting cancelled"),
        }
        .get(change, _("{0}: meeting"))
        .format(cohort_name)
    )
    invite = _ics(docs, cancelled=change == "cancelled") if change != "poll" else None
    for m in members(cohort):
        tz = _zone(m)
        if change == "poll":
            lines = [
                _("{0} asks when you can meet for “{1}”.").format(cohort_name, title),
                _("Answer in the Community before {0}.").format(
                    _when(docs[0].poll_closes_on, tz)
                ),
            ]
        else:
            lines = [title] + [_when(d.starts_on, tz) for d in docs]
            first = docs[0]
            if change != "cancelled":
                if first.mode == "In person" and first.location:
                    lines.append(_("Where: {0}").format(first.location))
                elif first.link:
                    lines.append(
                        '<a href="{0}">{1}</a>'.format(
                            frappe.utils.escape_html(first.link), _("Join the meeting")
                        )
                    )
        message = "".join(
            f"<p>{line if line.startswith('<a ') else frappe.utils.escape_html(line)}</p>"
            for line in lines
        )
        # The portal notice goes through the ledger; the email goes direct
        # because it carries the invite, after the same consent check.
        if m.user:
            try:
                comms.send_message(
                    channel="In-App",
                    subject=subject,
                    message=message,
                    person=m.person,
                    category=CATEGORY,
                    reference_doctype=MEETING,
                    reference_name=docs[0].name,
                )
            except Exception:
                frappe.log_error(title=f"Cohort meeting notice failed: {docs[0].name}")
        _email(m, subject, message, docs[0].name, invite)


def _email(m, subject, message, reference, invite=None):
    from seminary.seminary import comms

    person_doc = _person_doc(m.person)
    if not person_doc:
        return
    if comms.consent_blocks(person_doc, "Email", CATEGORY):
        return
    address = comms.resolve_address(person_doc, "Email", CATEGORY) or m.email
    if not address:
        return
    try:
        frappe.sendmail(
            recipients=[address],
            subject=subject,
            message=message,
            attachments=(
                [{"fname": "meeting.ics", "fcontent": invite}] if invite else None
            ),
            reference_doctype=MEETING,
            reference_name=reference,
        )
    except Exception:
        frappe.log_error(title=f"Cohort meeting email failed: {reference}")


# ---------------------------------------------------------------- reminders


def queue_reminders(name):
    """Reminders at the cohort type's hours, queued in the comms ledger
    (decisions/101 section 4.5). Past reminder times are skipped."""
    doc = frappe.get_doc(MEETING, name)
    if doc.status != "Scheduled" or not doc.starts_on:
        return
    hours = _type_of(doc.cohort).reminders
    start = get_datetime(doc.starts_on)
    now = now_datetime()
    # A moved meeting queues afresh: its old reminders are cancelled, and the
    # key must not match them, even when the move lands in the same second.
    version = "{0}~{1}".format(
        start.strftime("%Y%m%d%H%M"),
        get_datetime(doc.modified).strftime("%Y%m%d%H%M%S%f"),
    )
    for m in members(doc.cohort):
        tz = _zone(m)
        for h in hours:
            at = start - timedelta(hours=h)
            if at <= now:
                continue
            lines = [frappe.utils.escape_html(doc.title), _when(start, tz)]
            if doc.mode == "In person" and doc.location:
                lines.append(
                    frappe.utils.escape_html(_("Where: {0}").format(doc.location))
                )
            message = "".join(f"<p>{line}</p>" for line in lines)
            if doc.mode == "Virtual" and doc.link:
                message += '<p><a href="{0}">{1}</a></p>'.format(
                    frappe.utils.escape_html(doc.link), _("Join the meeting")
                )
            _send(
                m.person,
                _("Reminder: {0}").format(doc.title),
                message,
                doc.name,
                dedupe_key=f"cohort-meeting:{doc.name}:{version}:{h}:{m.person}",
                scheduled_at=at,
            )


def cancel_reminders(name):
    """Withdraw reminders still waiting for a meeting that moved or ended."""
    frappe.db.sql(
        """update `tabCommunication Log`
        set status = 'Cancelled', error = %(why)s
        where reference_doctype = %(dt)s and reference_name = %(name)s
          and status = 'Queued' and scheduled_at > %(now)s""",
        {
            "dt": MEETING,
            "name": name,
            "now": now_datetime(),
            "why": _("The meeting moved or was cancelled."),
        },
    )


def hourly():
    """Remind non-voters a day before a poll closes, and tell the leader when
    it has closed (decisions/101 section 4.2)."""
    now = now_datetime()
    for name in frappe.get_all(
        MEETING,
        filters={
            "status": "Polling",
            "poll_reminded": 0,
            "poll_closes_on": ["between", [now, now + timedelta(hours=24)]],
        },
        pluck="name",
    ):
        _remind_non_voters(name)
    for name in frappe.get_all(
        MEETING,
        filters={
            "status": "Polling",
            "poll_close_notified": 0,
            "poll_closes_on": ["<=", now],
        },
        pluck="name",
    ):
        _tell_leader_closed(name)


def _remind_non_voters(name):
    doc = frappe.get_doc(MEETING, name)
    voted = set(frappe.get_all(VOTE, filters={"meeting": name}, pluck="person"))
    cohort_name = frappe.db.get_value("Cohort", doc.cohort, "cohort_name")
    for m in members(doc.cohort):
        if m.person in voted or m.is_leader:
            continue
        _send(
            m.person,
            _("{0}: the meeting poll closes soon").format(cohort_name),
            "<p>{0}</p>".format(
                frappe.utils.escape_html(
                    _("Say when you can meet for “{0}” before {1}.").format(
                        doc.title, _when(doc.poll_closes_on, _zone(m))
                    )
                )
            ),
            name,
            dedupe_key=f"cohort-poll-reminder:{name}:{m.person}",
        )
    doc.db_set("poll_reminded", 1)


def _tell_leader_closed(name):
    doc = frappe.get_doc(MEETING, name)
    cohort_name = frappe.db.get_value("Cohort", doc.cohort, "cohort_name")
    for m in members(doc.cohort):
        if not m.is_leader:
            continue
        _send(
            m.person,
            _("{0}: the meeting poll has closed").format(cohort_name),
            "<p>{0}</p>".format(
                frappe.utils.escape_html(
                    _("Pick a time for “{0}” in the Community.").format(doc.title)
                )
            ),
            name,
            dedupe_key=f"cohort-poll-closed:{name}:{m.person}",
        )
    doc.db_set("poll_close_notified", 1)


# ------------------------------------------------------------ calendar feed


@frappe.whitelist()
def calendar_feed_url(cohort):
    """The cohort's subscribable feed, made on first ask (section 4.6)."""
    _require_reader(cohort)
    if not _type_of(cohort).meetings_in_calendar_feed:
        frappe.throw(_("This cohort has no calendar feed."))
    token = frappe.db.get_value("Cohort", cohort, "calendar_token")
    if not token:
        token = secrets.token_urlsafe(24)
        frappe.db.set_value(
            "Cohort", cohort, "calendar_token", token, update_modified=False
        )
    return frappe.utils.get_url(
        "/api/method/seminary.seminary.discipleship.meetings.cohort_ics"
        f"?cohort={frappe.utils.quote(cohort)}&token={token}"
    )


@frappe.whitelist(allow_guest=True)
@rate_limit(key="cohort", limit=120, seconds=3600, ip_based=True)
def cohort_ics(cohort=None, token=None):
    """Guarded as a section's feed is: a per-cohort token compared in constant
    time, rate limited per cohort and address."""
    stored = frappe.db.get_value("Cohort", cohort, "calendar_token") if cohort else None
    if not (stored and token and hmac.compare_digest(str(stored), str(token))):
        raise frappe.PermissionError(_("Invalid calendar token provided."))
    if not _type_of(cohort).meetings_in_calendar_feed:
        raise frappe.PermissionError(_("This cohort has no calendar feed."))
    docs = [
        frappe.get_doc(MEETING, n)
        for n in frappe.get_all(
            MEETING,
            filters={
                "cohort": cohort,
                "status": "Scheduled",
                "starts_on": [">=", now_datetime() - timedelta(days=FEED_PAST_DAYS)],
            },
            pluck="name",
            order_by="starts_on asc",
        )
    ]
    frappe.local.response.filename = f"{cohort}.ics"
    frappe.local.response.filecontent = _ics(docs)
    frappe.local.response.type = "raw"
    frappe.local.response.content_type = "text/calendar; charset=utf-8"
    frappe.local.response.display_content_as = "inline"
