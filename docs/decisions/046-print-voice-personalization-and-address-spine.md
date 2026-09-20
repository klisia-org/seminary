# 046 — Print & Voice channels, announcement personalization, and the address spine

**Date:** 2026-06-11
**Status:** Accepted — **address clauses superseded by [ADR 068](068-person-first-identity-and-shared-attribute-registry.md) (2026-09-04)**

The channels, personalization and mailing-label decisions stand. Two things about the address do not:

- **The deliberate Student exception is gone.** "Student ... keeps writable address fields as a
  registrar-intake snapshot that seeds the Person on creation and then stands as point-in-time backup"
  — the seeding never happened. `ensure_person()` accepted no address arguments at all, so nothing on
  the intake path ever wrote one; only the importer and the portal preferences page did. The fields
  were an unmanaged second copy, not a backup, and they are deleted. This is the "larger reconciliation
  ... deferred to its own change" that the Open section names.
- **Postal country is now its own field.** `alumni_profile.mailing_country` fetched `person.country`,
  which is the messaging-provider routing selector (043) — so a student's self-service address edit
  could reach comms routing. `Person.mailing_country` is distinct from `Person.country`.

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

### Escaping: the sink decides, and HTML opts back in (2026-09-20)

Author text is rendered by `author_templates` in a Jinja sandbox with no `frappe` global, no
session and strict undefined names. That part held. What did not is that it rendered with
`autoescape=False`, so every value interpolated from the context reached the output raw — and
recipient names *are* context values, controlled by the recipient.

p005a **A05-7** filed this as "the sandbox renders unescaped", with the caveat that turning
autoescaping on would break formatting. That caveat is half right, and the half that is wrong is
the important one: **Jinja escapes the interpolated value, not the template.** A template's own
markup is literal text and is never touched, so an author's `<b>` survives exactly as written.
Only `{{ ... }}` output changes — precisely the untrusted half.

The half that is right is the sink. Author text feeds two kinds of destination, and one of them is
not HTML:

- **HTML** — Email, In-App, Print (`comms.HTML_CHANNELS`, the same set as
  `Seminary Announcement.RICH_CHANNELS`), and `Seminary Announcement.message`, a Text Editor field.
- **Plain text** — SMS, WhatsApp, Telegram, Voice, `short_message` (Small Text), and every
  `Data` subject. Escaping here is not neutral: it puts `&#39;` where an apostrophe belongs and
  `&amp;` in the middle of a text message.

So `render_author_text(..., html=<bool>)` follows the sink, and defaults to `False` — a caller that
has not thought about its destination keeps the previous behaviour rather than silently mangling a
text message.

**And a context value that is genuinely HTML opts back in** with `| safe_html`, which passes it
through `content_safety.clean_rich` and marks the result safe. That is the p008 F1 policy applied
here: repair, never drop. Without it the only choices were escaping everything (breaking a template
that legitimately interpolates rich text from `doc`) or escaping nothing (the finding). The filter
is what makes this a scoping change rather than a trade-off.

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
