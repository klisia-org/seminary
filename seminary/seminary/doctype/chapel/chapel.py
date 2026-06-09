# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Chapel — a special, public seminary Event (all students and instructors are
invited, open to the public). A chaplain schedules each service here and assigns
the preacher/worship team via the Chapel Team child table.

A confirmed Chapel mirrors itself onto a Frappe Event (calendar visibility +
optional Google Calendar push via Frappe's native integration). The Event is a
*calendar mirror only*: it carries no Event Custom Category and no Student
Graduation Requirement participants, so the ADR 028 attendance engine
(reflect_event_attendance) short-circuits on it. Chapel attendance is tracked
separately via the Chapel Attendance doctype and student self check-in — see
seminary/seminary/chapel.py.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary.utils import generate_checkin_code


def _contact_email(contact):
    return frappe.db.get_value("Contact", contact, "email_id") or None


class Chapel(Document):
    def validate(self):
        self._maybe_set_checkin_code()

    def on_update(self):
        self._sync_event()

    def on_trash(self):
        if self.event and frappe.db.exists("Event", self.event):
            frappe.delete_doc("Event", self.event, ignore_permissions=True, force=True)

    # -- internals ----------------------------------------------------------

    def _maybe_set_checkin_code(self):
        """Generate a code the first time a chapel needs one (code-gated
        check-in is enabled). Kept once set so it stays stable across edits."""
        if self.checkin_code:
            return
        if frappe.db.get_single_value(
            "Seminary Settings", "require_chapel_checkin_code"
        ):
            self.checkin_code = generate_checkin_code()

    def _sync_event(self):
        """Upsert the linked Frappe Event from this Chapel. Only confirmed
        chapels get an Event (the chaplain's finalize gate)."""
        if not self.confirmed:
            return

        settings = frappe.get_cached_doc("Seminary Settings")
        sync = bool(self.sync_with_google_calendar) and bool(
            settings.sync_chapels_with_google_calendar
        )
        if (
            self.sync_with_google_calendar
            and settings.sync_chapels_with_google_calendar
            and not settings.official_google_calendar
        ):
            frappe.throw(
                _(
                    "Set an Official Google Calendar in Seminary Settings to sync "
                    "chapels, or uncheck 'Sync with Google Calendar' on this chapel."
                )
            )

        values = {
            "subject": self.chapel_topic,
            "starts_on": self.starts_on,
            "ends_on": self.ends_on,
            "event_type": "Public",
            "event_category": "Event",
            "location": (
                frappe.db.get_value("Room", self.room, "room_name")
                if self.room
                else None
            ),
            "description": self.description or None,
            "status": "Open",
            "sync_with_google_calendar": 1 if sync else 0,
            "google_calendar": settings.official_google_calendar if sync else None,
        }

        if self.event and frappe.db.exists("Event", self.event):
            event = frappe.get_doc("Event", self.event)
            event.update(values)
            self._set_participants(event)
            event.save(ignore_permissions=True)
        else:
            event = frappe.get_doc({"doctype": "Event", **values})
            self._set_participants(event)
            event.insert(ignore_permissions=True)
            # db_set avoids re-triggering on_update (no recursion).
            self.db_set("event", event.name)

    def _set_participants(self, event):
        """Mirror the Chapel Team (preacher, worship leader, host, …) onto the
        Event so they receive the calendar invite. Contacts only — students are
        not pre-listed (chapel is public; attendance is via self check-in)."""
        event.set("event_participants", [])
        for member in self.chapel_team or []:
            if not member.team_member_contact:
                continue
            event.append(
                "event_participants",
                {
                    "reference_doctype": "Contact",
                    "reference_docname": member.team_member_contact,
                    "email": _contact_email(member.team_member_contact),
                },
            )
