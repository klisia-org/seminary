"""Multi-channel communication engine (ADR 043).

All outbound messaging goes through send() / send_message() — direct
frappe.sendmail is the anti-pattern now. Both only CREATE a Queued
Communication Log (rendered snapshot, routed, consent-checked); delivery
happens in dispatch(), the cron-driven drainer that respects each Channel
Provider Account's hourly limit. The unique idempotency key on the log is the
no-double-send guarantee.

Routing per send: consent by category (Promotional needs opt-in, everything
else is blocked only by explicit opt-out, Emergency bypasses consent AND the
throttle), then the Person Channel Address scoped to the category (falling
back to the primary), then the provider account matching the person's country
(falling back to the channel's default account).

Adapters are resolved through the ``communication_channel_providers`` hook —
{provider_key: dotted.path.to.AdapterClass} — so other apps/regions add
providers with one class and one Channel Provider Account row. An adapter
implements send(log, account) -> provider_message_id|None and declares
``final_status`` ("Sent" for fire-and-track channels, "Delivered" when landing
is delivery, as for In-App).
"""

import json
import re
from urllib.parse import unquote

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime

ADAPTER_HOOK = "communication_channel_providers"
IN_APP_CHANNEL = "In-App"
EMAIL_CHANNEL = "Email"
MAX_RETRIES = 3
DISPATCH_BATCH = 500


# ---------------------------------------------------------------- adapters


class EmailAdapter:
    """Delivers through the site's Frappe Email Account stack."""

    final_status = "Sent"

    def send(self, log, account):
        if not log.to_address:
            raise ValueError("Email log has no to_address")
        frappe.sendmail(
            recipients=[log.to_address],
            subject=log.subject or "",
            message=log.message or "",
            reference_doctype=log.reference_doctype or log.doctype,
            reference_name=log.reference_name or log.name,
            expose_recipients="hide",
            now=False,
        )
        return None


class InAppAdapter:
    """The Communication Log row itself is the portal-inbox message: landing
    in the ledger is delivery. Read comes from the portal (stage two).

    instant=True: delivered synchronously at queue time — there is no carrier
    to rate-limit, and the inbox should never wait for the cron drainer."""

    final_status = "Delivered"
    instant = True

    def send(self, log, account):
        if not log.person:
            raise ValueError("In-App messages need a Person")
        return None


def get_adapter_registry():
    registry = {}
    hooked = frappe.get_hooks(ADAPTER_HOOK) or {}
    for key, value in hooked.items():
        registry[key] = value[-1] if isinstance(value, list) else value
    return registry


def get_adapter(provider_key):
    path = get_adapter_registry().get(provider_key)
    if not path:
        frappe.throw(_("No adapter registered for provider {0}.").format(provider_key))
    return frappe.get_attr(path)()


# ---------------------------------------------------------------- routing


def consent_blocks(person_doc, channel, category):
    if not category or category == "Emergency":
        return False
    status = None
    for row in person_doc.consents:
        if row.channel == channel and row.category == category:
            status = row.status
            break
    if category == "Promotional":
        return status != "Opted In"
    return status == "Opted Out"


def resolve_address(person_doc, channel, category=None):
    rows = [
        r
        for r in person_doc.channel_addresses
        if r.channel == channel and r.status == "Active"
    ]
    if category:
        scoped = next((r for r in rows if r.category == category), None)
        if scoped:
            return scoped.value
    primary = next((r for r in rows if r.is_primary), None)
    if primary:
        return primary.value
    unscoped = next((r for r in rows if not r.category), None)
    if unscoped:
        return unscoped.value
    return rows[0].value if rows else None


def pick_account(channel, country=None):
    accounts = frappe.get_all(
        "Channel Provider Account",
        filters={"channel": channel, "enabled": 1},
        fields=["name", "country"],
        order_by="creation asc",
    )
    if country:
        match = next((a for a in accounts if a.country == country), None)
        if match:
            return match.name
    default = next((a for a in accounts if not a.country), None)
    if default:
        return default.name
    return accounts[0].name if accounts else None


# ---------------------------------------------------------------- queueing


def send(
    person,
    template,
    *,
    to_address=None,
    context=None,
    channel="Email",
    category=None,
    reference_doctype=None,
    reference_name=None,
    triggered_by=None,
    scheduled_at=None,
    dedupe_key=None,
    awaiting_response=0,
    follow_up_after_days=0,
    follow_up_template=None,
    follow_up_of=None,
):
    """Render a Communication Template and queue the log. Returns the log
    name, or None when deduped / consent-cancelled.

    person may be None for addresses the spine doesn't know (an external
    recommender, a custom-filter recipient) — pass to_address explicitly and
    the site-default template version renders without consent data."""
    person_doc = frappe.get_doc("Person", person) if person else None
    tpl = frappe.get_doc("Communication Template", template)
    if not tpl.enabled:
        frappe.throw(_("Communication Template {0} is disabled.").format(template))
    category = category or tpl.category

    language = person_doc.language if person_doc else None
    version = tpl.get_version(channel, language)
    if not version:
        frappe.throw(
            _("Template {0} has no version for channel {1}.").format(template, channel)
        )

    ctx = {"person": person_doc}
    if reference_doctype and reference_name:
        ctx["doc"] = frappe.get_doc(reference_doctype, reference_name)
    ctx.update(context or {})

    return send_message(
        channel=channel,
        subject=(
            frappe.render_template(version.subject, ctx) if version.subject else None
        ),
        message=frappe.render_template(version.body, ctx),
        person=person_doc,
        to_address=to_address,
        category=category,
        template=tpl.name,
        language=version.language or language,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        triggered_by=triggered_by,
        scheduled_at=scheduled_at,
        dedupe_key=dedupe_key,
        awaiting_response=awaiting_response,
        follow_up_after_days=follow_up_after_days,
        follow_up_template=follow_up_template,
        follow_up_of=follow_up_of,
    )


def get_role_users(role):
    """Enabled users holding a role, minus the system accounts."""
    users = frappe.get_all(
        "Has Role",
        filters={"role": role, "parenttype": "User"},
        pluck="parent",
        distinct=True,
    )
    if not users:
        return []
    enabled = frappe.get_all(
        "User",
        filters=[["name", "in", users], ["enabled", "=", 1]],
        pluck="name",
    )
    return [u for u in enabled if u not in ("Administrator", "Guest")]


def send_to_role(
    role,
    template,
    *,
    context=None,
    channel="Email",
    reference_doctype=None,
    reference_name=None,
    triggered_by=None,
    dedupe_prefix=None,
):
    """Queue one templated log per enabled user holding the role. Each user
    gets a Person ensured (the ADR 042 staff seam), so staff communications
    land on their timeline too."""
    from seminary.seminary import person as person_spine

    logs = []
    for user in get_role_users(role):
        try:
            logs.append(
                send(
                    person_spine.ensure_person(user=user),
                    template,
                    context=context,
                    channel=channel,
                    reference_doctype=reference_doctype,
                    reference_name=reference_name,
                    triggered_by=triggered_by,
                    dedupe_key=f"{dedupe_prefix}::{user}" if dedupe_prefix else None,
                )
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"send_to_role({role}, {template}) failed for {user}",
            )
    return [log for log in logs if log]


def send_message(
    *,
    channel,
    message,
    subject=None,
    person=None,
    to_address=None,
    category=None,
    template=None,
    language=None,
    reference_doctype=None,
    reference_name=None,
    triggered_by=None,
    scheduled_at=None,
    dedupe_key=None,
    awaiting_response=0,
    follow_up_after_days=0,
    follow_up_template=None,
    follow_up_of=None,
):
    """Queue a pre-rendered message (the raw path — used by the Seminary
    Announcement port, where content is authored, not templated)."""
    message = _publish_embedded_files(message)
    person_doc = None
    if person:
        person_doc = (
            person
            if hasattr(person, "channel_addresses")
            else frappe.get_doc("Person", person)
        )

    values = dict(
        doctype="Communication Log",
        direction="Outbound",
        status="Queued",
        person=person_doc.name if person_doc else None,
        channel=channel,
        category=category,
        to_address=to_address,
        template=template,
        language=language,
        subject=subject,
        message=message,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        triggered_by=triggered_by or frappe.session.user,
        scheduled_at=scheduled_at,
        awaiting_response=awaiting_response,
        follow_up_after_days=follow_up_after_days,
        follow_up_template=follow_up_template,
        follow_up_of=follow_up_of,
    )

    if person_doc and consent_blocks(person_doc, channel, category):
        values.update(
            status="Cancelled",
            error=_("Blocked by consent: {0} / {1} for {2}.").format(
                channel, category, person_doc.name
            ),
        )
        return _insert_log(values, dedupe_key)

    if not values["to_address"] and person_doc and channel != IN_APP_CHANNEL:
        values["to_address"] = resolve_address(person_doc, channel, category)
    if not values["to_address"] and channel != IN_APP_CHANNEL:
        values.update(
            status="Cancelled",
            error=_("No active {0} address.").format(channel),
        )
        return _insert_log(values, dedupe_key)

    account = pick_account(channel, person_doc.country if person_doc else None)
    if not account:
        frappe.throw(
            _("No enabled Channel Provider Account for channel {0}.").format(channel)
        )
    values["provider_account"] = account
    log_name = _insert_log(values, dedupe_key)
    if log_name and not scheduled_at:
        _maybe_deliver_instant(log_name, account)
    return log_name


def _maybe_deliver_instant(log_name, account_name):
    """Adapters marked instant=True (In-App) deliver at queue time instead of
    waiting for the cron drainer. Errors fall back to the normal retry path."""
    account = frappe.get_doc("Channel Provider Account", account_name)
    try:
        adapter = get_adapter(account.provider)
    except Exception:
        return
    if getattr(adapter, "instant", False):
        _deliver(log_name, account)


def _publish_embedded_files(message):
    """Message content is being SENT to other people: an embedded private
    upload (desk Text Editor uploads default to private) would 403 for every
    recipient — portal inbox and email alike. Flip the referenced Files public
    and rewrite their URLs in the snapshot."""
    if not message or "/private/files/" not in message:
        return message
    for file_url in set(re.findall(r"/private/files/[^\"'\s>)]+", message)):
        # The desk editor appends ?fid=... to private URLs; File.file_url
        # stores the bare path.
        base = unquote(file_url.split("?")[0])
        name = frappe.db.get_value(
            "File", {"file_url": base}, "name"
        ) or frappe.db.get_value("File", {"file_url": file_url.split("?")[0]}, "name")
        if not name:
            continue
        try:
            file_doc = frappe.get_doc("File", name)
            file_doc.is_private = 0
            file_doc.save(ignore_permissions=True)
            message = message.replace(file_url, file_doc.file_url)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"Could not publish embedded file {file_url}"
            )
    return message


def _insert_log(values, dedupe_key=None):
    if dedupe_key:
        if frappe.db.exists("Communication Log", {"idempotency_key": dedupe_key}):
            return None
        values["idempotency_key"] = dedupe_key
    log = frappe.get_doc(values)
    try:
        log.insert(ignore_permissions=True)
    except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
        return None  # raced on the idempotency key — already queued elsewhere
    if log.status == "Cancelled":
        _reflect_announcement(log)
    return log.name


# ---------------------------------------------------------------- dispatch


def dispatch():
    """Cron drainer: deliver Queued logs per provider account, up to
    hourly_limit minus the trailing-hour sent count. Emergency-category logs
    bypass the throttle (never the account's enabled flag)."""
    now = now_datetime()
    accounts = {
        a.name: a
        for a in frappe.get_all(
            "Channel Provider Account",
            filters={"enabled": 1},
            fields=["name", "channel", "provider", "hourly_limit", "settings"],
        )
    }
    if not accounts:
        return

    remaining = {}
    for name, account in accounts.items():
        if account.hourly_limit:
            used = frappe.db.count(
                "Communication Log",
                {
                    "provider_account": name,
                    "direction": "Outbound",
                    "sent_at": (">=", add_to_date(now, hours=-1)),
                },
            )
            remaining[name] = max(0, account.hourly_limit - used)
        else:
            remaining[name] = None  # unlimited

    rows = frappe.db.sql(
        """
        SELECT name, provider_account, category
        FROM `tabCommunication Log`
        WHERE direction = 'Outbound' AND status = 'Queued'
          AND IFNULL(scheduled_at, '1900-01-01') <= %(now)s
          AND IFNULL(next_attempt_at, '1900-01-01') <= %(now)s
        ORDER BY creation ASC
        LIMIT %(limit)s
        """,
        {"now": now, "limit": DISPATCH_BATCH},
        as_dict=True,
    )

    for row in rows:
        account = accounts.get(row.provider_account)
        if not account:
            continue  # account disabled/removed: stays Queued for ops to fix
        emergency = row.category == "Emergency"
        if (
            remaining[account.name] is not None
            and remaining[account.name] <= 0
            and not emergency
        ):
            continue
        delivered = _deliver(row.name, account)
        if delivered and remaining[account.name] is not None and not emergency:
            remaining[account.name] -= 1

    _finalize_announcements()
    frappe.db.commit()


def _deliver(log_name, account):
    log = frappe.get_doc("Communication Log", log_name)
    if log.status != "Queued":
        return False  # raced with another dispatcher run
    log.db_set("status", "Sending", update_modified=False)
    try:
        adapter = get_adapter(account.provider)
        message_id = adapter.send(log, account)
        stamp = now_datetime()
        updates = {"status": adapter.final_status, "sent_at": stamp, "error": None}
        if adapter.final_status == "Delivered":
            updates["delivered_at"] = stamp
        if message_id:
            updates["provider_message_id"] = message_id
        log.db_set(updates, update_modified=False)
        _reflect_announcement(log)
        return True
    except Exception as e:
        retries = (log.retry_count or 0) + 1
        if retries >= MAX_RETRIES:
            log.db_set(
                {"status": "Failed", "retry_count": retries, "error": str(e)[:500]},
                update_modified=False,
            )
            frappe.log_error(
                f"Communication Log {log.name} failed permanently: {e}",
                "Communication Dispatch",
            )
            _reflect_announcement(log)
        else:
            log.db_set(
                {
                    "status": "Queued",
                    "retry_count": retries,
                    "error": str(e)[:500],
                    "next_attempt_at": add_to_date(
                        now_datetime(), minutes=5 * (2 ** (retries - 1))
                    ),
                },
                update_modified=False,
            )
        return False


def account_settings(account):
    try:
        return json.loads(account.settings or "{}")
    except ValueError:
        return {}


# ------------------------------------------------- announcement reflection


def _reflect_announcement(log):
    """Stage-one port glue: mirror log outcomes onto Seminary Announcement
    Recipient rows so the existing desk grid and portal query keep working."""
    if log.reference_doctype != "Seminary Announcement" or not log.reference_name:
        return
    mapped = {
        "Sent": "Sent",
        "Delivered": "Sent",
        "Read": "Sent",
        "Failed": "Failed",
        "Cancelled": "Failed",
    }.get(log.status)
    if not mapped:
        return
    row = frappe.db.get_value(
        "Seminary Announcement Recipient",
        {"parent": log.reference_name, "email": log.to_address},
        "name",
    )
    if row:
        frappe.db.set_value(
            "Seminary Announcement Recipient",
            row,
            {
                "delivery_status": mapped,
                "error": (log.error or None) if mapped == "Failed" else None,
            },
            update_modified=False,
        )


def _finalize_announcements():
    for name in frappe.get_all(
        "Seminary Announcement",
        filters={"docstatus": 1, "status": "Sending"},
        pluck="name",
    ):
        base = {
            "reference_doctype": "Seminary Announcement",
            "reference_name": name,
            "direction": "Outbound",
        }
        if frappe.db.count(
            "Communication Log", {**base, "status": ("in", ("Queued", "Sending"))}
        ):
            continue
        delivered = frappe.db.count(
            "Communication Log",
            {**base, "status": ("in", ("Sent", "Delivered", "Read"))},
        )
        frappe.db.set_value(
            "Seminary Announcement",
            name,
            {
                "status": "Sent" if delivered else "Failed",
                "sent_datetime": now_datetime(),
            },
            update_modified=False,
        )


# ---------------------------------------------------------------- follow-up


def process_follow_ups():
    """Daily sweep (ADR 043): outbound logs awaiting a response whose window
    elapsed with no read and no inbound reply either queue their follow-up
    template or raise a ToDo for whoever triggered them."""
    due = frappe.db.sql(
        """
        SELECT name FROM `tabCommunication Log`
        WHERE direction = 'Outbound'
          AND awaiting_response = 1 AND follow_up_done = 0
          AND follow_up_after_days > 0
          AND status IN ('Sent', 'Delivered')
          AND read_at IS NULL
          AND sent_at <= DATE_SUB(%(now)s, INTERVAL follow_up_after_days DAY)
        """,
        {"now": now_datetime()},
        pluck=True,
    )
    for name in due:
        try:
            _follow_up(frappe.get_doc("Communication Log", name))
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Follow-up failed for {name}")


# ------------------------------------------------------------ portal inbox

PREF_CATEGORIES = ("Transactional", "Academic", "Community", "Promotional", "Emergency")
INBOX_VISIBLE_STATUSES = ("Sent", "Delivered", "Read")


def _my_person():
    """The Person linked to the session user. Portal endpoints below filter by
    this server-side — a portal user can only ever see their own ledger."""
    from seminary.seminary.person import find_person

    if frappe.session.user == "Guest":
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    person = find_person(user=frappe.session.user)
    if not person:
        frappe.throw(_("No Person record is linked to your account."))
    return person


@frappe.whitelist()
def get_my_inbox(channel=None, category=None, unread_only=0, limit=100, box="inbox"):
    """The structured portal inbox (ADR 043 stage two): every message sent to
    the session user's Person, any channel, with filterable metadata.
    box="sent" lists the messages the session user composed instead."""
    person = _my_person()
    if box == "sent":
        filters = {"triggered_by": frappe.session.user, "direction": "Outbound"}
    else:
        filters = {
            "person": person,
            "direction": "Outbound",
            "status": ("in", INBOX_VISIBLE_STATUSES),
        }
    if channel:
        filters["channel"] = channel
    if category:
        filters["category"] = category
    if cint(unread_only) and box != "sent":
        filters["read_at"] = ("is", "not set")
    messages = frappe.get_all(
        "Communication Log",
        filters=filters,
        fields=[
            "name",
            "channel",
            "category",
            "subject",
            "message",
            "status",
            "sent_at",
            "read_at",
            "reference_doctype",
            "reference_name",
            "creation",
            "triggered_by",
            "person",
        ],
        order_by="creation desc",
        limit_page_length=cint(limit) or 100,
    )
    _annotate_parties(messages)
    unread = frappe.db.count(
        "Communication Log",
        {
            "person": person,
            "direction": "Outbound",
            "status": ("in", ("Sent", "Delivered")),
            "read_at": ("is", "not set"),
        },
    )
    return {"messages": messages, "unread": unread}


def _annotate_parties(messages):
    """Attach human names: sender_name from the triggering User, person_name
    for the recipient (the Sent box shows who a message went to)."""
    users = {m.triggered_by for m in messages if m.triggered_by}
    persons = {m.person for m in messages if m.person}
    user_names = (
        dict(
            frappe.get_all(
                "User",
                filters=[["name", "in", list(users)]],
                fields=["name", "full_name"],
                as_list=True,
            )
        )
        if users
        else {}
    )
    person_names = (
        dict(
            frappe.get_all(
                "Person",
                filters=[["name", "in", list(persons)]],
                fields=["name", "full_name"],
                as_list=True,
            )
        )
        if persons
        else {}
    )
    for m in messages:
        m["sender_name"] = user_names.get(m.triggered_by)
        m["person_name"] = person_names.get(m.person)


@frappe.whitelist()
def mark_inbox_read(name):
    """Portal read receipt: sets read_at (and Read for in-flight statuses)."""
    person = _my_person()
    log = frappe.db.get_value(
        "Communication Log", name, ["person", "status", "read_at"], as_dict=True
    )
    if not log or log.person != person:
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    if log.read_at:
        return log.read_at
    stamp = now_datetime()
    updates = {"read_at": stamp}
    if log.status in ("Sent", "Delivered"):
        updates["status"] = "Read"
    frappe.db.set_value("Communication Log", name, updates, update_modified=False)
    return stamp


@frappe.whitelist()
def mark_all_inbox_read():
    person = _my_person()
    frappe.db.sql(
        """
        UPDATE `tabCommunication Log`
        SET read_at = %(stamp)s,
            status = CASE WHEN status IN ('Sent', 'Delivered') THEN 'Read' ELSE status END
        WHERE person = %(person)s AND direction = 'Outbound'
          AND read_at IS NULL AND status IN ('Sent', 'Delivered', 'Read')
        """,
        {"stamp": now_datetime(), "person": person},
    )
    return True


@frappe.whitelist()
def get_my_communication_preferences():
    """Self-service preferences (ADR 043 stage two): language, per
    channel × category consent, and a read-only view of channel addresses."""
    person = frappe.get_doc("Person", _my_person())
    consents = {f"{row.channel}::{row.category}": row.status for row in person.consents}
    return {
        "language": person.language,
        "languages": frappe.get_all(
            "Language",
            filters={"enabled": 1},
            fields=["name", "language_name"],
            order_by="language_name asc",
        ),
        "channels": frappe.get_all(
            "Communication Channel",
            filters={"enabled": 1},
            pluck="name",
            order_by="creation asc",
        ),
        "categories": list(PREF_CATEGORIES),
        "consents": consents,
        "addresses": [
            {
                "channel": row.channel,
                "value": row.value,
                "category": row.category,
                "is_primary": row.is_primary,
                "verified": row.verified,
                "status": row.status,
            }
            for row in person.channel_addresses
        ],
    }


@frappe.whitelist()
def update_my_communication_preferences(language=None, consents=None):
    """consents: [{channel, category, status: Unset|Opted In|Opted Out}, ...].
    Writes through the Person spine with source='portal'. Emergency opt-outs
    are recorded but the engine ignores them by design (ADR 043)."""
    person = frappe.get_doc("Person", _my_person())
    if isinstance(consents, str):
        consents = json.loads(consents)

    if language:
        if not frappe.db.exists("Language", language):
            frappe.throw(_("Unknown language {0}.").format(language))
        person.language = language

    for item in consents or []:
        channel = item.get("channel")
        category = item.get("category")
        status = item.get("status") or "Unset"
        if (
            category not in PREF_CATEGORIES
            or status not in ("Unset", "Opted In", "Opted Out")
            or not frappe.db.exists("Communication Channel", channel)
        ):
            continue
        row = next(
            (
                r
                for r in person.consents
                if r.channel == channel and r.category == category
            ),
            None,
        )
        if row:
            if row.status != status:
                row.status = status
                row.source = "portal"
                row.recorded_on = now_datetime()
        elif status != "Unset":
            person.append(
                "consents",
                {
                    "channel": channel,
                    "category": category,
                    "status": status,
                    "source": "portal",
                    "recorded_on": now_datetime(),
                },
            )

    person.save(ignore_permissions=True)
    return get_my_communication_preferences()


# -------------------------------------------------------- portal messaging

STAFF_MESSAGING_ROLES = {"Instructor", "Seminary Manager", "Program Chair"}


def _is_messaging_staff():
    return bool(set(frappe.get_roles()) & STAFF_MESSAGING_ROLES)


@frappe.whitelist()
def get_my_messaging_scope(course=None):
    """Who the session user may message (ADR 043 portal messaging), the
    authorization source of truth — send_portal_message validates against it
    server-side. Students: instructors of course schedules they're enrolled
    in. Staff (Instructor / Seminary Manager / Program Chair): every
    instructor and student, narrowable per course schedule."""
    me = _my_person()
    if _is_messaging_staff():
        courses = _staff_course_options()
        recipients = _staff_recipients(course)
    else:
        enrolled = _student_enrolled_cs()
        courses = [
            {"value": r.name, "label": f"{r.title} ({r.academic_term})"}
            for r in enrolled
        ]
        recipients = _student_recipients(course, [r.name for r in enrolled])
    recipients = [r for r in recipients if r["person"] != me]
    return {
        "staff": _is_messaging_staff(),
        "courses": courses,
        "recipients": recipients,
    }


def _student_enrolled_cs():
    return frappe.db.sql(
        """
        SELECT DISTINCT cs.name, cs.title, cs.academic_term, cs.creation
        FROM `tabCourse Enrollment Individual` cei
        JOIN `tabCourse Schedule` cs ON cei.coursesc_ce = cs.name
        JOIN `tabStudent` s ON cei.student_ce = s.name
        WHERE s.user = %(user)s AND cei.docstatus = 1 AND cei.withdrawn = 0
        ORDER BY cs.creation DESC
        """,
        {"user": frappe.session.user},
        as_dict=True,
    )


def _student_recipients(course, enrolled_cs):
    if course:
        enrolled_cs = [cs for cs in enrolled_cs if cs == course]
    if not enrolled_cs:
        return []
    rows = frappe.db.sql(
        """
        SELECT DISTINCT i.person, i.instructor_name, cs.title
        FROM `tabCourse Schedule Instructors` csi
        JOIN `tabInstructor` i ON csi.instructor = i.name
        JOIN `tabCourse Schedule` cs ON csi.parent = cs.name
        WHERE csi.parent IN %(cs)s AND IFNULL(i.person, '') != ''
        """,
        {"cs": tuple(enrolled_cs)},
        as_dict=True,
    )
    by_person = {}
    for r in rows:
        entry = by_person.setdefault(
            r.person,
            {
                "person": r.person,
                "label": r.instructor_name,
                "kind": "Instructor",
                "courses": [],
            },
        )
        if r.title:
            entry["courses"].append(r.title)
    return list(by_person.values())


def _staff_course_options():
    rows = frappe.db.sql(
        """
        SELECT DISTINCT cs.name, cs.title, cs.academic_term
        FROM `tabCourse Schedule` cs
        JOIN `tabAcademic Term` t ON cs.academic_term = t.name
        LEFT JOIN `tabCourse Schedule Instructors` csi ON csi.parent = cs.name
        LEFT JOIN `tabInstructor` i ON csi.instructor = i.name
        WHERE t.term_end_date >= CURDATE() OR i.user = %(user)s
        ORDER BY cs.creation DESC
        LIMIT 300
        """,
        {"user": frappe.session.user},
        as_dict=True,
    )
    return [{"value": r.name, "label": f"{r.title} ({r.academic_term})"} for r in rows]


def _staff_recipients(course):
    if course:
        instructors = frappe.db.sql(
            """
            SELECT DISTINCT i.person, i.instructor_name
            FROM `tabCourse Schedule Instructors` csi
            JOIN `tabInstructor` i ON csi.instructor = i.name
            WHERE csi.parent = %(cs)s AND IFNULL(i.person, '') != ''
            """,
            {"cs": course},
            as_dict=True,
        )
        students = frappe.db.sql(
            """
            SELECT DISTINCT s.person, s.student_name
            FROM `tabCourse Enrollment Individual` cei
            JOIN `tabStudent` s ON cei.student_ce = s.name
            WHERE cei.coursesc_ce = %(cs)s AND cei.docstatus = 1
              AND cei.withdrawn = 0 AND IFNULL(s.person, '') != ''
            """,
            {"cs": course},
            as_dict=True,
        )
    else:
        instructors = frappe.get_all(
            "Instructor",
            filters={"status": "Active", "person": ("is", "set")},
            fields=["person", "instructor_name"],
        )
        students = frappe.get_all(
            "Student",
            filters={"enabled": 1, "person": ("is", "set")},
            fields=["person", "student_name"],
        )
    out = [
        {
            "person": r.person,
            "label": r.instructor_name,
            "kind": "Instructor",
            "courses": [],
        }
        for r in instructors
    ]
    seen = {r["person"] for r in out}
    out += [
        {"person": r.person, "label": r.student_name, "kind": "Student", "courses": []}
        for r in students
        if r.person not in seen
    ]
    return out


@frappe.whitelist()
def send_portal_message(
    recipients=None,
    message=None,
    subject=None,
    course=None,
    all_students=0,
    recipient=None,
):
    """Portal compose: person-to-person In-App messages, instant delivery.
    Accepts a list of recipients; all_students expands to every student in the
    sender's scope (staff only — and the scope already honors the course
    filter). Every target is validated against the scope server-side."""
    _my_person()
    if not (message or "").strip():
        frappe.throw(_("Write a message first."))

    if isinstance(recipients, str):
        recipients = json.loads(recipients)
    targets = list(recipients or [])
    if recipient:
        targets.append(recipient)

    scope = get_my_messaging_scope(course=course)
    if cint(all_students):
        if not scope["staff"]:
            frappe.throw(
                _("Only staff can message all students."), frappe.PermissionError
            )
        targets += [r["person"] for r in scope["recipients"] if r["kind"] == "Student"]

    targets = [t for t in dict.fromkeys(targets) if t]
    if not targets:
        frappe.throw(_("Pick at least one recipient."))
    allowed = {r["person"] for r in scope["recipients"]}
    blocked = [t for t in targets if t not in allowed]
    if blocked:
        frappe.throw(_("You can't message this recipient."), frappe.PermissionError)

    body = "<p>{0}</p>".format(
        frappe.utils.escape_html(message.strip()).replace("\n", "<br>")
    )
    sent = 0
    for target in targets:
        if send_message(
            channel=IN_APP_CHANNEL,
            person=target,
            subject=subject,
            message=body,
            category="Community",
            reference_doctype="Course Schedule" if course else None,
            reference_name=course,
            triggered_by=frappe.session.user,
        ):
            sent += 1
    return {"sent": sent}


# ---------------------------------------------------------------- webhooks

# Status events can only move a log forward; a late "delivered" never
# downgrades a "read".
_STATUS_RANK = {"Queued": 0, "Sending": 1, "Sent": 2, "Delivered": 3, "Read": 4}
_STATUS_ALIASES = {
    "sent": "Sent",
    "delivered": "Delivered",
    "read": "Read",
    "failed": "Failed",
    "bounced": "Bounced",
    "undelivered": "Failed",
}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook(account=None, secret=None, **kwargs):
    """Provider webhook endpoint (ADR 043):
    POST /api/method/seminary.seminary.comms.webhook?account=<Channel Provider Account>

    Verification defaults to a shared secret (settings JSON `webhook_secret`,
    sent as ?secret=, X-Webhook-Secret header, or payload field) — an account
    with no secret configured rejects everything. Adapters override
    verify_webhook / handle_webhook for provider-native signatures and payload
    shapes; the default contract accepts normalized JSON:
      {"kind": "status", "provider_message_id": "...", "status": "delivered"}
      {"kind": "inbound", "from_address": "...", "body": "...", "subject": "..."}
    """
    if not account or not frappe.db.exists("Channel Provider Account", account):
        frappe.throw(_("Unknown account."), frappe.PermissionError)
    acc = frappe.get_doc("Channel Provider Account", account)
    if not acc.enabled:
        frappe.throw(_("Account disabled."), frappe.PermissionError)
    settings = account_settings(acc)
    adapter = get_adapter(acc.provider)

    payload = _webhook_payload(kwargs)
    verify = getattr(adapter, "verify_webhook", None) or _verify_webhook_secret
    if not verify(acc, settings, secret or payload.get("secret")):
        frappe.throw(_("Webhook verification failed."), frappe.PermissionError)

    parse = getattr(adapter, "handle_webhook", None) or _parse_generic_webhook
    event = parse(payload, acc)
    if not event:
        return {"ok": True, "handled": False}
    result = _apply_webhook_event(event, acc)
    return {"ok": True, **result}


def _webhook_payload(kwargs):
    payload = {}
    request = getattr(frappe.local, "request", None)
    if request is not None:
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            payload.update(body)
    payload.update({k: v for k, v in kwargs.items() if k not in ("cmd",)})
    return payload


def _verify_webhook_secret(account, settings, provided):
    """Default verification: constant-time compare against the account's
    configured webhook_secret. No secret configured = nothing accepted."""
    import hmac

    expected = settings.get("webhook_secret")
    if not expected:
        return False
    if not provided:
        request = getattr(frappe.local, "request", None)
        if request is not None:
            provided = request.headers.get("X-Webhook-Secret")
    return bool(provided) and hmac.compare_digest(str(provided), str(expected))


def _parse_generic_webhook(payload, account):
    kind = payload.get("kind")
    if not kind:
        if payload.get("status") and payload.get("provider_message_id"):
            kind = "status"
        elif payload.get("from_address") and payload.get("body"):
            kind = "inbound"
    if kind == "status":
        status = _STATUS_ALIASES.get(str(payload.get("status", "")).strip().lower())
        if not status or not payload.get("provider_message_id"):
            return None
        return {
            "kind": "status",
            "provider_message_id": payload["provider_message_id"],
            "status": status,
        }
    if kind == "inbound":
        if not payload.get("from_address") or not payload.get("body"):
            return None
        return {
            "kind": "inbound",
            "from_address": payload["from_address"],
            "body": payload["body"],
            "subject": payload.get("subject"),
            "provider_message_id": payload.get("provider_message_id"),
        }
    return None


def _apply_webhook_event(event, account):
    if event["kind"] == "status":
        return _apply_status_event(event, account)
    if event["kind"] == "inbound":
        return _apply_inbound_event(event, account)
    return {"handled": False}


def _apply_status_event(event, account):
    log_name = frappe.db.get_value(
        "Communication Log",
        {
            "provider_message_id": event["provider_message_id"],
            "provider_account": account.name,
        },
    ) or frappe.db.get_value(
        "Communication Log", {"provider_message_id": event["provider_message_id"]}
    )
    if not log_name:
        return {"handled": False, "reason": "unknown provider_message_id"}
    log = frappe.get_doc("Communication Log", log_name)
    new_status = event["status"]
    stamp = now_datetime()

    if new_status in ("Failed", "Bounced"):
        log.db_set(
            {"status": new_status, "error": _("Reported by provider webhook.")},
            update_modified=False,
        )
    else:
        if _STATUS_RANK.get(new_status, 0) <= _STATUS_RANK.get(log.status, 0):
            return {"handled": True, "log": log.name, "noop": True}
        updates = {"status": new_status}
        if new_status == "Delivered" and not log.delivered_at:
            updates["delivered_at"] = stamp
        if new_status == "Read":
            if not log.delivered_at:
                updates["delivered_at"] = stamp
            if not log.read_at:
                updates["read_at"] = stamp
        log.db_set(updates, update_modified=False)
    _reflect_announcement(log)
    return {"handled": True, "log": log.name}


def _apply_inbound_event(event, account):
    """An incoming message: matched to a Person through their channel address
    for this account's channel; unmatched senders still land in the ledger
    with the raw from_address (ADR 043)."""
    addr = (event.get("from_address") or "").strip()
    person = _match_person_by_address(account.channel, addr)
    body = "<p>{0}</p>".format(
        frappe.utils.escape_html((event.get("body") or "").strip()).replace(
            "\n", "<br>"
        )
    )
    log = frappe.get_doc(
        {
            "doctype": "Communication Log",
            "direction": "Inbound",
            "status": "Delivered",
            "channel": account.channel,
            "provider_account": account.name,
            "person": person,
            "from_address": addr,
            "subject": event.get("subject"),
            "message": body,
            "provider_message_id": event.get("provider_message_id"),
            "triggered_by": f"webhook::{account.name}",
            "delivered_at": now_datetime(),
        }
    )
    log.insert(ignore_permissions=True)
    return {"handled": True, "log": log.name, "person": person}


def _match_person_by_address(channel, address):
    if not address:
        return None
    candidates = [address]
    if address.lower() != address:
        candidates.append(address.lower())
    for value in candidates:
        person = frappe.db.get_value(
            "Person Channel Address",
            {"parenttype": "Person", "channel": channel, "value": value},
            "parent",
        )
        if person:
            return person
    # last resort for Email: the spine's primary_email
    if channel == EMAIL_CHANNEL:
        return frappe.db.get_value("Person", {"primary_email": address.lower()})
    return None


# ----------------------------------------------------- desk conversation UI


@frappe.whitelist()
def get_person_timeline(person, limit=50):
    """The CRM-style conversation feed for a Person (desk form, ADR 044)."""
    frappe.has_permission("Communication Log", "read", throw=True)
    return frappe.get_all(
        "Communication Log",
        filters={"person": person},
        fields=[
            "name",
            "direction",
            "channel",
            "status",
            "category",
            "subject",
            "message",
            "to_address",
            "from_address",
            "triggered_by",
            "reference_doctype",
            "reference_name",
            "sent_at",
            "read_at",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=int(limit),
    )


@frappe.whitelist()
def compose_communication(
    person, channel, subject=None, message=None, template=None, send_now=1
):
    """Desk compose action ('start an email / send an SMS from the system').
    Either renders a template or takes free-form subject/message; queues
    through the normal consent/routing path and optionally delivers
    immediately instead of waiting for the cron drainer."""
    frappe.has_permission("Communication Log", "create", throw=True)
    if template:
        log = send(person, template, channel=channel, triggered_by=frappe.session.user)
    else:
        if not message:
            frappe.throw(_("Provide a message or pick a template."))
        log = send_message(
            channel=channel,
            subject=subject,
            message=message,
            person=person,
            category="Transactional",
            triggered_by=frappe.session.user,
        )
    if log and frappe.utils.cint(send_now):
        status = frappe.db.get_value("Communication Log", log, "status")
        if status == "Queued":
            deliver_now(log)
    return log


def deliver_now(log_name):
    """Deliver a single Queued log immediately (compose 'send now'). Skips the
    hourly budget — a deliberate human action, not a bulk drain."""
    account_name = frappe.db.get_value(
        "Communication Log", log_name, "provider_account"
    )
    if not account_name:
        return False
    account = frappe.get_doc("Channel Provider Account", account_name)
    return _deliver(log_name, account)


def _follow_up(log):
    responded = log.person and frappe.db.exists(
        "Communication Log",
        {"direction": "Inbound", "person": log.person, "creation": (">", log.sent_at)},
    )
    if not responded:
        if log.follow_up_template and log.person:
            send(
                log.person,
                log.follow_up_template,
                channel=log.channel,
                category=log.category,
                reference_doctype=log.reference_doctype,
                reference_name=log.reference_name,
                triggered_by=log.triggered_by,
                follow_up_of=log.name,
                dedupe_key=f"follow-up::{log.name}",
            )
        else:
            assignee = (
                log.triggered_by
                if log.triggered_by and frappe.db.exists("User", log.triggered_by)
                else None
            )
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "description": _(
                        "No response to '{0}' ({1}) after {2} day(s). Follow up manually."
                    ).format(
                        log.subject or log.name,
                        log.to_address,
                        log.follow_up_after_days,
                    ),
                    "reference_type": "Communication Log",
                    "reference_name": log.name,
                    "allocated_to": assignee,
                }
            ).insert(ignore_permissions=True)
    log.db_set("follow_up_done", 1, update_modified=False)
