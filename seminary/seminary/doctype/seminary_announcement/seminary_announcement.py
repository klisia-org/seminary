import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime, strip_html

from seminary.seminary.doctype.seminary_announcement.announcement_recipients import (
    resolve_recipients,
)

# Channels whose body is the authored rich-text message (Print is a generated
# PDF letter, so it gets the full message too); everything else gets the
# plain-text Short Message (or the message stripped to text).
RICH_CHANNELS = {"Email", "In-App", "Print"}
IN_APP_CHANNEL = "In-App"
EMAIL_CHANNEL = "Email"
PRINT_CHANNEL = "Print"
VOICE_CHANNEL = "Voice"
DEFAULT_CHANNELS = ["Email", "In-App"]
# Channels that don't need a Person to address (Email uses the recipient's
# email; Print generates a PDF for anyone).
NO_PERSON_REQUIRED = {"Email", "Print"}
# Channels the "Email + In-App fallback" reaches when a recipient can't be
# reached on any selected channel.
FALLBACK_CHANNELS = ["Email", "In-App"]


class SeminaryAnnouncement(Document):

    def validate(self):
        self._validate_audience_selected()
        self._validate_term_for_audience()
        self._validate_custom_filter_fields()
        self._validate_channels()
        self._validate_message_bodies()
        self._validate_templates()
        self._normalize_message_images()

    def before_submit(self):
        resolved = resolve_recipients(self)
        if not resolved:
            frappe.throw(_("No recipients matched the selected audience."))

        self.set("recipients", [])
        for r in resolved:
            self.append(
                "recipients",
                {
                    "party_type": r["party_type"],
                    "party": r.get("party"),
                    "party_name": r.get("party_name"),
                    "email": r["email"],
                    "user": r.get("user"),
                    "delivery_status": "Pending",
                },
            )
        self.recipient_count = len(resolved)
        self.status = "Queued"

    def on_submit(self):
        scheduled = (
            get_datetime(self.scheduled_datetime) if self.scheduled_datetime else None
        )
        if scheduled and scheduled > now_datetime():
            return

        frappe.enqueue(
            "seminary.seminary.doctype.seminary_announcement.seminary_announcement.send_announcement",
            queue="long",
            enqueue_after_commit=True,
            announcement=self.name,
        )

    def _validate_audience_selected(self):
        has_courses = bool(self.courses and len(self.courses) > 0)
        has_custom = bool(self.custom_filter_doctype)
        if not (
            self.audience_students_enrolled
            or self.audience_instructors_teaching
            or self.audience_alumni
            or has_courses
            or has_custom
        ):
            frappe.throw(
                _(
                    "Select at least one audience: enrolled students, teaching "
                    "instructors, alumni, specific course schedules, or a custom "
                    "filter."
                )
            )

    def _validate_term_for_audience(self):
        """Term-scoped audiences need a term; alumni-only / custom-only don't."""
        term_scoped = (
            self.audience_students_enrolled
            or self.audience_instructors_teaching
            or bool(self.courses and len(self.courses) > 0)
        )
        if term_scoped and not self.academic_term:
            frappe.throw(
                _(
                    "Academic Term is required when the audience includes enrolled "
                    "students, teaching instructors, or specific course schedules."
                )
            )

    def _validate_channels(self):
        """Every selected channel must have an enabled provider account, so
        authors get one clear error at submit instead of per-recipient failures."""
        from seminary.seminary import comms

        for channel in self._selected_channels():
            if not comms.pick_account(channel):
                frappe.throw(
                    _(
                        "No enabled Channel Provider Account is configured for "
                        "channel {0}. Configure one before sending over it."
                    ).format(channel)
                )

    def _validate_templates(self):
        """Catch personalization problems at save time, before a send.
        Available tokens: {{ recipient.first_name }}, {{ recipient.last_name }},
        {{ recipient.name }}, {{ recipient.email }}, {{ person.* }}.

        Frappe's Jinja inlines unknown-key errors into the output instead of
        raising, so we both catch exceptions (syntax) and scan the rendered
        sample for the 'no such element' marker (a bad token like
        {{ recipient.first }})."""
        sample = _sample_context()
        for field in ("subject", "message", "short_message"):
            val = self.get(field)
            if not val or ("{{" not in val and "{%" not in val):
                continue
            label = _(self.meta.get_label(field))
            try:
                rendered = frappe.render_template(val, sample)
            except Exception as e:
                frappe.throw(_("Personalization error in {0}: {1}").format(label, e))
            if "no such element" in (rendered or ""):
                frappe.throw(
                    _(
                        "Unknown personalization token in {0}. Available tokens: {1}."
                    ).format(label, RECIPIENT_TOKENS)
                )

    def _normalize_message_images(self):
        """Make embedded message images render everywhere: flip private uploads
        public and rewrite absolute same-site URLs to relative (an absolute
        host can break Desk display and PDF rendering)."""
        if not self.message:
            return
        from seminary.seminary import comms

        msg = comms._publish_embedded_files(self.message)
        msg = re.sub(
            r'(src=["\'])https?://[^"\']*?(/(?:private/)?files/)', r"\1\2", msg
        )
        if msg != self.message:
            self.message = msg

    def _validate_message_bodies(self):
        """Require the body each selected channel actually uses: the rich
        Message for Email / In-App, and a short body (Short Message, or the
        Message stripped to text) for SMS / WhatsApp / Telegram."""
        channels = self._selected_channels()
        has_rich = any(c in RICH_CHANNELS for c in channels)
        has_short = any(c not in RICH_CHANNELS for c in channels)
        if has_rich and not (self.message or "").strip():
            frappe.throw(_("Message is required for Email / In-App."))
        if (
            has_short
            and not (self.short_message or "").strip()
            and not (self.message or "").strip()
        ):
            frappe.throw(
                _(
                    "Short Message is required for SMS / WhatsApp / Telegram "
                    "(or fill in Message to derive it)."
                )
            )

    def _selected_channels(self):
        """Selected channel names, defaulting to Email + In-App when none are
        chosen (backward-compatible with announcements created before channels)."""
        chosen = [c.channel for c in (self.channels or []) if c.channel]
        # de-dupe while preserving order
        seen, ordered = set(), []
        for ch in chosen or DEFAULT_CHANNELS:
            if ch not in seen:
                seen.add(ch)
                ordered.append(ch)
        return ordered

    def _validate_custom_filter_fields(self):
        if not self.custom_filter_doctype:
            return
        email_field = self.custom_email_field or "email"
        meta = frappe.get_meta(self.custom_filter_doctype)
        if not meta.get_field(email_field) and email_field != "name":
            frappe.throw(
                _("Email field {0} does not exist on {1}.").format(
                    email_field, self.custom_filter_doctype
                )
            )


def send_announcement(announcement: str):
    """Materialize one Communication Log per recipient (ADR 043). Delivery is
    the dispatcher's job — rate-limited per provider account — which reflects
    outcomes back onto the recipient rows and flips this doc to Sent/Failed
    once nothing is left Queued/Sending. The per-recipient idempotency key
    makes re-running this job (or re-enqueuing the announcement) safe."""
    from seminary.seminary import comms
    from seminary.seminary.person import find_person

    doc = frappe.get_doc("Seminary Announcement", announcement)
    if doc.status not in ("Queued", "Sending"):
        return

    doc.db_set("status", "Sending", update_modified=False)

    channels = doc._selected_channels()
    category = doc.category or "Academic"
    letter_head = _resolve_letter_head(doc)
    voice_media_url = _voice_media_url(doc)
    # Channels to fall back to when a recipient is unreachable on every selected
    # channel — only the ones not already being sent.
    fallback_channels = (
        [c for c in FALLBACK_CHANNELS if c not in channels]
        if doc.fallback_email_portal
        else []
    )

    for child in doc.recipients:
        if child.delivery_status == "Sent":
            continue
        try:
            person_name = find_person(email=child.email, user=child.user)
            person = frappe.get_doc("Person", person_name) if person_name else None
            bodies = _rendered_bodies(doc, child, person, letter_head)

            reached = False
            for channel in channels:
                # Most channels need a Person to resolve an address against;
                # Email uses the recipient's email and Print needs neither.
                if channel not in NO_PERSON_REQUIRED and not person:
                    continue
                reachable = (
                    comms.reachability(person, channel, category, email=child.email)
                    == "ok"
                )
                # Still queue unreachable selected channels: send_message records
                # a Cancelled log with the reason (audit), it just won't deliver.
                _queue_channel(
                    doc, child, person, channel, category, bodies, voice_media_url
                )
                reached = reached or reachable

            if fallback_channels and not reached:
                for channel in fallback_channels:
                    if channel != EMAIL_CHANNEL and not person:
                        continue
                    if (
                        comms.reachability(person, channel, category, email=child.email)
                        != "ok"
                    ):
                        continue
                    _queue_channel(
                        doc, child, person, channel, category, bodies, voice_media_url
                    )
                    reached = True
        except Exception as e:
            frappe.db.set_value(
                "Seminary Announcement Recipient",
                child.name,
                {"delivery_status": "Failed", "error": str(e)[:500]},
                update_modified=False,
            )
            frappe.log_error(
                f"Seminary Announcement {doc.name} failed to queue for {child.email}: {e}",
                "Seminary Announcement Send",
            )

    if PRINT_CHANNEL in channels:
        try:
            _attach_letters_pdf(doc)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), "Seminary Announcement letters PDF"
            )
        if doc.print_mailing_labels:
            try:
                from seminary.seminary.mailing_labels import (
                    attach_labels_for_announcement,
                )

                attach_labels_for_announcement(doc)
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(), "Seminary Announcement mailing labels"
                )

    frappe.db.commit()


def _collect_letters(doc):
    """The personalized, letterhead-wrapped letters for the Print channel —
    one HTML string per recipient. After submit they come from the sent Print
    Communication Logs (the official snapshots); on a draft they're rendered
    live from the resolved recipients (a full preview)."""
    if doc.docstatus == 1:
        messages = frappe.get_all(
            "Communication Log",
            filters={
                "reference_doctype": "Seminary Announcement",
                "reference_name": doc.name,
                "channel": PRINT_CHANNEL,
            },
            fields=["message"],
            order_by="creation asc",
            pluck="message",
        )
        if messages:
            return [m for m in messages if m]

    from seminary.seminary.doctype.seminary_announcement.announcement_recipients import (
        resolve_recipients,
    )
    from seminary.seminary.person import find_person

    letter_head = _resolve_letter_head(doc)
    letters = []
    for r in resolve_recipients(doc):
        child = frappe._dict(r)
        person_name = find_person(email=child.email, user=child.get("user"))
        person = frappe.get_doc("Person", person_name) if person_name else None
        letters.append(_rendered_bodies(doc, child, person, letter_head)["print"])
    return letters


def build_letters_pdf(doc):
    """(pdf_bytes, letter_count) for the consolidated Print letters."""
    from frappe.utils.pdf import get_pdf

    from seminary.seminary import comms

    letters = _collect_letters(doc)
    pages = "".join(f'<div style="page-break-after:always">{l}</div>' for l in letters)
    return get_pdf(comms.pdf_html(pages)), len(letters)


def _attach_letters_pdf(doc):
    """Attach the consolidated Letters PDF to the announcement (replacing any
    prior one). Returns the file URL, or None when there are no letters."""
    pdf, count = build_letters_pdf(doc)
    if not count:
        return None
    for old in frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Seminary Announcement",
            "attached_to_name": doc.name,
            "file_name": ("like", "letters-%"),
        },
        pluck="name",
    ):
        frappe.delete_doc("File", old, ignore_permissions=True, force=True)
    f = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"letters-{doc.name}.pdf",
            "attached_to_doctype": "Seminary Announcement",
            "attached_to_name": doc.name,
            "is_private": 1,
            "content": pdf,
        }
    ).insert(ignore_permissions=True)
    return f.file_url


def _resolve_letter_head(doc):
    """The Letter Head HTML (content, footer) for the printed PDF, per the
    announcement's mode: a specific one, the Seminary Settings default, or none."""
    mode = doc.print_letterhead_mode or "Seminary Default"
    if mode == "None":
        return None
    name = (
        doc.print_letter_head
        if mode == "Specific"
        else frappe.db.get_single_value("Seminary Settings", "letterhead")
    )
    if not name:
        return None
    return frappe.db.get_value("Letter Head", name, ["content", "footer"], as_dict=True)


def _wrap_letterhead(letter_head, message):
    """Wrap a (rendered) message in the resolved letter head for the printed PDF."""
    if not letter_head:
        return message
    head = (
        f'<div class="letter-head">{letter_head.content}</div>'
        if letter_head.content
        else ""
    )
    foot = (
        f'<div class="letter-head-footer">{letter_head.footer}</div>'
        if letter_head.footer
        else ""
    )
    return f"{head}{message}{foot}"


def _render(template, ctx):
    """Render an author-written Jinja snippet against the recipient context.
    No Jinja markers → returned as-is; a render error falls back to the raw
    text (submit-time validation surfaces real syntax errors to the author)."""
    if not template or ("{{" not in template and "{%" not in template):
        return template
    try:
        return frappe.render_template(template, ctx)
    except Exception:
        return template


# Tokens available in announcement message/subject personalization.
RECIPIENT_TOKENS = (
    "recipient.first_name, recipient.last_name, recipient.name, recipient.email"
)


def _recipient_dict(full, first, last, email):
    # Aliases so both {{ recipient.first_name }} and {{ recipient.first }} work.
    return {
        "name": full,
        "full_name": full,
        "first_name": first,
        "first": first,
        "last_name": last,
        "last": last,
        "email": email or "",
    }


def _render_context(child, person):
    full = (
        person.full_name
        if person and getattr(person, "full_name", None)
        else (child.party_name or "")
    ).strip()
    parts = full.split()
    first = (getattr(person, "first_name", None) if person else None) or (
        parts[0] if parts else ""
    )
    last = (getattr(person, "last_name", None) if person else None) or (
        parts[-1] if len(parts) > 1 else ""
    )
    return {
        "recipient": _recipient_dict(full, first, last, child.email),
        "person": person,
    }


def _sample_context():
    return {
        "recipient": _recipient_dict(
            "Sample Recipient", "Sample", "Recipient", "sample@example.com"
        ),
        "person": None,
    }


def _rendered_bodies(doc, child, person, letter_head):
    """Per-recipient rendered bodies: subject, rich message (Email/In-App),
    short text (SMS/WhatsApp/Telegram/Voice), and the letterhead-wrapped print
    body. Personalization tokens like {{ recipient.first_name }} resolve here."""
    ctx = _render_context(child, person)
    message = _render(doc.message or "", ctx)
    subject = _render(doc.subject or "", ctx)
    short = (
        _render(doc.short_message, ctx) if doc.short_message else strip_html(message)
    )
    heading = (
        f"<h1>{frappe.utils.escape_html(subject)}</h1>"
        if subject and doc.print_subject_heading
        else ""
    )
    return {
        "subject": subject,
        "message": message,
        "short": short,
        "print": _wrap_letterhead(letter_head, heading + message),
    }


def _voice_media_url(doc):
    """Absolute, publicly fetchable URL of the Voice recording (Twilio must be
    able to GET it). Flips the attached File public if needed."""
    if not doc.voice_audio:
        return None
    url = doc.voice_audio
    name = frappe.db.get_value("File", {"file_url": url}, "name")
    if name:
        f = frappe.get_doc("File", name)
        if f.is_private:
            f.is_private = 0
            f.save(ignore_permissions=True)
            url = f.file_url
    return frappe.utils.get_url(url)


def _queue_channel(doc, child, person, channel, category, bodies, voice_media_url):
    """Queue one Communication Log for a recipient on a channel. Print carries
    the letterhead-wrapped body, other rich channels (Email, In-App) the
    authored message, and the rest the short body; Voice also carries the audio
    URL. Email passes its address explicitly; other channels resolve the Person
    Channel Address in send_message."""
    from seminary.seminary import comms

    if channel == PRINT_CHANNEL:
        body = bodies["print"]
    elif channel in RICH_CHANNELS:
        body = bodies["message"]
    else:
        body = bodies["short"]
    to_address = child.email if channel == EMAIL_CHANNEL else None
    media_url = voice_media_url if channel == VOICE_CHANNEL else None
    comms.send_message(
        channel=channel,
        category=category,
        person=person,
        to_address=to_address,
        subject=bodies["subject"],
        message=body,
        media_url=media_url,
        reference_doctype=doc.doctype,
        reference_name=doc.name,
        triggered_by=doc.owner,
        dedupe_key=f"seminary-announcement::{doc.name}::{(child.email or '').lower()}::{channel}",
    )


def process_scheduled_announcements():
    """Scheduler task: enqueue send for announcements whose send-time has arrived,
    and retry any Queued ones with no schedule (e.g. if the initial enqueue failed).
    """
    due = frappe.db.sql(
        """
        SELECT name FROM `tabSeminary Announcement`
        WHERE docstatus = 1
          AND status = 'Queued'
          AND (scheduled_datetime IS NULL OR scheduled_datetime <= %(now)s)
        """,
        {"now": now_datetime()},
        pluck=True,
    )
    for name in due:
        frappe.enqueue(
            "seminary.seminary.doctype.seminary_announcement.seminary_announcement.send_announcement",
            queue="long",
            announcement=name,
        )
