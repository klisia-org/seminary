# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from seminary.seminary.api import sanitize_html


class CohortPost(Document):
    def validate(self):
        if self.content:
            self.content = sanitize_html(self.content)
        if self.visibility == "direct" and not self.direct_recipient:
            frappe.throw(_("A direct post needs a recipient."))
        if self.visibility != "direct":
            self.direct_recipient = None
        self._resolve_scripture_refs()
        self._sync_prayer_answered()
        self._require_video_for_sermon_lab()

    def _require_video_for_sermon_lab(self):
        kind = (
            frappe.db.get_value("Cohort Channel", self.channel, "channel_kind")
            if self.channel
            else None
        )
        if kind == "video_timestamp" and not self.video_url:
            frappe.throw(_("A Sermon Lab post needs a video link."))

    def _sync_prayer_answered(self):
        # answered_on tracks the flag; clearing the flag clears the date/note.
        if self.prayer_answered:
            if not self.prayer_answered_on:
                self.prayer_answered_on = today()
        else:
            self.prayer_answered_on = None
            self.prayer_answer_note = None

    def _resolve_scripture_refs(self):
        """Backfill canonical ordinals for any scripture row entered by display
        text (e.g. from the desk). The feed API expands multi-segment refs into
        rows before insert; this covers single-segment rows added by hand."""
        from seminary.seminary.integrations.bible import parse_reference_segments

        for row in self.scripture_refs or []:
            if row.display and not row.verse_start_ord:
                seg = parse_reference_segments(row.display)[0]
                row.resolved_ref = seg["resolved_ref"]
                row.verse_start_ord = seg["verse_start_ord"]
                row.verse_end_ord = seg["verse_end_ord"]

    def after_insert(self):
        self.notify_new()

    def on_update(self):
        # Comments/reactions cache the post's scope (cohort/visibility/author/
        # recipient) so one permission clause covers all three. Keep the cache
        # honest when the post's scope changes.
        fields = ("cohort", "visibility", "author", "direct_recipient")
        changed = [f for f in fields if self.has_value_changed(f)]
        if changed:
            self._propagate_scope(changed)

    def _propagate_scope(self, changed):
        col = {
            "cohort": "cohort",
            "visibility": "visibility",
            "author": "post_author",
            "direct_recipient": "direct_recipient",
        }
        values = {col[f]: self.get(f) for f in changed}
        for dt in ("Cohort Post Comment", "Cohort Post Reaction"):
            for row in frappe.get_all(dt, filters={"post": self.name}, pluck="name"):
                frappe.db.set_value(dt, row, values, update_modified=False)

    def notify_new(self):
        """Nudge connected clients viewing this cohort/channel to refetch. Only
        ids travel over the wire; the actual data fetch stays permission-scoped."""
        if self.status not in ("published", "pinned"):
            return
        frappe.publish_realtime(
            "cohort_feed_update",
            {"cohort": self.cohort, "channel": self.channel, "post": self.name},
            after_commit=True,
        )
