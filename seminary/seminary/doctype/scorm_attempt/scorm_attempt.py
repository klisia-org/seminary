# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""One student's runtime state for one SCO (privatedocs p009 §2.9).

Written by the SCORM commit endpoint, which finds the row by the launch it was
issued under and the session user -- identity is never named by the caller.

**The value rules live in `validate()`, not in the endpoint**, and that is a
deliberate departure from §2.9's literal wording. Read literally, "writes
through a controller with ordinary permissions, on a row the session user owns"
means granting Student `write if_owner`, which would let a student PUT
`/api/resource/SCORM Attempt` and set `score_raw` and `completion_status`
directly -- straight past the allow-list the endpoint applies. So: Student is
read-if-owner only, the endpoint writes with `ignore_permissions` after its own
guards (the `save_progress` pattern already in this app), and every rule that
makes a value trustworthy is enforced *here*, where no write path can skip it.

`suspend_data` is attacker-controlled opaque text. It is handed back to the
launcher verbatim and is **never rendered as HTML** anywhere -- not in the SPA,
not in Desk. Any future staff-facing attempt viewer must render it as text.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document

from seminary.scorm import cmi


class SCORMAttempt(Document):
    def validate(self):
        self.validate_status()
        self.validate_scores()
        self.validate_state()

    def validate_status(self):
        self.completion_status = cmi.check_vocabulary(
            "completion_status",
            self.completion_status or "unknown",
            cmi.COMPLETION_VALUES,
        )
        self.success_status = cmi.check_vocabulary(
            "success_status", self.success_status or "unknown", cmi.SUCCESS_VALUES
        )

    def validate_scores(self):
        """Clamped to what the package itself declared, or to 0-100.

        Clamped rather than refused: a package reporting 110 out of 100 is badly
        written, not hostile, and refusing would lose the student's real progress
        with the bad number. What keeps the number from being treated as an
        assessment is §2.12, not this.
        """
        for field in ("score_raw", "score_min", "score_max", "score_scaled"):
            value = self.get(field)
            if value in (None, ""):
                continue
            self.set(field, cmi.check_number(field, value))

        if self.score_scaled is not None:
            self.score_scaled = cmi.clamp(self.score_scaled, -1.0, 1.0)

        if self.score_raw is None:
            return
        low = self.score_min if self.score_min is not None else 0.0
        high = self.score_max if self.score_max is not None else 100.0
        if low > high:
            # The package contradicted itself; its range is not usable.
            low, high = 0.0, 100.0
        self.score_raw = cmi.clamp(self.score_raw, low, high)

    def validate_state(self):
        self.location = cmi.check_length("location", self.location, cmi.MAX_LOCATION)
        self.suspend_data = cmi.check_length(
            "suspend_data",
            self.suspend_data,
            int(frappe.conf.get("scorm_max_suspend_bytes") or cmi.DEFAULT_MAX_SUSPEND),
        )
        self.session_time = cmi.check_time("session_time", self.session_time)
        self.total_time = cmi.check_time("total_time", self.total_time)
