# Communication

SeminaryERP ships a first-class multi-channel communication system. Every message sent through the system — email, SMS, WhatsApp, Telegram, or the portal In-App inbox — is recorded in a single **Communication Log** ledger, giving staff a complete audit trail and a CRM-style view of every conversation with each person.

## Key concepts

- **Person** — the identity spine (see [Person](#person)). Every stakeholder has exactly one Person record with a stable `PERS-#####` id. Email and phone are contact addresses, not identity keys: changing them never breaks links to other records.
- **Communication Channel** — the _medium_ (Email, SMS, WhatsApp, Telegram, In-App). Seeded automatically; not user-configurable.
- **Channel Provider Account** — a configured _instance_ of a channel: your Mailgun account, your Twilio number, your Telegram bot. One channel can have multiple provider accounts (e.g., country-specific SMS numbers).
- **Communication Template** — reusable message blueprints with per-channel, per-language versions rendered as Jinja2.
- **Communication Trigger** — a declarative rule that fires a template when a document field reaches a configured state — no custom code required.
- **Communication Log** — the immutable ledger row created for every outbound or inbound message. Status moves forward only: Queued → Sending → Sent → Delivered → Read.

## Person

The Person doctype is the identity spine for all stakeholders — students, applicants, instructors, alumni, and any external party. It replaces email as the primary key: two different email addresses for the same human resolve to a single `PERS-#####` record.

### What a Person contains

| Section           | Fields                                                                                                                           |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Identity          | First, middle, last name; language; country                                                                                      |
| Contact           | Primary email, primary mobile (mirrors into Channel Addresses)                                                |
| Channel Addresses | Per-channel reachability rows (Email, SMS, Telegram chat id, …) with scope, primary flag, verification status |
| Consents          | Per-category opt-in/out per channel                                                                                              |
| Links             | User (login), Customer (financial), linked role records                                    |

Role records (Student, Instructor, Student Applicant, Alumni Profile) carry a **person** Link field. Their contact fields are read-only mirrors hydrated from the Person — editing them is done on the Person form, not on the role record.

### CRM Timeline

Opening a Person on Desk shows a **Conversation** tab listing every Communication Log sent to or received from that person, sorted newest-first. Each entry shows the channel icon, direction arrow, status pill, subject (clickable), timestamp, and the triggering reference document. Staff can compose a new message directly from the Person form using the Email, SMS, or In-App buttons.

### How Persons are created

Persons are created automatically at onboarding:

- **Portal / webform path** — when a Student Applicant is created, `ensure_person()` runs and mints a Person (or finds the existing one by email or User link).
- **Staff path** — creating an Instructor or User triggers the same function; identity data lifts from the User record.

Staff can also create Persons manually on Desk for external parties (recommenders, donors) who are not system users.

## Communication Channels

Seven channels are seeded at install: **Email**, **SMS**, **WhatsApp**, **Telegram**, **In-App**, **Print**, and **Voice**. Channels are reference data — they are not edited by staff.

## Channel Provider Accounts

A Channel Provider Account is what connects a channel to a real service. Navigate to **Communication > Channel Provider Account** to configure one.

| Field                                    | Description                                                                                                                        |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Channel                                  | Which channel this account covers (Email, Telegram, …)                                                          |
| Provider                                 | The adapter that carries it — a dropdown: `frappe-email`, `in-app`, `telegram`, `twilio`                           |
| Country                                  | Optional — routes messages to this account for that country first                                                                  |
| Hourly Limit                             | Max outbound messages per hour (0 = unlimited)                                                                  |
| Credentials                              | Typed fields that appear based on the provider (see below); secrets are stored **encrypted**                    |
| Extra Settings (JSON) | Advanced/optional — extra raw JSON merged under the typed fields. Secrets belong in the encrypted fields, not here |

When you pick a Provider, the matching credential fields appear and the required ones are enforced on save. Auth tokens and bot tokens are **Password** fields — encrypted at rest, never shown back in plain text.

Two accounts are seeded:

- **Default Email** — uses the built-in Frappe email stack (`frappe-email`); no extra credentials needed.
- **Portal Inbox** — the In-App channel (`in-app`); messages land instantly in the portal inbox.

### Adding a Telegram account

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Create a Channel Provider Account:
   - Channel: **Telegram**
   - Provider: **telegram**
   - **Bot Token** — the token from @BotFather (encrypted). This is the only field you must fill.
3. **Save.** On save the system does the rest automatically: it generates the encrypted **Webhook Secret**, fetches the **Bot Username**, and — if the site is publicly reachable over HTTPS — registers the webhook with Telegram.
4. **If the site isn't public yet** (e.g. local dev), click **Register Telegram Webhook** on the form and supply a public HTTPS tunnel URL (e.g. an ngrok/cloudflared address). Telegram only accepts public HTTPS webhooks. The same button lets you re-register at any time.
5. Recipients connect from their portal **Preferences** page: the _Connect Telegram_ link opens a signed deep-link that registers their chat id on their Person automatically. Bots cannot initiate contact, so this connect flow is required before any Telegram message can be delivered to that person.

> The `bench ... execute seminary.seminary.telegram_adapter.setup_webhook` command still works as a scripted fallback, but the button (and auto-registration on save) is the normal path.

### Adding a Twilio account (SMS or WhatsApp)

One adapter (`twilio`) serves both SMS and WhatsApp — create one account per channel.

1. In the [Twilio console](https://console.twilio.com), copy the **Account SID** and **Auth Token**, and provision a sending number (an SMS number, or a WhatsApp-enabled sender).
2. Create a Channel Provider Account:
   - Channel: **SMS** (or **WhatsApp**)
   - Provider: **twilio**
   - **Twilio Account SID** — starts with `AC`.
   - **Twilio Auth Token** — encrypted.
   - **From Number** — E.164, e.g. `+15551234567`. For WhatsApp use the WhatsApp-enabled sender (the sandbox is `+14155238886`); the `whatsapp:` prefix is added automatically from the Channel. _Or_ leave it blank and set a **Messaging Service SID** (`MG...`) instead.
3. **Delivery receipts** are automatic — each message sets a `StatusCallback` pointing at the shared webhook, so Twilio advances the log to _Delivered_ or _Failed_.
4. **Inbound replies:** in the Twilio console, set the number's _"A message comes in"_ webhook to
   `https://<your-site>/api/method/seminary.seminary.comms.webhook?account=<account name>`.
   Both status callbacks and inbound messages are verified against Twilio's `X-Twilio-Signature`.

Recipients are reachable once their Person has a phone number on the matching channel (the primary mobile is mirrored to the SMS channel automatically; WhatsApp addresses are added per Person).

### Adding a Twilio Voice account

Voice uses the **same Twilio credentials** as SMS — it just places a call that reads the message aloud (text-to-speech). Create a separate account:

- Channel: **Voice**
- Provider: **twilio**
- **Twilio Account SID** / **Twilio Auth Token** — as above.
- **From Number** — a **voice-capable** Twilio number (Messaging Service SIDs don't apply to calls).

Voice reuses the recipient's phone number — if a Person has no dedicated Voice address, the system falls back to their SMS number (their primary mobile). The call's outcome (answered / busy / no-answer) flows back through the same webhook.

### Print

**Print** is built in and seeded out of the box (the **Print Spool** account, provider `print`) — no credentials. Sending on the Print channel renders the message to a **PDF attached to the Communication Log**, ready for the office to print and mail. Like the portal inbox, it "delivers" immediately at queue time; there's no address to resolve, so every recipient is reachable. Print uses the full rich **Message** (not the Short Message).

## Communication Templates

Navigate to **Communication > Communication Template** to create or edit templates.

Each template has one or more **versions**, each scoped to a channel and optionally a language. When a message is sent, the engine picks the version matching the recipient's preferred language and the target channel, falling back to the default language version.

Template bodies and subjects are Jinja2. The render context always includes:

| Variable   | Contents                                                                                          |
| ---------- | ------------------------------------------------------------------------------------------------- |
| `person`   | The recipient's Person document                                                                   |
| `doc`      | The reference document (if `reference_doctype` / `reference_name` were passed) |
| Any extras | Key/value pairs passed by the caller                                                              |

Seven templates are seeded: waitlist promotion (student and registrar variants), waitlist closed, CEI payment threshold, late-grades nag, few academic terms warning, and recommendation request.

### Categories

Every template carries a **category** that controls consent and routing:

| Category      | Consent rule                                         |
| ------------- | ---------------------------------------------------- |
| Emergency     | Always delivered; bypasses throttle and consent      |
| Transactional | Delivered unless the person has explicitly opted out |
| Promotional   | Delivered only if the person has opted in            |

## Communication Triggers

Triggers let staff configure automatic notifications without writing code. Navigate to **Communication > Communication Trigger**.

| Field             | Description                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------------- |
| Reference Doctype | The doctype to watch (e.g., _Withdrawal Request_) |
| Trigger On        | Save, Insert, Submit, or Cancel                                                                      |
| Template          | The Communication Template to render                                                                 |
| Once Per Document | Send at most once per document name (idempotent re-runs)                          |
| Conditions        | AND-ed field-match rules evaluated against the saved document                                        |
| Recipients        | Who receives the message (see below)                                              |

### Conditions

Each condition row specifies a **Field**, an **Operator**, and an **Expected Value**. All rows must match for the trigger to fire. Supported operators: equals, not equals, contains, not contains, starts with, ends with, is set, is not set, greater than, less than.

Edge detection: the trigger compares the document _after_ save to its state _before_ save. A trigger on `workflow_state = Academically Approved` fires only when the state _transitions_ to that value, not on every subsequent save.

### Recipients

Each recipient row specifies where to deliver:

| Recipient Type  | Resolves to                                          |
| --------------- | ---------------------------------------------------- |
| Role            | All enabled users holding that role                  |
| Person Field    | A Link-to-Person field on the document or its parent |
| Specific Person | A hardcoded Person name                              |

## Communication Log

Every message creates a Communication Log row. Navigate to **Communication > Communication Log** to search, filter, and inspect the full ledger.

Key fields:

| Field            | Description                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| Direction        | Outbound (we sent) or Inbound (we received)                       |
| Status           | Queued → Sending → Sent → Delivered → Read / Failed / Bounced / Cancelled                               |
| Channel          | Medium used                                                                                             |
| Provider Account | Which account handled delivery                                                                          |
| Person           | Recipient/sender linked to the spine                                                                    |
| Reference        | The triggering document (e.g., a Withdrawal Request) |
| Idempotency Key  | Unique per logical message — guarantees no double-send                                                  |

Status only moves forward. Delivery timestamps (sent_at, delivered_at, read_at) are stamped as each transition occurs.

Administrators can bypass the throttle queue for an urgent log using the **Deliver Now** button on the log form.

## Portal Inbox

Students, instructors, and staff access their messages at **Portal > Inbox**. The inbox supports:

- **Received / Sent** tab toggle
- Filter by channel, category, or unread-only
- Click a message to expand it; first expand marks it as read
- **Compose** to start a new message:
  - Students can message their instructors (filtered to shared courses)
  - Instructors and staff can message students, with an optional course filter and an _All Students_ shortcut
- **Reply** to a received message — threaded back to the sender (within your messaging scope)

The **Inbox** item in the portal sidebar carries an **unread count badge**.

## Desk Communication Inbox

Staff triage incoming communications from a dedicated desk page: **Desk → Communication Inbox** (`/app/communication-inbox`). It's a two-pane view — conversations on the left (one per Person, newest first; _Unread_ or _All_), the full thread on the right (inbound and outbound, chat-style). Opening a conversation marks its inbound messages read; the reply box sends a threaded response on the **same channel the person used** (a Telegram question gets a Telegram reply), falling back to In-App. The desk navbar shows an **unread badge** (inbound messages awaiting triage) via the standard notification config. Replies and inbound messages are linked through the Communication Log's `in_reply_to`, and every message still lands on the Person's _Conversation_ timeline.

## Communication Preferences

Recipients manage their channel preferences at **Portal > Preferences**. From there they can:

- Set their preferred language for communications
- Opt in or out of Transactional and Promotional categories per channel (Emergency is always active)
- Edit their **mailing address** (where printed letters go) — written straight to their Person, the single source of truth
- View their registered channel addresses (email, mobile, Telegram chat id)
- Connect their Telegram account via the signed deep-link button

The mailing address lives on the **Person** record (not duplicated onto Student/Alumni). Role records that need to show it — e.g. Alumni Profile — mirror it read-only via `fetch_from`, so there is one place to edit and no drift. Staff can still set it on the Person form (or, for students, on the Student record at intake, which seeds the Person).

## Announcements

[Seminary Announcements](../modules/announcements.md) route through the Communication Log. An announcement picks a **category** (default Academic — set Emergency for a campus closure to bypass consent and the hourly throttle), one or more **channels** (default Email + In-App; add SMS / WhatsApp / Telegram for urgent reach), and an audience that can now include **All Alumni**. Each recipient × channel becomes one log; rich channels (Email, In-App) carry the full message, while length-limited channels (SMS / WhatsApp / Telegram) carry the **Short Message** (or the message stripped to plain text). Duplicate sends are deduplicated automatically by idempotency key.

## Delivery and throttling

Outbound messages are queued (status = Queued) and drained by a background job that runs every five minutes. Each Channel Provider Account has an **Hourly Limit**; the drainer sends at most `limit − messages_sent_in_the_last_hour` messages per account per run.

Emergency messages bypass the limit and are delivered immediately.

In-App messages are also delivered immediately at queue time — there is no carrier to rate-limit, and the portal inbox should never wait for the cron drainer.

Failed deliveries are retried up to three times with exponential back-off (5 → 10 → 20 minutes). After the third failure the log status moves to Failed and a Frappe Error Log is written.
