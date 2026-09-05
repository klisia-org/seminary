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
        self.assert_reachable()
        self.validate_channel_addresses()
        self.sync_primary_channel_addresses()
        self.warn_about_required_details()

    def warn_about_required_details(self):
        """Name the details the school requires that this record still lacks.

        A warning, never a throw (ADR 067 section 9). `ensure_person` is called
        with nothing but a `user` from the comms, communication-trigger and
        partner-portal paths, so a hard requirement here would break
        notification delivery and partner signup outright. And a rule enabled
        this week must not make a Person created three years ago unsaveable
        while a registrar is correcting their phone number: the requirement
        reaches records made *after* the toggle, which is what the planner's
        readiness check exists to compensate for.

        Skipped on insert, because a Person is very often created by a system
        path with two fields and filled in afterwards -- warning at that moment
        would train everyone to ignore it.
        """
        if self.is_new() or self.flags.ignore_required_details:
            return
        if not frappe.db.table_exists("Mandatory Personal Field"):
            return
        from seminary.seminary.doctype.mandatory_personal_field import (
            mandatory_personal_field as mpf,
        )

        meta = frappe.get_meta("Person")
        missing = []
        for fieldname in sorted(mpf.required_fields()):
            df = meta.get_field(fieldname)
            if df and not self.get(fieldname):
                missing.append(_(df.label) if df.label else fieldname)
        if missing:
            frappe.msgprint(
                _("Still to record for this person: {0}.").format(", ".join(missing)),
                indicator="orange",
                alert=True,
            )

    def assert_reachable(self):
        """A Person holding a role record must keep a primary email.

        Since ADR 068 phase 4 the role addresses are `fetch_from
        person.primary_email`, and Frappe *blanks* a mirror whose source is
        null. Those addresses are unique-indexed and provision the portal
        login, so clearing the spine's email would strand the login on the
        role's next save — far away from the edit that caused it. Refuse here,
        where the person doing it can still see why.
        """
        from seminary.seminary.person_fields import assert_reachable

        if not self.is_new():
            assert_reachable(self)

    def on_update(self):
        self.warn_on_login_email_drift()
        self.propagate_to_roles()
        self.resync_open_snapshots()
        self.refresh_coordinates()

    def resync_open_snapshots(self):
        """Correct the snapshots on documents that are still running.

        Distinct from `propagate_to_roles`, and deliberately so: that keeps
        mirrors current on records that describe *this person now*, while this
        re-takes a snapshot on a record that describes something that happened
        to them and has not finished happening yet. A concluded enrollment is
        never touched by either (ADR 068 §3).
        """
        from seminary.seminary.person_fields import resync_open_snapshots

        resync_open_snapshots(self.name)

    def refresh_coordinates(self):
        """Queue a geocode when the address changed (ADR 068 §7).

        Queued, never inline: an intake form must not block on a third party
        and a provider outage must not fail the save. This hangs off `Person`
        rather than each intake path because phase 5 left exactly one address
        writer — `person_import_batch._apply_person_address` used to write with
        `db.set_value`, which runs no hooks, so an imported address would never
        have reached this.
        """
        from seminary.seminary.integrations import geocoding

        if not geocoding.is_enabled():
            return
        if geocoding.address_changed(self):
            geocoding.enqueue_for(self.name)

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

        What gets pushed where is declared in `person_fields.SPEC` (ADR 068),
        not written out here — this used to be a hand-maintained dict that
        disagreed with the JSON flags meant to protect the same fields.

        The push is needed even once the role fields become `fetch_from`
        mirrors: Frappe re-fetches only when the *role* doc is saved, and there
        is no reverse hook. `db.set_value` runs no hooks, so this cannot
        recurse. Doc names are never touched — Instructor and Alumni Profile
        still autoname from instructor_name/email until ADR 068 section 5, so
        the registry deliberately declares no binding for those two fields.
        """
        from seminary.seminary.person_fields import propagation_plan

        for doctype, values in propagation_plan(self).items():
            rows = frappe.get_all(
                doctype,
                filters={"person": self.name},
                fields=["name"] + list(values),
            )
            for row in rows:
                # No unique-collision guard is needed here. `Student.person`,
                # `Instructor.person` and `Alumni Profile.person` are unique
                # (ADR 068 §1), so this loop sees at most one row per doctype,
                # and `Person.primary_email` is unique too — so no two people
                # can be pushing the same address at a unique mirror.
                changed = {
                    field: value
                    for field, value in values.items()
                    if (row.get(field) or "") != (value or "")
                }
                if changed:
                    frappe.db.set_value(
                        doctype, row.name, changed, update_modified=False
                    )
