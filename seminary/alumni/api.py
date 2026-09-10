import json

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, getdate, now_datetime, today

from seminary.seminary.api import get_program_audit

DIRECTORY_FIELDS = (
    "name",
    "full_name",
    "image",
    "current_role",
    "current_organization",
    "current_partner_organization",
    "linkedin_url",
    "city",
    "country",
)

PROFILE_EDITABLE_FIELDS = (
    "full_name",
    "current_role",
    "current_organization",
    "current_partner_organization",
    "linkedin_url",
    "city",
    "country",
    "bio",
    "show_in_directory",
    "open_to_cohort_invites",
)

#: Peer messages are capped by counting the sender's own ledger rows rather
#: than with frappe.rate_limiter, which can key only on IP or a named form
#: field — behind office NAT that throttles a building, on mobile data it
#: throttles nobody (ADR 070).
RELAY_DAILY_LIMIT = 10
RELAY_PER_RECIPIENT_DAILY = 3


def _require_alumni_directory():
    """The one definition of who may read the directory."""
    if "Alumni" not in frappe.get_roles():
        frappe.throw(
            _("You do not have access to the alumni directory."), frappe.PermissionError
        )


@frappe.whitelist()
def directory_search(
    query: str = "",
    program: str = "",
    class_year: int | None = None,
    class_year_from: int | None = None,
    class_year_to: int | None = None,
    open_to_invites: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Search the directory. Returns {results, total, limit, offset}.

    Contact addresses are deliberately absent at any sharing setting: a list
    endpoint that hands back emails is a scraper's endpoint. They come one
    profile at a time from `get_directory_profile` (ADR 070).
    """
    _require_alumni_directory()

    filters: list = [
        ["enabled", "=", 1],
        ["show_in_directory", "=", 1],
    ]
    # Completed programs are rows now (ADR 069), so the program and class-year
    # filters reach through the child table. Frappe's `[child_doctype, field,
    # op, value]` filter form does that join for us and keeps permissions.
    #
    # It also reuses one join per child doctype, so program and both year
    # bounds bind to the SAME graduation row — "graduated from this program in
    # this span", not "has some degree from it and some degree in the span".
    # That is what makes a from/to pair mean anything.
    if program:
        filters.append(["Alumni Graduation", "program", "=", program])
    if class_year:
        filters.append(["Alumni Graduation", "class_year", "=", int(class_year)])
    if class_year_from:
        filters.append(["Alumni Graduation", "class_year", ">=", int(class_year_from)])
    if class_year_to:
        filters.append(["Alumni Graduation", "class_year", "<=", int(class_year_to)])
    if cint(open_to_invites):
        filters.append(["open_to_cohort_invites", "=", 1])

    or_filters = None
    if query:
        like = f"%{query}%"
        or_filters = [
            ["full_name", "like", like],
            ["current_role", "like", like],
            ["current_organization", "like", like],
            ["city", "like", like],
        ]

    limit = min(int(limit), 100)
    offset = int(offset)
    rows = frappe.get_all(
        "Alumni Profile",
        fields=list(DIRECTORY_FIELDS),
        filters=filters,
        or_filters=or_filters,
        limit_page_length=limit,
        limit_start=offset,
        # Ordered by name, not by class year. A person can hold several
        # graduations, so "their class year" is no longer a single sortable
        # value — ordering by one of them would silently pick a row.
        order_by="full_name asc",
        distinct=True,
    )
    _attach_graduations(rows)
    _attach_partner_organizations(rows)
    return {
        "results": rows,
        # Counted by pulling distinct names, not frappe.db.count: that hands
        # `distinct` to COUNT(*), which over-counts across the graduation join
        # whenever one profile matches on two degrees.
        "total": len(
            frappe.get_all(
                "Alumni Profile",
                filters=filters,
                or_filters=or_filters,
                pluck="name",
                distinct=True,
                limit_page_length=0,
            )
        ),
        "limit": limit,
        "offset": offset,
    }


def _attach_partner_organizations(rows):
    """Resolve linked partner organizations in one query, Listed ones only.

    Skipped entirely where the seminary has the partner directory switched
    off — the badge links into a directory that would refuse the click.
    """
    from seminary.partner.api import _directory_enabled

    for row in rows:
        row["partner_organization"] = None
    if not _directory_enabled():
        return
    ids = {r.get("current_partner_organization") for r in rows}
    ids.discard(None)
    if not ids:
        return
    orgs = {
        o["name"]: o
        for o in frappe.get_all(
            "Partner Organization",
            filters={"name": ("in", list(ids)), "listing_status": "Listed"},
            fields=["name", "organization_name", "image"],
        )
    }
    for row in rows:
        row["partner_organization"] = orgs.get(row.get("current_partner_organization"))


def _attach_graduations(rows):
    """One query for every listed profile's graduations, not one per row."""
    if not rows:
        return
    grads = frappe.get_all(
        "Alumni Graduation",
        filters={
            "parenttype": "Alumni Profile",
            "parent": ("in", [r["name"] for r in rows]),
        },
        fields=["parent", "program", "academic_year", "class_year"],
        order_by="class_year asc",
    )
    by_parent: dict = {}
    for grad in grads:
        by_parent.setdefault(grad.parent, []).append(grad)
    for row in rows:
        row["graduations"] = by_parent.get(row["name"], [])


@frappe.whitelist()
def get_my_profile() -> dict | None:
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required."), frappe.PermissionError)
    name = frappe.db.get_value("Alumni Profile", {"user": frappe.session.user}, "name")
    if not name:
        return None
    doc = frappe.get_doc("Alumni Profile", name)
    return doc.as_dict()


@frappe.whitelist()
def mark_as_alumni(program_enrollment: str) -> dict:
    staff_roles = {"Program Chair", "Registrar", "Seminary Manager", "System Manager"}
    if not (staff_roles & set(frappe.get_roles())) and not frappe.has_permission(
        "Alumni Profile", "create"
    ):
        frappe.throw(
            _("Not permitted to mark students as alumni."), frappe.PermissionError
        )

    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    if pe.docstatus != 1:
        frappe.throw(
            _("Program Enrollment must be submitted before transitioning to alumni.")
        )

    if frappe.db.get_value("Program", pe.program, "is_ongoing"):
        frappe.throw(_("Ongoing programs do not transition to alumni status."))

    audit = get_program_audit(program_enrollment=program_enrollment)
    if not audit.get("graduation_eligible"):
        frappe.throw(
            _("Student is not yet eligible for graduation per the program audit.")
        )

    student = frappe.get_doc("Student", pe.student)
    if not student.user:
        frappe.throw(
            _(
                "Student {0} has no linked User account; cannot create alumni profile."
            ).format(student.name)
        )

    # A person has one Alumni Profile and may graduate more than once, so the
    # second degree is a row on the profile — not a second profile, and not a
    # silent no-op. This used to return here on the existing profile, which
    # dropped the second graduation entirely *and* skipped the
    # `date_of_conclusion` stamp below, because the return preceded it (ADR 069).
    if not pe.date_of_conclusion:
        pe.db_set("date_of_conclusion", today(), update_modified=True)
        pe.reload()

    conclusion_date = getdate(pe.date_of_conclusion)
    existing = frappe.db.get_value("Alumni Profile", {"person": student.person})

    if existing:
        profile = frappe.get_doc("Alumni Profile", existing)
        already = profile.record_graduation(pe, conclusion_date)
        if not already:
            profile.save(ignore_permissions=True)
    else:
        # Person first (ADR 068 §1): the graduate already has one — this is the
        # same human, not a new identity. `email` and `full_name` are
        # `fetch_from person.*` mirrors, so passing the Student's copies would
        # be writing a mirror of a mirror.
        from seminary.seminary import intake

        profile = intake.make_alumni_profile(
            student.person, user=student.user, student=student.name
        )
        profile.record_graduation(pe, conclusion_date)
        profile.save(ignore_permissions=True)
        profile.db_set("owner", student.user, update_modified=False)

    # The role is granted by AlumniProfile.after_insert now, so it is already
    # there for a first graduation and this no longer re-grants it on a second
    # one. That is the point: a school that revoked someone's portal access
    # should not have it handed back because they finished another degree.

    return {
        "name": profile.name,
        "already_existed": bool(existing),
        "graduations": len(profile.graduations),
    }


@frappe.whitelist()
def update_profile(values: dict) -> dict:
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required."), frappe.PermissionError)

    name = frappe.db.get_value("Alumni Profile", {"user": frappe.session.user}, "name")
    if not name:
        frappe.throw(_("No alumni profile found for current user."))

    if isinstance(values, str):
        values = json.loads(values)

    # Every other editable field is free text the alumnus owns; this one is a
    # Link, and setting it blind would let someone badge themselves to an
    # organization the seminary has not listed.
    if values.get("current_partner_organization"):
        org = str(values["current_partner_organization"]).strip()
        if (
            frappe.db.get_value("Partner Organization", org, "listing_status")
            != "Listed"
        ):
            frappe.throw(_("Choose an organization from the partner directory."))

    doc = frappe.get_doc("Alumni Profile", name)
    for field in PROFILE_EDITABLE_FIELDS:
        if field in values:
            doc.set(field, values[field])
    doc.save(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def get_directory_profile(name: str) -> dict:
    """One alumnus, as another alumnus may see them (ADR 070).

    A profile that does not exist and a profile that has hidden itself throw
    the *same* error on purpose: distinguishing them would turn this into an
    oracle for exactly the people who asked not to be found.
    """
    _require_alumni_directory()

    row = frappe.db.get_value(
        "Alumni Profile",
        name,
        [
            *DIRECTORY_FIELDS,
            "person",
            "bio",
            "enabled",
            "show_in_directory",
            "open_to_cohort_invites",
        ],
        as_dict=True,
    )
    if not row or not (row.enabled and row.show_in_directory):
        frappe.throw(_("Profile not found."), frappe.DoesNotExistError)

    rows = [row]
    _attach_graduations(rows)
    _attach_partner_organizations(rows)
    row.pop("enabled", None)
    row.pop("show_in_directory", None)
    person = row.pop("person", None)
    row["contacts"] = _shared_contacts(person)
    row["relay_available"] = _relay_available(person)
    return row


def _shared_contacts(person):
    """The addresses this person chose to show, and that we can stand behind.

    `verified` is not optional here: an unverified address is an unconfirmed
    one, and publishing a typo to every alumnus publishes a stranger's inbox.
    Shaped like `utils.get_instructor_contact_channels` so the portal renders
    both with one component.
    """
    import re

    from seminary.seminary import comms

    if not person:
        return []
    rows = frappe.get_all(
        "Person Channel Address",
        filters={
            "parenttype": "Person",
            "parent": person,
            "share_in_directory": 1,
            "verified": 1,
            "status": "Active",
        },
        fields=["channel", "value"],
        order_by="idx asc",
    )
    if not rows:
        return []
    # `portal_contactable` stays the school's switch for which channels the
    # portal may surface at all; the per-address flag narrows it to what this
    # person chose. Both have to say yes.
    meta = {
        c["name"]: c
        for c in frappe.get_all(
            "Communication Channel",
            filters={
                "name": ("in", [r.channel for r in rows]),
                "enabled": 1,
                "portal_contactable": 1,
            },
            fields=["name", "channel_name", "weblink_prefix", "svg_icon"],
        )
    }
    out = []
    for r in rows:
        info = meta.get(r.channel)
        # Telegram stores a bot chat id, not a handle: it forms no public link
        # and the raw id is meaningless to a peer, so it is never published.
        if not info or r.channel == comms.TELEGRAM_CHANNEL:
            continue
        url = None
        prefix = info.get("weblink_prefix")
        if prefix:
            if r.channel == comms.WHATSAPP_CHANNEL:
                digits = re.sub(r"\D", "", r.value)
                url = prefix + digits if digits else None
            else:
                url = prefix + r.value
        out.append(
            {
                "channel": r.channel,
                "channel_name": info.get("channel_name"),
                "value": r.value,
                "url": url,
                "svg_icon": info.get("svg_icon"),
            }
        )
    return out


def _relay_available(person):
    """Can a peer reach them through the portal at all?

    Only the boolean travels: whether someone opted out of Community messages
    is their business, not the viewer's.
    """
    from seminary.seminary import comms

    if not person:
        return False
    if not comms.may_message(person):
        return False
    person_doc = frappe.get_doc("Person", person)
    return comms.reachability(person_doc, comms.IN_APP_CHANNEL, "Community") == "ok"


@frappe.whitelist(methods=["POST"])
def send_directory_message(profile: str, message: str) -> dict:
    """Write to another alumnus from the directory (ADR 070).

    Directory policy only. Authorization belongs to the portal messaging scope
    — an "Alumni Directory" Portal Messaging Rule is what admits this at all,
    so a seminary that configures no such rule has no peer messaging — and
    delivery, sanitization and threading belong to `send_portal_message`. What
    is added here is the rate limit, which portal compose has never had.
    """
    from seminary.seminary import comms
    from seminary.seminary.person import find_person

    _require_alumni_directory()
    me = find_person(user=frappe.session.user)
    if not me or not frappe.db.exists("Alumni Profile", {"person": me, "enabled": 1}):
        frappe.throw(_("You do not have an alumni profile."), frappe.PermissionError)

    target = frappe.db.get_value(
        "Alumni Profile",
        profile,
        ["person", "enabled", "show_in_directory"],
        as_dict=True,
    )
    if (
        not target
        or not target.person
        or not (target.enabled and target.show_in_directory)
    ):
        frappe.throw(_("Profile not found."), frappe.DoesNotExistError)
    if target.person == me:
        frappe.throw(_("That is your own profile."))

    body = frappe.utils.strip_html(message or "").strip()
    if not body:
        frappe.throw(_("Write a message first."))
    if len(body) > 4000:
        frappe.throw(_("That message is too long."))

    # The messaging scope is the authorization — an "Alumni Directory" Portal
    # Messaging Rule is what admits peer mail at all, and `may_message` is the
    # same check `send_portal_message` and `reply_portal_message` apply. One
    # message covers "no rule configured" and "they are unreachable", so this
    # cannot be used to probe someone's settings.
    if not comms.may_message(target.person):
        frappe.throw(
            _("{0} isn't accepting messages through the directory.").format(
                frappe.db.get_value("Alumni Profile", profile, "full_name") or _("They")
            )
        )

    _guard_relay_rate(profile)

    # Sent here rather than through send_portal_message so the log can carry
    # the Alumni Profile reference the rate limit counts on. Exposing that as
    # a parameter on the whitelisted compose endpoint would let a caller pass
    # a different reference each time and walk straight past the limit.
    log = comms.send_message(
        channel=comms.IN_APP_CHANNEL,
        person=target.person,
        subject=_("A message from the alumni directory"),
        message="<p>{0}</p>".format(
            frappe.utils.escape_html(body).replace("\n", "<br>")
        ),
        category="Community",
        reference_doctype="Alumni Profile",
        reference_name=profile,
        triggered_by=frappe.session.user,
    )
    # A consent block cancels the log instead of raising. Reporting that as
    # sent is the one outcome worth refusing outright — the sender is told the
    # same thing whether the block was found before or after the insert.
    if (
        not log
        or frappe.db.get_value("Communication Log", log, "status") == "Cancelled"
    ):
        frappe.throw(_("We could not deliver that message."))
    return {"sent": True}


def _guard_relay_rate(profile):
    since = add_to_date(now_datetime(), days=-1)
    mine = {
        "triggered_by": frappe.session.user,
        "reference_doctype": "Alumni Profile",
        "creation": (">", since),
    }
    if frappe.db.count("Communication Log", mine) >= RELAY_DAILY_LIMIT:
        frappe.throw(_("You have sent as many directory messages as one day allows."))
    if (
        frappe.db.count("Communication Log", {**mine, "reference_name": profile})
        >= RELAY_PER_RECIPIENT_DAILY
    ):
        frappe.throw(_("You have already written to them a few times today."))
