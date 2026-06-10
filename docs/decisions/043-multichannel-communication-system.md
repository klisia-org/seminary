# 043 — First-class multi-channel communication system

**Date:** 2026-06-10
**Status:** Accepted

## Context

Communication today is email-only and scattered: Seminary Announcement (broadcast
with recipient resolution, scheduling, per-recipient delivery status), six ad-hoc
`frappe.sendmail` call sites with hardcoded copy, and attendance Notification
Logs. No consent, no read tracking, no rate limiting (seminaries on free provider
tiers need send throttles), no SMS/WhatsApp/Telegram (regionally essential), no
unified view of what a person was told. Frappe's Communication/Newsletter stack
is email-centric; Frappe CRM is sales-funnel oriented. Persons exist per ADR 042.

## Decision

**Channel ≠ provider.** *Communication Channel* is semantic (Email, SMS,
WhatsApp, Telegram, In-App, Print/PDF, Voice/IVR), seeded create-only-if-missing
(never fixtures, per 015's lesson). *Channel Provider Account* is a configured
instance (Twilio-US, Vonage-BR, Telegram bot…) holding credentials, a
country/region scope, `hourly_limit`, and an adapter key resolved through a
`communication_channel_providers` hook — adapters implement
`send(log) → provider_message_id` and `handle_webhook(payload)`, so adding a
provider is one class + one row.

**Communication Log is the ledger and the unified timeline.** One row per
person × channel × message: direction, status spine
(Queued→Sending→Sent→Delivered→Read / Failed/Bounced/Cancelled), template,
rendered snapshot, `triggered_by`, `reference_doctype/name`, campaign,
timestamps per status, `provider_message_id`, and a **unique
`idempotency_key`** — insert-or-skip is the no-double-send guarantee. Creating
a Log never sends inline: a cron dispatcher drains Queued rows per provider
account up to `hourly_limit` minus the trailing-hour sent count, with
backoff retries; status-transition guards make delivery effectively-once.

**Routing per send:** consent check by category (Transactional / Academic /
Community / Promotional / Emergency — Promotional needs opt-in, Transactional is
blocked only by explicit opt-out, Emergency bypasses throttle and opt-out), then
the verified Person Channel Address scoped to that category (falling back to
the primary), then a provider account matching the person's region.

**Communication Template** = key + category + context doctype, with child
versions per (channel, language) holding Jinja subject/body; fallback chain
language→site default, channel→campaign's fallback order.

**Communication Campaign** evolves Seminary Announcement: segment targeting
(today's term/program/course resolvers plus Person attributes), multi-channel
with preference-aware per-person channel choice, materializing Logs for the
dispatcher. The **portal inbox** renders In-App logs with filterable metadata
(category, reference, course) and an unread badge; mark-read sets `read_at` —
provider webhooks (one whitelisted endpoint per account, signature-verified)
set Delivered/Read for external channels and create inbound Logs matched to
Person by channel address.

**Follow-ups:** outbound logs may set `awaiting_response` +
`follow_up_after_days` + follow-up template; a daily task queues the follow-up
(or a staff ToDo) when neither inbound reply nor read arrives in time.

**Portal is a deliberate second stage.** Backend ships first (Log, dispatcher,
Email adapter, campaign port); the SPA (ADR 011 cohesion, ADR 003 tokens) then
grows three surfaces: the structured inbox above (replacing `/announcements`),
a self-service preferences page (channel addresses, per-category consent,
language) writing to Person via whitelisted APIs, and a staff per-person
timeline. Until then `/announcements` keeps reading the ported campaign output.

## Consequences

Easier: one per-person timeline; provider swap = new account row; free-tier
throttling; multilingual copy outside Python; Print/IVR later as mere adapters.
Harder: all outbound messaging must go through `comms.send()` — direct
`frappe.sendmail` becomes an anti-pattern, and the six existing call sites
migrate template-by-template. Open: email open-pixel tracking, multi-step
sequences (drip), donor module on top of Person, Notification Log bridge
retirement.

## Roadmap
Remaining on the communication roadmap: Twilio SMS / WhatsApp Cloud adapters (same shape as Telegram), Days-Before/After scheduled triggers, reply-from-inbox threading, and surfacing inbound replies in the portal.