# 045 — Announcement audiences, categories & multi-channel delivery

**Date:** 2026-06-11
**Status:** Accepted

## Context

The Seminary Announcement doctype is the broadcast "port" onto the ADR 043
communication engine, but it under-used what the engine already offers. Audience
was limited to enrolled students / teaching instructors / specific courses / a
custom filter — there was no first-class way to reach **alumni**, even though
they are a clean doctype (`Alumni Profile` with `user`, `email`, `enabled`).
Category was **hardcoded** to `Academic` in `send_announcement()`, so the
consent/throttle semantics the engine attaches to categories (notably
`Emergency`, which bypasses both) were unreachable. And channels were hardcoded
to **Email + In-App**, so a calamity ("the seminary must close") could not go
out over SMS / WhatsApp / Telegram with a short, plain-text body — even though
the engine routes any channel per-Person and a Telegram adapter already shipped.

## Decision

**Alumni become a first-class audience.** A new `audience_alumni` checkbox is
resolved by `_alumni_recipients()` over enabled `Alumni Profile`s (filtered on
`enabled`, not `show_in_directory` — directory visibility is a public-listing
concern, not reachability). It is term-independent, so it ignores
term/program/course narrowing and unions+dedupes with the other rules like any
audience. Recipient rows gain an `Alumni` party type.

**Category is exposed on the port.** A `category` Select (the Communication Log
options; default `Academic`) replaces the hardcoded value and is passed straight
to `comms.send_message`. No engine change is needed: `Emergency` already bypasses
consent (`consent_blocks`) and the hourly throttle (`dispatch`), so an emergency
announcement reaches everyone on every selected channel, immediately.

**Channels are selectable, with a rich/short body split.** A `channels` Table
MultiSelect (of `Communication Channel`) drives one `send_message` per recipient
× channel; empty = Email + In-App (backward compatible). Rich channels (Email,
In-App) send the authored `message`; length-limited channels (SMS, WhatsApp,
Telegram) send the new `short_message`, falling back to the message stripped to
plain text. Submit validates every chosen channel has an enabled provider
account, so authors get one clear error instead of per-recipient failures.
Because a recipient can now span several channels, the grid reflection
(`_reflect_announcement`) rolls up monotonically — **"Sent wins"**: any channel
reaching Sent/Delivered/Read marks the recipient Sent; Failed is recorded only
when not already Sent — and finds the row via the email encoded in the
per-recipient idempotency key, so non-Email channels reflect too.

**Twilio adapter for SMS + WhatsApp.** One `TwilioAdapter` serves both channels
(Twilio's Messages API is identical; WhatsApp just prefixes addresses with
`whatsapp:`), keyed off the account's channel, registered under the `twilio`
provider. Outbound sets a per-message `StatusCallback` to the shared comms
webhook; delivery receipts and inbound replies verify Twilio's
`X-Twilio-Signature`. Credentials are secrets, so no account is auto-seeded — the
seminary creates one by hand, the same as Telegram.

**`academic_term` is now conditional** (`mandatory_depends_on` + a backend guard):
required only for term-scoped audiences, optional for alumni-only / custom-only
broadcasts. The autoname falls back to `ANN-GENERAL-####` when no term is set.

## Consequences

Easier: an emergency campus-closure SMS/WhatsApp/Telegram blast, an alumni
newsletter, or a promotional broadcast are all the same doctype with different
checkboxes — no code. Every channel's outcome lands on the recipient grid and on
the Person timeline. Harder: authors must understand that `Emergency` overrides
consent and throttling; SMS/WhatsApp require Twilio credentials and Person phone
addresses to be reachable. Open (unchanged from ADR 043): email open tracking,
multi-step drip sequences.
