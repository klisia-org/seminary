# Copyright (c) 2026, Murilo Melo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

EMAIL_CHANNEL = "Email"
SMS_CHANNEL = "SMS"


class Person(Document):
    def validate(self):
        self.set_full_name()
        self.normalize_reachability()
        self.validate_channel_addresses()
        self.sync_primary_channel_addresses()

    def on_update(self):
        self.warn_on_login_email_drift()
        self.propagate_to_roles()

    def set_full_name(self):
        self.full_name = " ".join(
            filter(None, [self.first_name, self.middle_name, self.last_name])
        )

    def normalize_reachability(self):
        # Empty string would collide on the unique index; store NULL instead.
        self.primary_email = (self.primary_email or "").strip().lower() or None
        self.primary_mobile = (self.primary_mobile or "").strip() or None

    def validate_channel_addresses(self):
        seen = set()
        primaries = set()
        for row in self.channel_addresses:
            if row.channel == EMAIL_CHANNEL and row.value:
                row.value = row.value.strip().lower()
            key = (row.channel, (row.value or "").strip().lower())
            if key in seen:
                frappe.throw(
                    _("Duplicate {0} address: {1}").format(row.channel, row.value)
                )
            seen.add(key)
            if row.is_primary:
                # One primary per channel; the first row wins.
                if row.channel in primaries:
                    row.is_primary = 0
                else:
                    primaries.add(row.channel)

    def sync_primary_channel_addresses(self):
        """Mirror primary_email / primary_mobile into their channel-address rows.

        The top-level fields are the convenience handles staff edit; the child
        table is what ADR 043's routing reads. Guarded on channel existence so
        Person saves survive a half-installed site (channels are seeded by
        install/migrate, not fixtures).
        """
        self._upsert_primary(EMAIL_CHANNEL, self.primary_email)
        self._upsert_primary(SMS_CHANNEL, self.primary_mobile)

    def _upsert_primary(self, channel, value):
        if not value or not frappe.db.exists("Communication Channel", channel):
            return
        rows = [r for r in self.channel_addresses if r.channel == channel]
        primary = next((r for r in rows if r.is_primary), None)
        if primary:
            primary.value = value
            return
        same_value = next(
            (r for r in rows if (r.value or "").strip().lower() == value.lower()), None
        )
        if same_value:
            same_value.is_primary = 1
            return
        self.append(
            "channel_addresses",
            {"channel": channel, "value": value, "is_primary": 1, "status": "Active"},
        )

    def warn_on_login_email_drift(self):
        """Frappe keys User by email; we deliberately do not rename it (ADR 042)."""
        before = self.get_doc_before_save()
        if (
            before
            and before.primary_email != self.primary_email
            and self.user
            and self.user != self.primary_email
        ):
            frappe.msgprint(
                _(
                    "Primary email changed, but the linked User {0} keeps its login email. "
                    "Rename the User from the desk if the login should change too."
                ).format(self.user),
                indicator="orange",
                alert=True,
            )

    def propagate_to_roles(self):
        """Push spine-owned values into linked role rows.

        Role contact fields are read-only mirrors (ADR 042): kept as real
        columns so every existing query (announcement recipient resolution,
        reports) stays valid, refreshed here because Frappe's fetch_from only
        fires when the *role* doc is saved. db.set_value runs no hooks, so this
        cannot recurse. Doc names are never touched — Instructor and Alumni
        Profile autoname from instructor_name/email, so those stay put.
        """
        full = self.full_name
        names = {
            "first_name": self.first_name or "",
            "middle_name": self.middle_name or "",
            "last_name": self.last_name or "",
        }
        targets = {
            "Student": {**names, "student_name": full},
            "Student Applicant": {**names, "title": full},
            "Instructor": {},
            "Alumni Profile": {"full_name": full},
        }
        email_field = {
            "Student": "student_email_id",
            "Student Applicant": "student_email_id",
            "Instructor": "prof_email",
        }
        mobile_field = {
            "Student": "student_mobile_number",
            "Student Applicant": "student_mobile_number",
            "Instructor": "phone_message",
        }
        for doctype, values in targets.items():
            values = dict(values)
            # Never blank a unique/required email mirror from an empty spine.
            if self.primary_email and doctype in email_field:
                values[email_field[doctype]] = self.primary_email
            if self.primary_mobile and doctype in mobile_field:
                values[mobile_field[doctype]] = self.primary_mobile
            if not values:
                continue
            rows = frappe.get_all(
                doctype,
                filters={"person": self.name},
                fields=["name"] + list(values),
            )
            for row in rows:
                changed = {
                    field: value
                    for field, value in values.items()
                    if (row.get(field) or "") != (value or "")
                }
                if changed:
                    frappe.db.set_value(
                        doctype, row.name, changed, update_modified=False
                    )
