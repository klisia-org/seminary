# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""SCORM delivery: unpack a package into object storage, and serve it safely.

See `privatedocs/p009-SCORM-delivery.md`. The two properties everything else
hangs off:

* **Deny-by-default addressing.** `explode` writes an inventory of the member
  paths it validated; delivery answers only for a path that is a key of it. A
  client never names an object key.
* **Isolation by origin.** Package code runs on a host that carries no session,
  no CSRF token and no cookie of the app's, and that may call no LMS endpoint.
  Every write back into the LMS is made by the app origin under the user's own
  session.

Nothing here extracts an archive to local disk, and nothing rewrites package
content. Both were tried before p008 and both were the vulnerability.
"""
