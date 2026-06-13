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

import base64
import json
import mimetypes
import re
from urllib.parse import unquote

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime

ADAPTER_HOOK = "communication_channel_providers"
IN_APP_CHANNEL = "In-App"
EMAIL_CHANNEL = "Email"
PRINT_CHANNEL = "Print"
VOICE_CHANNEL = "Voice"
SMS_CHANNEL = "SMS"
WHATSAPP_CHANNEL = "WhatsApp"
TELEGRAM_CHANNEL = "Telegram"
# Channels that don't deliver to an address — landing in the ledger (or, for
# Print, the generated document) is the delivery, so no address is resolved.
ADDRESSLESS_CHANNELS = {IN_APP_CHANNEL, PRINT_CHANNEL}
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


class PrintAdapter:
    """The Communication Log holds the rendered letter snapshot (log.message).
    There is no carrier, so like In-App the row itself is the delivery. The
    printable artifact is the consolidated Letters PDF on the Seminary
    Announcement (all recipients, one per page), not a PDF per log."""

    final_status = "Delivered"
    instant = True

    def send(self, log, account):
        if not log.message:
            raise ValueError("Print log has no rendered letter")
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
    # Physical mail carries no opt-in requirement — Print is never consent-blocked.
    if channel == PRINT_CHANNEL:
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
    if rows:
        return rows[0].value
    # Voice calls reach the same number as SMS — fall back to the SMS address
    # (the primary mobile mirrors there) so Voice works without a separate one.
    if channel == VOICE_CHANNEL:
        return resolve_address(person_doc, SMS_CHANNEL, category)
    return None


def reachability(person_doc, channel, category, *, email=None):
    """Would a queued send on this channel actually deliver, and if not, why?
    Returns 'ok' | 'opted_out' | 'no_address'. Mirrors the routing checks in
    send_message so the announcement preview and the email/portal fallback
    agree with what dispatch will do. `email` is the known address for the
    Email channel when the spine has no Person (announcement recipients are
    resolved by email)."""
    if person_doc and consent_blocks(person_doc, channel, category):
        return "opted_out"
    if channel == IN_APP_CHANNEL:
        return "ok" if person_doc else "no_address"
    if channel == PRINT_CHANNEL:
        return "ok"  # addressless: a PDF can always be generated
    address = email if (channel == EMAIL_CHANNEL and email) else None
    if not address and person_doc:
        address = resolve_address(person_doc, channel, category)
    return "ok" if address else "no_address"


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
    media_url=None,
    reference_doctype=None,
    reference_name=None,
    triggered_by=None,
    scheduled_at=None,
    dedupe_key=None,
    awaiting_response=0,
    follow_up_after_days=0,
    follow_up_template=None,
    follow_up_of=None,
    in_reply_to=None,
    attach_files=None,
):
    """Queue a pre-rendered message (the raw path — used by the Seminary
    Announcement port, where content is authored, not templated).

    For external channels embedded files are flipped public so the recipient's
    client can fetch them without a session. For In-App (portal inbox) they stay
    private and are attached to the per-recipient log instead, so Frappe's
    /private/files ACL serves them only to the recipient/sender (ADR 043)."""
    if channel != IN_APP_CHANNEL:
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
        media_url=media_url,
        in_reply_to=in_reply_to,
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

    if not values["to_address"] and person_doc and channel not in ADDRESSLESS_CHANNELS:
        values["to_address"] = resolve_address(person_doc, channel, category)
    if not values["to_address"] and channel not in ADDRESSLESS_CHANNELS:
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
    if log_name and channel == IN_APP_CHANNEL:
        _attach_inapp_files(log_name, message, attach_files)
    if log_name and not scheduled_at:
        _maybe_deliver_instant(log_name, account)
    return log_name


def _attach_inapp_files(log_name, message, attach_files=None):
    """Attach every private file an In-App message references — explicit
    attachments plus inline images in the body — to the per-recipient
    Communication Log, reusing the uploaded bytes (create_attachment_copy).
    The recipient/sender can then download via Frappe's /private/files ACL
    because they can read their own log; nothing is made public."""
    urls = set(attach_files or [])
    urls |= set(re.findall(r"/private/files/[^\"'\s>)]+", message or ""))
    for url in urls:
        base = unquote(url.split("?")[0])
        name = frappe.db.get_value("File", {"file_url": base}, "name")
        if not name:
            continue
        if frappe.db.exists(
            "File",
            {
                "file_url": base,
                "attached_to_doctype": "Communication Log",
                "attached_to_name": log_name,
            },
        ):
            continue
        try:
            source = frappe.get_doc("File", name)
            source.create_attachment_copy(
                "Communication Log", log_name, ignore_permissions=True
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"Could not attach {url} to {log_name}"
            )


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
    """Message content SENT over an EXTERNAL channel (Email): the recipient's
    client fetches embedded images with no Frappe session, so an embedded
    private upload would 403. Flip the referenced Files public and rewrite their
    URLs in the snapshot. NOT used for In-App — those stay private and are
    served by doc-permission (see _attach_inapp_files / _privatize_embedded_files)."""
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


def _privatize_embedded_files(message):
    """Defense-in-depth for In-App compose: if an inline image was uploaded
    public (the editor's default before the private-upload fix), flip the
    sender's OWN file private and rewrite its URL, so portal-message content is
    never publicly reachable regardless of the client. Scoped to files owned by
    the current user so we never re-privatize a shared/system public asset."""
    if not message or "/files/" not in message:
        return message
    for file_url in set(re.findall(r"(?<!/private)/files/[^\"'\s>)]+", message)):
        base = unquote(file_url.split("?")[0])
        row = frappe.db.get_value(
            "File", {"file_url": base, "is_private": 0}, ["name", "owner"], as_dict=True
        )
        if not row or row.owner != frappe.session.user:
            continue
        try:
            file_doc = frappe.get_doc("File", row.name)
            file_doc.is_private = 1
            file_doc.save(ignore_permissions=True)
            message = message.replace(file_url, file_doc.file_url)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"Could not privatize embedded file {file_url}"
            )
    return message


def _inline_file_images(html):
    """Embed referenced site files (letter-head logos, message images) as
    base64 data URIs so the PDF renderer never has to fetch them over HTTP —
    the usual cause of missing letter-head logos (wrong host/port, private-file
    auth, spaces in the filename). Reads bytes straight off disk, so it works
    for both public and private files."""
    if not html:
        return html

    def repl(match):
        opening, src = match.group(1), match.group(2)
        # src may be relative (/files/x.png) or absolute (http://host/files/x.png)
        path_match = re.search(r"/(?:private/)?files/[^\"']*", src)
        if not path_match:
            return match.group(0)
        raw = path_match.group(0)
        path = unquote(raw.split("?")[0])
        name = frappe.db.get_value("File", {"file_url": path}, "name") or (
            frappe.db.get_value("File", {"file_url": raw.split("?")[0]}, "name")
        )
        if not name:
            return match.group(0)
        try:
            content = frappe.get_doc("File", name).get_content()
        except Exception:
            return match.group(0)
        if isinstance(content, str):
            content = content.encode()
        mime = mimetypes.guess_type(path)[0] or "image/png"
        b64 = base64.b64encode(content).decode()
        return f"{opening}data:{mime};base64,{b64}"

    return re.sub(r'(src=["\'])([^"\']*?/(?:private/)?files/[^"\']*)', repl, html)


# Editors constrain images to their container on screen but store no width cap,
# so wkhtmltopdf renders them at full native size (gigantic, multi-page). Cap to
# the page width while preserving aspect ratio and any smaller explicit size.
_PDF_STYLE = (
    "<style>"
    "img{max-width:100%!important;height:auto!important;}"
    "table{max-width:100%!important;}"
    "</style>"
)


def pdf_html(html):
    """Prepare authored HTML for PDF rendering: inline referenced site images
    as data URIs (no HTTP fetch) and cap image size to the page width."""
    return _PDF_STYLE + _inline_file_images(html)


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
    """Effective provider config for an account (typed credential fields with
    secrets decrypted, overlaid on the raw Extra Settings JSON). Accepts a doc,
    a name, or the lightweight dict dispatch() carries — the latter two are
    loaded to a doc so Password fields decrypt."""
    # frappe._dict (what dispatch carries) returns None for missing attrs rather
    # than raising, so probe for a *callable* get_config, not just its presence.
    get_config = getattr(account, "get_config", None)
    if callable(get_config):
        return get_config()
    name = account if isinstance(account, str) else account.name
    return frappe.get_doc("Channel Provider Account", name).get_config()


# ------------------------------------------------- announcement reflection


def _reflect_announcement(log):
    """Stage-one port glue: mirror log outcomes onto Seminary Announcement
    Recipient rows so the desk grid and portal query keep working.

    A recipient can now receive several channels (Email, In-App, SMS, …). The
    grid has one row per recipient, so we roll the channels up monotonically:
    "Sent wins" — any channel reaching Sent/Delivered/Read marks the recipient
    Sent; we only record Failed when the row is not already Sent. The rule is
    order-independent, so out-of-order webhook/dispatch events converge."""
    if log.reference_doctype != "Seminary Announcement" or not log.reference_name:
        return
    success = log.status in ("Sent", "Delivered", "Read")
    failed = log.status in ("Failed", "Cancelled")
    if not (success or failed):
        return
    row = _announcement_recipient_row(log)
    if not row:
        return
    current = frappe.db.get_value(
        "Seminary Announcement Recipient", row, "delivery_status"
    )
    if current == "Sent":
        return  # Sent wins — never downgraded by a later channel failure.
    frappe.db.set_value(
        "Seminary Announcement Recipient",
        row,
        {
            "delivery_status": "Sent" if success else "Failed",
            "error": None if success else (log.error or None),
        },
        update_modified=False,
    )


def _announcement_recipient_row(log):
    """Find the recipient grid row for an announcement log across any channel.

    The recipient email is encoded in the per-recipient idempotency key
    (``seminary-announcement::<name>::<email>::<channel>``), so non-Email
    channels — whose to_address is a phone number or chat id — still map back
    to their row. Falls back to to_address for older Email-only logs."""
    email = None
    key = log.idempotency_key or ""
    if key.startswith("seminary-announcement::"):
        parts = key.split("::")
        if len(parts) >= 4:
            email = parts[2]
    if not email:
        email = (log.to_address or "").lower()
    if not email:
        return None
    return frappe.db.get_value(
        "Seminary Announcement Recipient",
        {"parent": log.reference_name, "email": email},
        "name",
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
def get_my_unread_count():
    """Lightweight unread count for the portal sidebar badge (same definition
    as get_my_inbox's unread)."""
    person = _my_person()
    return frappe.db.count(
        "Communication Log",
        {
            "person": person,
            "direction": "Outbound",
            "status": ("in", ("Sent", "Delivered")),
            "read_at": ("is", "not set"),
        },
    )


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
        "mailing_address": {
            "address_line_1": person.address_line_1,
            "address_line_2": person.address_line_2,
            "city": person.city,
            "state": person.state,
            "pincode": person.pincode,
            "country": person.country,
        },
        "countries": frappe.get_all("Country", pluck="name", order_by="name asc"),
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
def update_my_communication_preferences(
    language=None, consents=None, mailing_address=None
):
    """consents: [{channel, category, status: Unset|Opted In|Opted Out}, ...].
    mailing_address: {address_line_1, address_line_2, city, state, pincode,
    country}. Writes through the Person spine with source='portal'. Emergency
    opt-outs are recorded but the engine ignores them by design (ADR 043)."""
    person = frappe.get_doc("Person", _my_person())
    if isinstance(consents, str):
        consents = json.loads(consents)
    if isinstance(mailing_address, str):
        mailing_address = json.loads(mailing_address)

    if mailing_address is not None:
        for field in ("address_line_1", "address_line_2", "city", "state", "pincode"):
            person.set(field, (mailing_address.get(field) or "").strip() or None)
        country = (mailing_address.get("country") or "").strip()
        # Country also drives provider routing — only set a valid one, never clear.
        if country and frappe.db.exists("Country", country):
            person.country = country

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
    server-side.

    Driven by the Portal Messaging Rules configured on Seminary Settings
    (sender role -> audience). When no rules are configured it falls back to
    the built-in defaults: students reach the instructors of course schedules
    they're enrolled in; staff (Instructor / Seminary Manager / Program Chair)
    reach every instructor and student, narrowable per course schedule.

    Each recipient carries a `group` (display heading for the compose picker)
    and a `kind` (Instructor / Student / Role / User / Support — the
    all_students expansion and existing checks key off `kind`)."""
    me = _my_person()
    staff = _is_messaging_staff()
    settings = frappe.get_cached_doc("Seminary Settings")
    rules = [r for r in (settings.portal_messaging_rules or []) if r.enabled]

    if not rules:
        recipients = _legacy_recipients(course, staff)
    else:
        my_roles = set(frappe.get_roles())
        by_person = {}
        for rule in rules:
            if rule.sender_role not in my_roles:
                continue
            group = (rule.group_label or "").strip() or _default_group(rule)
            for rec in _resolve_audience(rule, course, staff, settings):
                _merge_recipient(by_person, rec, group)
        recipients = list(by_person.values())

    if staff:
        courses = _staff_course_options()
    else:
        courses = [
            {"value": r.name, "label": f"{r.title} ({r.academic_term})"}
            for r in _student_enrolled_cs()
        ]
    recipients = [r for r in recipients if r["person"] != me]
    return {"staff": staff, "courses": courses, "recipients": recipients}


def _legacy_recipients(course, staff):
    """Built-in messaging policy used when a seminary has configured no Portal
    Messaging Rules (and for pre-seed installs). Mirrors the original ADR 043
    behavior verbatim, backfilling the display `group`."""
    if staff:
        recipients = _staff_recipients(course)
    else:
        recipients = _student_recipients(
            course, [r.name for r in _student_enrolled_cs()]
        )
    for r in recipients:
        r["group"] = "Instructors" if r["kind"] == "Instructor" else "Students"
    return recipients


# ----- rule-driven audience resolution

_AUDIENCE_GROUP = {
    "Course Instructors": "Instructors",
    "All Instructors": "Instructors",
    "Course Students": "Students",
    "All Students": "Students",
    "Support User": "Support",
    "Specific User": "Direct",
}


def _default_group(rule):
    if rule.audience == "Role":
        return rule.audience_role or "Other"
    return _AUDIENCE_GROUP.get(rule.audience, "Other")


def _merge_recipient(by_person, rec, group):
    """Dedupe by person across rules: first rule that reaches a person wins the
    display group; later rules only union the per-course annotations."""
    existing = by_person.get(rec["person"])
    if existing:
        for c in rec.get("courses", []):
            if c not in existing["courses"]:
                existing["courses"].append(c)
        return
    rec = dict(rec)
    rec["group"] = group
    rec.setdefault("courses", [])
    by_person[rec["person"]] = rec


def _resolve_audience(rule, course, staff, settings):
    audience = rule.audience
    if audience == "Course Instructors":
        return _student_recipients(course, [r.name for r in _student_enrolled_cs()])
    if audience == "Course Students":
        return _course_student_recipients(course, staff)
    if audience == "All Instructors":
        return _all_instructor_recipients(course) if staff else []
    if audience == "All Students":
        return _all_student_recipients(course) if staff else []
    if audience == "Role":
        return _role_recipients(rule.audience_role)
    if audience == "Specific User":
        return _user_recipient(rule.audience_user, "User")
    if audience == "Support User":
        return _user_recipient(settings.support_user, "Support")
    return []


def _all_instructor_recipients(course=None):
    """Every active instructor, or — when a course filter is set — just the
    instructors of that Course Schedule (preserves the staff course filter)."""
    if course:
        rows = frappe.db.sql(
            """
            SELECT DISTINCT i.person, i.instructor_name
            FROM `tabCourse Schedule Instructors` csi
            JOIN `tabInstructor` i ON csi.instructor = i.name
            WHERE csi.parent = %(cs)s AND IFNULL(i.person, '') != ''
            """,
            {"cs": course},
            as_dict=True,
        )
    else:
        rows = frappe.get_all(
            "Instructor",
            filters={"status": "Active", "person": ("is", "set")},
            fields=["person", "instructor_name"],
        )
    return [
        {
            "person": r.person,
            "label": r.instructor_name,
            "kind": "Instructor",
            "courses": [],
        }
        for r in rows
    ]


def _all_student_recipients(course=None):
    """Every enabled student, or — when a course filter is set — just the
    students enrolled in that Course Schedule."""
    if course:
        rows = frappe.db.sql(
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
        rows = frappe.get_all(
            "Student",
            filters={"enabled": 1, "person": ("is", "set")},
            fields=["person", "student_name"],
        )
    return [
        {"person": r.person, "label": r.student_name, "kind": "Student", "courses": []}
        for r in rows
    ]


def _course_student_recipients(course, staff):
    """Students enrolled in the sender's course schedules — the schedules a
    staff member teaches, or a student's own enrolled schedules — honoring the
    course filter."""
    if staff:
        rows = frappe.db.sql(
            """
            SELECT DISTINCT cs.name
            FROM `tabCourse Schedule` cs
            JOIN `tabCourse Schedule Instructors` csi ON csi.parent = cs.name
            JOIN `tabInstructor` i ON csi.instructor = i.name
            WHERE i.user = %(user)s
            """,
            {"user": frappe.session.user},
            as_dict=True,
        )
        cs_names = [r.name for r in rows]
    else:
        cs_names = [r.name for r in _student_enrolled_cs()]
    if course:
        cs_names = [c for c in cs_names if c == course]
    if not cs_names:
        return []
    rows = frappe.db.sql(
        """
        SELECT DISTINCT s.person, s.student_name, cs.title
        FROM `tabCourse Enrollment Individual` cei
        JOIN `tabStudent` s ON cei.student_ce = s.name
        JOIN `tabCourse Schedule` cs ON cei.coursesc_ce = cs.name
        WHERE cei.coursesc_ce IN %(cs)s AND cei.docstatus = 1
          AND cei.withdrawn = 0 AND IFNULL(s.person, '') != ''
        """,
        {"cs": tuple(cs_names)},
        as_dict=True,
    )
    by_person = {}
    for r in rows:
        entry = by_person.setdefault(
            r.person,
            {
                "person": r.person,
                "label": r.student_name,
                "kind": "Student",
                "courses": [],
            },
        )
        if r.title:
            entry["courses"].append(r.title)
    return list(by_person.values())


def _role_recipients(role):
    """Persons whose enabled User holds `role`. Single join (no find_person
    N+1); Person-less role holders are silently skipped since messages target a
    Person."""
    if not role:
        return []
    rows = frappe.db.sql(
        """
        SELECT DISTINCT p.name AS person, p.full_name AS label
        FROM `tabHas Role` hr
        JOIN `tabUser` u ON hr.parent = u.name
        JOIN `tabPerson` p ON p.user = u.name
        WHERE hr.parenttype = 'User' AND hr.role = %(role)s
          AND u.enabled = 1 AND u.name NOT IN ('Administrator', 'Guest')
        """,
        {"role": role},
        as_dict=True,
    )
    return [
        {"person": r.person, "label": r.label, "kind": "Role", "courses": []}
        for r in rows
    ]


def _user_recipient(user, kind):
    if not user:
        return []
    from seminary.seminary.person import find_person

    person = find_person(user=user)
    if not person:
        return []
    label = (
        frappe.db.get_value("Person", person, "full_name")
        or frappe.db.get_value("User", user, "full_name")
        or user
    )
    return [{"person": person, "label": label, "kind": kind, "courses": []}]


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
    attachments=None,
):
    """Portal compose: person-to-person In-App messages, instant delivery.
    Accepts a list of recipients; all_students expands to every student in the
    sender's scope (staff only — and the scope already honors the course
    filter). Every target is validated against the scope server-side. The body
    is rich text (sanitized server-side); attachments and inline images stay
    PRIVATE and are attached to each recipient's log, so only the recipient and
    sender can download them via Frappe's /private/files ACL (ADR 043)."""
    _my_person()
    if not frappe.utils.strip_html(message or "").strip():
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

    if isinstance(attachments, str):
        attachments = json.loads(attachments)
    attachments = attachments or []
    attach_files = [a["file_url"] for a in attachments if a.get("file_url")]

    body = frappe.utils.sanitize_html(message)
    body = _privatize_embedded_files(body)  # belt-and-suspenders on inline images
    body += _attachment_html(attachments)
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
            attach_files=attach_files,
        ):
            sent += 1
    return {"sent": sent}


def _attachment_html(attachments):
    """A trusted download-link block appended to a message body. The files stay
    PRIVATE; _attach_inapp_files attaches them to each recipient's log so the
    /private/files links resolve only for the recipient and sender."""
    if not attachments:
        return ""
    if isinstance(attachments, str):
        attachments = json.loads(attachments)
    items = "".join(
        '<li><a href="{0}">{1}</a></li>'.format(
            frappe.utils.escape_html(a.get("file_url", "")),
            frappe.utils.escape_html(
                a.get("file_name") or a.get("file_url") or _("Attachment")
            ),
        )
        for a in (attachments or [])
        if a.get("file_url")
    )
    if not items:
        return ""
    return "<hr><p><b>{0}</b></p><ul>{1}</ul>".format(_("Attachments"), items)


@frappe.whitelist()
def reply_portal_message(in_reply_to, message):
    """Portal reply: answer a received In-App message, threaded to it. Replies
    go to the original sender (must be within the replier's messaging scope)."""
    me = _my_person()
    if not (message or "").strip():
        frappe.throw(_("Write a message first."))
    original = frappe.db.get_value(
        "Communication Log",
        in_reply_to,
        ["person", "triggered_by"],
        as_dict=True,
    )
    if not original or original.person != me:
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    from seminary.seminary.person import find_person

    sender_person = find_person(user=original.triggered_by)
    if not sender_person or sender_person == me:
        frappe.throw(_("This message can't be replied to."))
    if sender_person not in {
        r["person"] for r in get_my_messaging_scope()["recipients"]
    }:
        frappe.throw(_("You can't message this recipient."), frappe.PermissionError)

    body = "<p>{0}</p>".format(
        frappe.utils.escape_html(message.strip()).replace("\n", "<br>")
    )
    log = send_message(
        channel=IN_APP_CHANNEL,
        person=sender_person,
        message=body,
        category="Community",
        triggered_by=frappe.session.user,
        in_reply_to=in_reply_to,
    )
    return {"log": log}


@frappe.whitelist()
def contact_instructor(instructor, channel, message, subject=None):
    """Portal contact: a logged message to an instructor on a chosen channel
    (ADR 042/043) — the icons on Course Detail route here instead of opening the
    instructor's personal app, so the conversation lives in the Communication
    Log. Authorized two ways: the instructor must be within the sender's
    `get_my_messaging_scope` (a student reaches only the instructors of courses
    they're enrolled in) and the instructor's own `students_may_contact` toggle
    must allow it (staff are always allowed). In-App lands in the inbox; an
    external channel routes through its provider account when one is configured."""
    _my_person()
    if not frappe.utils.strip_html(message or "").strip():
        frappe.throw(_("Write a message first."))

    info = frappe.db.get_value(
        "Instructor",
        instructor,
        ["person", "students_may_contact"],
        as_dict=True,
    )
    if not info or not info.person:
        frappe.throw(_("Instructor not found."), frappe.DoesNotExistError)

    if not _is_messaging_staff() and not info.students_may_contact:
        frappe.throw(
            _("This instructor isn't accepting student messages."),
            frappe.PermissionError,
        )
    if info.person not in {r["person"] for r in get_my_messaging_scope()["recipients"]}:
        frappe.throw(_("You can't message this instructor."), frappe.PermissionError)

    if not frappe.db.get_value(
        "Communication Channel",
        {"name": channel, "enabled": 1, "portal_contactable": 1},
    ):
        frappe.throw(_("This channel isn't available."))

    # Pre-check the provider so a missing external account fails friendly here,
    # not with send_message's generic "No enabled Channel Provider Account".
    if channel != IN_APP_CHANNEL:
        if not pick_account(channel):
            frappe.throw(_("This channel isn't available right now."))
        person_doc = frappe.get_doc("Person", info.person)
        if not resolve_address(person_doc, channel):
            frappe.throw(_("This instructor has no {0} address.").format(channel))

    # Email needs a subject; default one naming the sender so the recipient
    # knows who reached out (the send goes out from the seminary's address).
    if channel == EMAIL_CHANNEL and not (subject or "").strip():
        sender = frappe.utils.get_fullname(frappe.session.user)
        subject = (
            _("New message from {0}").format(sender)
            if sender
            else _("New message from the portal")
        )

    body = "<p>{0}</p>".format(
        frappe.utils.escape_html(message.strip()).replace("\n", "<br>")
    )
    log = send_message(
        channel=channel,
        person=info.person,
        subject=subject,
        message=body,
        category="Community",
        reference_doctype="Instructor",
        reference_name=instructor,
        triggered_by=frappe.session.user,
    )
    return {"log": log}


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


# ------------------------------------------------- desk communication inbox
#
# A *personal* inbox for the logged-in user (like the portal inbox, with two
# panes + reply). Conversations are grouped by the OTHER party relative to the
# viewer — not by the log's `person` (the addressee) — so a message sent to me
# appears under its sender, not under me. Broadcast announcements are excluded;
# they're not conversations (see the Person Conversation tab / Communication Log
# list for the full ledger).

NON_CONVERSATION_REF = "Seminary Announcement"


def _inbox_viewer():
    from seminary.seminary.person import find_person

    return find_person(user=frappe.session.user)


def _counterparty(log, me_user, cache):
    """The other party in a log relative to the viewer: the recipient when the
    viewer sent it, else the sender's Person."""
    if log.triggered_by == me_user:
        return log.person
    if log.triggered_by not in cache:
        from seminary.seminary.person import find_person

        cache[log.triggered_by] = find_person(user=log.triggered_by)
    return cache[log.triggered_by]


@frappe.whitelist()
def get_inbox_conversations(scope="all", limit=50):
    """The viewer's conversations, grouped by the other party, most-recent
    first. scope='unread' keeps only those with messages to the viewer not yet
    read. Broadcast announcements are excluded."""
    frappe.has_permission("Communication Log", "read", throw=True)
    me_user = frappe.session.user
    me = _inbox_viewer()
    if not me:
        return []
    logs = frappe.db.sql(
        """
        SELECT name, person, triggered_by, channel, subject, message,
               read_at, creation
        FROM `tabCommunication Log`
        WHERE (person = %(me)s OR triggered_by = %(user)s)
          AND IFNULL(reference_doctype, '') != %(ref)s
        ORDER BY creation DESC
        LIMIT 2000
        """,
        {"me": me, "user": me_user, "ref": NON_CONVERSATION_REF},
        as_dict=True,
    )
    cache, convos, order = {}, {}, []
    for log in logs:
        other = _counterparty(log, me_user, cache)
        if not other or other == me:
            continue
        if other not in convos:
            convos[other] = {"last": log, "unread": 0}
            order.append(other)
        if log.person == me and log.triggered_by != me_user and not log.read_at:
            convos[other]["unread"] += 1

    names = (
        dict(
            frappe.get_all(
                "Person",
                filters=[["name", "in", order]],
                fields=["name", "full_name"],
                as_list=True,
            )
        )
        if order
        else {}
    )
    rows = []
    for other in order:
        info = convos[other]
        if scope == "unread" and not info["unread"]:
            continue
        last = info["last"]
        rows.append(
            {
                "person": other,
                "person_name": names.get(other) or other,
                "unread": info["unread"],
                "last_at": last.creation,
                "last_channel": last.channel,
                "last_mine": last.triggered_by == me_user,
                "snippet": (
                    last.subject or frappe.utils.strip_html(last.message or "")
                )[:80],
            }
        )
    return rows[: int(limit)]


@frappe.whitelist()
def get_conversation(person, limit=200):
    """The thread between the viewer and `person`, oldest first. Each message
    carries `mine` (the viewer sent it) for chat-bubble sides."""
    frappe.has_permission("Communication Log", "read", throw=True)
    me_user = frappe.session.user
    me = _inbox_viewer()
    if not me:
        frappe.throw(_("No Person is linked to your account."))
    other_user = frappe.db.get_value("Person", person, "user")
    messages = frappe.db.sql(
        """
        SELECT name, channel, status, category, subject, message, to_address,
               from_address, triggered_by, sent_at, read_at, creation
        FROM `tabCommunication Log`
        WHERE IFNULL(reference_doctype, '') != %(ref)s
          AND (
                (person = %(me)s AND triggered_by = %(other_user)s)
             OR (person = %(other)s AND triggered_by = %(me_user)s)
          )
        ORDER BY creation ASC
        LIMIT %(limit)s
        """,
        {
            "me": me,
            "other": person,
            "other_user": other_user,
            "me_user": me_user,
            "ref": NON_CONVERSATION_REF,
            "limit": int(limit),
        },
        as_dict=True,
    )
    for m in messages:
        m["mine"] = m.triggered_by == me_user
    return {
        "person": person,
        "person_name": frappe.db.get_value("Person", person, "full_name") or person,
        "messages": messages,
    }


@frappe.whitelist()
def mark_conversation_read(person):
    """Mark messages the viewer received from `person` as read."""
    frappe.has_permission("Communication Log", "read", throw=True)
    me = _inbox_viewer()
    other_user = frappe.db.get_value("Person", person, "user")
    if not me or not other_user:
        return False
    frappe.db.sql(
        """
        UPDATE `tabCommunication Log`
        SET read_at = %(now)s,
            status = CASE WHEN status IN ('Sent', 'Delivered') THEN 'Read' ELSE status END
        WHERE person = %(me)s AND triggered_by = %(other_user)s AND read_at IS NULL
        """,
        {"now": now_datetime(), "me": me, "other_user": other_user},
    )
    return True


@frappe.whitelist()
def reply_in_conversation(person, message, in_reply_to=None, channel=None):
    """Reply to `person`, threaded to the message it answers. Person-to-person
    desk messages go In-App by default (or the replied-to message's channel)."""
    frappe.has_permission("Communication Log", "create", throw=True)
    if not (message or "").strip():
        frappe.throw(_("Write a reply first."))
    if not channel and in_reply_to:
        channel = frappe.db.get_value("Communication Log", in_reply_to, "channel")
    channel = channel or IN_APP_CHANNEL
    body = "<p>{0}</p>".format(
        frappe.utils.escape_html(message.strip()).replace("\n", "<br>")
    )
    log = send_message(
        channel=channel,
        person=person,
        message=body,
        category="Community",
        triggered_by=frappe.session.user,
        in_reply_to=in_reply_to,
    )
    if log and frappe.db.get_value("Communication Log", log, "status") == "Queued":
        deliver_now(log)
    mark_conversation_read(person)
    return {"log": log, "channel": channel}


@frappe.whitelist()
def get_inbox_unread_count():
    """Unread conversation messages to the viewer (desk inbox badge)."""
    frappe.has_permission("Communication Log", "read", throw=True)
    me = _inbox_viewer()
    if not me:
        return 0
    return frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabCommunication Log`
        WHERE person = %(me)s AND triggered_by != %(user)s
          AND direction = 'Outbound' AND read_at IS NULL
          AND IFNULL(reference_doctype, '') != %(ref)s
        """,
        {"me": me, "user": frappe.session.user, "ref": NON_CONVERSATION_REF},
    )[0][0]


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
