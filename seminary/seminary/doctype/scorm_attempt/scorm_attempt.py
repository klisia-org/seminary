# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""One student's runtime state for one SCO (privatedocs p009 §2.9).

Written only by the SCORM commit endpoint, which finds the row by
`(frappe.session.user, package, sco)` -- identity comes from the session and is
never named by the caller.

**The value rules belong in `validate()` here, not in the endpoint**, so that no
write path can skip them: the closed vocabularies, the score clamp to the
declared range, the time formats, and the `location` / `suspend_data` length
caps. They arrive with p009 S6 along with the commit endpoint and the CMI
element allow-list; this controller is the schema half.

`suspend_data` is attacker-controlled opaque text. It is handed back to the
launcher verbatim and is **never rendered as HTML** anywhere -- not in the SPA,
not in Desk. Any future staff-facing attempt viewer must render it as text.
"""

from __future__ import annotations

from frappe.model.document import Document


class SCORMAttempt(Document):
    pass
