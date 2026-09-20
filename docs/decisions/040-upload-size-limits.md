# 040 — Upload size limits & in-platform recordings

**Date:** 2026-06-10
**Status:** Accepted

## Context

File uploads had no client-side guard and never told the user a limit. Frappe
*does* enforce `max_file_size` server-side, but the file uploads in full and
then fails with a cryptic error. Adding in-platform lesson video recording
(the editor's "Record Video" block) made this sharper: recordings can be large,
and storage + egress are the real cost drivers (no object storage / CDN today;
public files are served by nginx, private files stream through a worker).

## Decision

**One source of truth, surfaced everywhere.** The general cap is Frappe's own
`max_file_size` (System Settings → site config → 25 MB default), exposed to the
SPA via whitelisted `lesson_media.get_upload_limits()`. The frontend
`uploadLimits` resource + `validateFileSize()` helper (in `utils/index.js`) are
wired into **every** `FileUploader` so oversized files are rejected before
upload, with a "Max N MB" hint on the prominent ones.

**Recordings carry a tighter sub-cap.** Client: `RecorderPlugin` `maxSeconds`
(3 min) + `videoBitsPerSecond` (~1.5 Mbps) ≈ ~36 MB. Server backstop:
`lesson_media.enforce_recording_limits` (a `File` `validate` hook scoped by the
`lesson-recording-` filename prefix) rejects recorder output over
`MAX_RECORDING_MB` (75) — the client cap alone is bypassable.

## Consequences

- **One knob:** set System Settings → Max File Size to the value users are held
  to; it drives both enforcement and every label. If it reads huge, it was
  raised (likely to allow video) — lower it deliberately.
- **Recorder caps move together:** `maxSeconds`, `videoBitsPerSecond` (client)
  and `MAX_RECORDING_MB` (server). They cross-reference in comments.
- The recording sub-cap must stay ≤ the global `max_file_size`, or Frappe
  rejects recordings first.
- Compact uploaders (avatars, table-cell links, inline discussion replies) get
  validation but no visible hint, to avoid clutter; the rejection message still
  informs.
- No new infra. If video grows, Cloudflare R2 + CDN slots in underneath without
  touching the recorder; private-file streaming through workers remains the
  scaling caveat.

## Addendum (2026-09-20) — what bounds the *direct* path when nothing is configured

p005a A10-6 read `direct_limit_for_user` as falling back to a hard 2 GiB. It does not wherever a
policy exists: `limit_for_user` resolves the per-role exceptions, then **Default Max Upload**, and
`DEFAULT_MAX_DIRECT_BYTES` is reached only when *neither* is set. Measured across potestas
(10/40/100 MB), testable (25/400 MB) and tlink (30/75/100 MB), the constant bound nobody.

Two principals can still reach it, and only one matters:

- **`Administrator`** — uncapped by design (`limit_for_user` returns `None` first). Schools are not
  given this account; they are given **System Manager**, which holds no special case and resolves to
  the default like any other role. Verified: 10 MB on potestas, 25 MB on testable, 30 MB on tlink.
- **A site with object storage configured and no upload policy at all.** Here the constant really is
  the only ceiling, because the direct path deliberately escapes Frappe's `max_file_size` and
  nginx's body cap — that escape is the whole point of the path, so it must not be bounded by
  `global_max_bytes()`.

The second case is legitimate but was invisible, and the warning alone does not reach it: a fresh
install that never opens Seminary Settings never sees one. So **Default Max Upload now ships a
default of 25 MB**. `after_install` already saves Seminary Settings (`seed_portal_messaging_rules`),
and a Single persists its field defaults on save, so a new site is bounded from the first minute.
Existing sites are untouched — their stored value wins over the field default, verified on potestas
(kept 10) and testable (kept 25) across a migrate.

25 MB rather than something derived from `global_max_bytes()`: that resolves per site and is not a
stable basis for a shipped default — it read 80 MB on potestas and 512000 MB on testable, the latter
because System Settings' value is interpreted as megabytes here.

Seminary Settings also warns on save when object storage is configured and no policy is, naming the
constant and pointing at **Default Max Upload**. And the field's own description used to say that at
0 "only System Settings → Max File Size" applies, which is false for the direct path and was exactly
the misreading behind this row; it now says what 0 really means.
Enforcement is unchanged: narrowing an unconfigured site to the global cap would break the direct
path for anyone deliberately relying on it, which this ADR's "one knob, surfaced everywhere" rule
does not license.

**Still not built:** an aggregate quota (bytes per user per window). A10-6 asked for one; it needs
two numbers nobody has set and a counter, so it stays recorded rather than guessed.
