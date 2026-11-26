# 121 — Message notices and phone notifications

**Date:** 2026-11-26
**Status:** Accepted 2026-11-26
**Delivers:** LMS-COL-03 (Yes), LMS-COL-05 (Yes)
**Related:** 043 (channels, Communication Log, portal compose), 045 (announcement channels),
097 (reply notices, unread)

## Context

Students and instructors can already message each other in the portal (043 addendum), but a
message is In-App only: nobody is told it arrived, so an instructor who rarely opens the portal
misses it. Email notices work. For phones there is only SMS/WhatsApp through the Twilio adapter,
which needs the school's own Twilio account, and the portal cannot push to a phone. Canvas,
Moodle and Brightspace all tell the recipient of a new message and push to phones.

## Decision

1. **An unread message is announced by email.** Portal messages, replies and In-App contact
   messages are marked to be announced. A message still unread 15 minutes after it arrived gets
   one email notice through `comms.send()`, in the Community category the messages use, so a
   Community email opt-out also stops it. The notice names the senders and links to the inbox. It
   never carries the body or attachments, which stay private.
2. **One notice per batch.** The window is fixed at 15 minutes. When the oldest unannounced unread
   message for a person reaches it, one notice covers every unannounced unread message they have,
   and each message records the notice that announced it. A message read first is never announced.
3. **Web Push is a channel.** A new *Push* Communication Channel and a `web-push` provider
   (`pywebpush`) send to browsers and installed portals. Its Channel Provider Account holds the
   VAPID key pair, made when the account is created. The portal gets a web manifest and a service
   worker under `/seminary/`, so it can be installed on a phone. A *Push Subscription* (user,
   endpoint, keys, device label, last used) is added from the preferences page and deleted when the
   push service says it is gone. Push logs are sent from a background job as soon as they are
   queued, not by the five-minute drainer.
4. **In-App logs also push.** When a person has a push subscription, every In-App log for them
   queues a Push log with a title, the sender and a link, so §1 messages, 097 reply notices and
   announcements reach the phone at once, without new templates. The Push log points at the In-App
   log. Consent on Push decides it per category, so it is on by default and off for Promotional.
5. **No native app.** Phone coverage is Push plus the existing SMS/WhatsApp adapter.

## Consequences

Messages and reply notices reach a phone with no per-school SMS cost. iOS only shows push for a
portal added to the home screen (16.4+), and the preferences page says so. Seminary now depends on
`pywebpush`. The Twilio adapter gets tests, and 043's roadmap is corrected: the adapter exists.

## Addendum (2026-11-26, before release): one worker for the whole site, and other apps' notices

Accepted 2026-11-26, built the same day. Another portal on the same site needs device notifications too, and a browser should
hold one subscription per site, not one per portal.

1. **The worker is site-wide.** It is served at `/sw.js` with scope `/`. Each portal keeps its own
   web manifest (`/<portal>/manifest.webmanifest`) for installing. A browser that turned
   notifications on in one portal gets them in every portal, with no second prompt.
2. **The device control is shared.** The *Notifications on your devices* section and its browser
   code move to `portal-shell`, so any portal can show it.
3. **Apps send through one helper.** `web_push.notify(person, title, reference, category)` queues
   a Push log when the person has a device and has not opted out, and does nothing otherwise.
4. **Links come from the record's app.** A `push_links` hook maps a reference to the page its
   reader works from. Without one, staff get the Desk form and everyone else the portal home.
