# 046 — Print & Voice channels, announcement personalization, and the address spine

**Date:** 2026-06-11
**Status:** Accepted

## Context

ADR 045 gave Seminary Announcements an alumni audience, a category, channel
selection, and one Twilio adapter for SMS/WhatsApp. Using it in anger surfaced
the rest of the work: the seeded **Voice** and **Print** channels still had no
adapter; provider credentials sat in a plaintext `settings` JSON that the
operator had to hand-author (and re-derive a webhook secret for); an announcement
could only say the same thing to everyone; nobody could see *before* sending who
a channel would actually reach; and there was no usable way to **print** the
letters or **mail** them. Two modelling questions also came due: where a postal
address lives, and whether the printed PDF could reliably render a letter head.
This ADR records the decisions that closed those gaps.

## Decision

**Every seeded channel now has an adapter.** The one Twilio adapter grows a third
mode — **Voice** places a call through the Calls API that reads the message aloud
(TwiML `<Say>`), or plays an attached recording (`<Play>`, the director's own
voice) when a `media_url` is present; call-status callbacks map to the ledger.
Voice reuses the SMS phone number (`resolve_address` falls back Voice→SMS). The
new **Print** adapter has no carrier: the Communication Log *is* the delivery,
holding the rendered letter snapshot. There is no PDF-per-log — the printable
artifact is a single consolidated **Letters PDF** on the announcement (below).
`Print` and `In-App` are *addressless* (no recipient address resolved), and
**Print bypasses consent** entirely — physical mail carries no opt-in
requirement, like the Emergency category.

**Provider configuration is typed and secret-safe.** `Channel Provider Account`
replaces the free-text provider with a Select and exposes per-provider credential
fields that appear by provider; secrets (auth tokens, bot tokens, webhook
secrets) are **Password fields, encrypted at rest**. `get_config()` assembles the
adapter's settings from the typed fields (decrypted), with the old `settings`
JSON kept only as an optional escape hatch; a patch migrated existing accounts and
stripped their plaintext secrets. Telegram is now near-zero-config: pasting the
bot token auto-generates the webhook secret, fetches the bot username, and (when
the site is public HTTPS) registers the webhook — with a desk button for dev
tunnels.

**Announcements author once, personalize per recipient.** Subject, message, and
short body are rendered through Jinja per recipient (`{{ recipient.first_name }}`,
`recipient.{name,last_name,email}`, `{{ person.* }}`), sourcing real name parts
from the Person. Because Frappe's Jinja inlines unknown-token errors instead of
raising, submit-time validation scans the rendered sample for the error marker
and rejects bad tokens up front. **Reachability is shown before sending**: the
preview tallies, per selected channel, who is reachable (address present and not
opted out) versus who relies on the fallback. The default-on **Email + In-App
fallback** guarantees arrival — a recipient unreachable on every selected channel
is sent Email + In-App instead, so an emergency SMS blast never silently drops
the phone-less.

**Printing is first-class.** Print bodies are wrapped in a letter head
(Seminary Settings default / none / a specific one), with a toggle to print the
subject as an `<h1>` (newsletter) or omit it (formal letter). A **Letters PDF**
(one personalized letter per page, from the sent Print logs after submit, or
rendered live as a preview on a draft) is generated on send and on demand from
the announcement. **Mailing labels** render recipient addresses onto a sheet
whose geometry is a configurable **Mailing Label Format** doctype (seeded with
Avery presets; a seminary measures and adds its own). For PDF reliability,
referenced site images are **inlined as base64 data URIs** (no fragile HTTP fetch
from the renderer — the cause of missing letter-head logos) and capped to the
page width so editor images don't balloon across pages.

**Postal address lives on the Person spine, not the role records.** A mailing
address is reachability data, so it belongs on `Person` alongside email/mobile
(ADR 042) — not duplicated onto Alumni Profile, where one human who is
student-then-alumnus-then-donor would drift across copies. Any portal user edits
their address through the **Preferences** self-service (written straight to their
Person); role records that need to show it mirror it **read-only via
`fetch_from`** (Alumni Profile does). The one deliberate exception is **Student**,
which keeps writable address fields as a registrar-intake snapshot that seeds the
Person on creation and then stands as point-in-time backup while live edits flow
to the Person.

## Consequences

Easier: a calamity reaches people by SMS, WhatsApp, Telegram, *and* an automated
call in one announcement, with email/portal as a guaranteed backstop; a newsletter
or a formal letter prints from the announcement with the seminary's letter head; a
provider is configured by filling labelled fields, not hand-writing JSON; alumni
keep their own mailing address current. Harder: more channels mean more provider
accounts and recipient addresses to keep healthy; per-recipient rendering and the
consolidated PDF cost more work at send time; the PDF renderer's image handling is
now load-bearing (base64 inlining). Open: SMS/WhatsApp/Voice all assume Twilio —
other carriers would each need an adapter; the larger reconciliation of Student's
writable address onto the Person spine is deferred to its own change; true
pixel-WYSIWYG between the editor and the PDF is out of scope (images are capped,
not laid out identically).
