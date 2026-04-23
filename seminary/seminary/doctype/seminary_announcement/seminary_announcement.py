import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

from seminary.seminary.doctype.seminary_announcement.announcement_recipients import (
    resolve_recipients,
)


class SeminaryAnnouncement(Document):
    def validate(self):
        self._validate_audience_selected()
        self._validate_custom_filter_fields()

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
            or has_courses
            or has_custom
        ):
            frappe.throw(
                _(
                    "Select at least one audience: enrolled students, teaching "
                    "instructors, specific course schedules, or a custom filter."
                )
            )

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
    doc = frappe.get_doc("Seminary Announcement", announcement)
    if doc.status not in ("Queued", "Sending"):
        return

    doc.db_set("status", "Sending", update_modified=False)
    sent = 0
    failed = 0

    for child in doc.recipients:
        if child.delivery_status == "Sent":
            continue
        try:
            frappe.sendmail(
                recipients=[child.email],
                subject=doc.subject,
                message=doc.message,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
                expose_recipients="hide",
                now=False,
            )
            frappe.db.set_value(
                "Seminary Announcement Recipient",
                child.name,
                {"delivery_status": "Sent", "error": None},
                update_modified=False,
            )
            sent += 1
        except Exception as e:
            frappe.db.set_value(
                "Seminary Announcement Recipient",
                child.name,
                {"delivery_status": "Failed", "error": str(e)[:500]},
                update_modified=False,
            )
            failed += 1
            frappe.log_error(
                f"Seminary Announcement {doc.name} failed for {child.email}: {e}",
                "Seminary Announcement Send",
            )

    final_status = "Sent" if sent > 0 else "Failed"
    doc.db_set(
        {"status": final_status, "sent_datetime": now_datetime()},
        update_modified=False,
    )
    frappe.db.commit()


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
