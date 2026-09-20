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

## Denial kinds (p010 H1, p009 S11)

Every refusal this package makes is recorded through
`seminary.seminary.security_log.record_denial` under one of the slugs below.
They are listed here because the slug is the operator's grep anchor and the
counter's field name -- so it is an interface, and renaming one silently breaks
an alert nobody will notice is broken.

    bench --site <site> execute seminary.seminary.security_log.denial_counts
    grep scorm_ sites/<site>/logs/seminary.security.log

| Kind | Raised by | What it means |
| --- | --- | --- |
| `scorm_ingest_refused` | `api._check_scorm_archive` | A zip was refused at upload: bomb, ratio, entry count, no manifest. Stopped before a chapter exists. |
| `scorm_explode_refused` | `explode._record` | A zip passed ingest and failed the unpack: traversal, symlink, absolute path, collision. |
| `scorm_host_scope` | `delivery.guard_delivery_host` | Something asked the delivery host for a non-SCORM path -- Desk, `/api`, a website route. Routine from scanners; a spike with real paths is not. |
| `scorm_token_miss` | `delivery.SCORMDelivery` | A launch token did not resolve. Expired, revoked, or guessed. |
| `scorm_package_miss` | `delivery.SCORMDelivery` | The token resolved but named a different package than the URL, or the package is not `Ready`. **Cross-package access attempted.** |
| `scorm_member_miss` | `delivery.SCORMDelivery` | A path that is not a key of the inventory. The deny-by-default lookup doing its job; also what traversal and bucket probing look like from here. |
| `scorm_commit_identity` | `runtime.commit` | A token was presented by a session other than the one it was issued to, to **write**. The most serious of these. |
| `scorm_state_identity` | `runtime.state` | The same, to read. |

A `permission` denial from `guards` covers the launch itself: `launch` runs
`require_enrolled`, which logs through the shared factory like every other
course read, so there is no SCORM-specific kind for "not on this roster".
"""
