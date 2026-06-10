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
