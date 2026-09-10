# 070 — Alumni reachability: peer contact, address verification, and cohort invitations

**Date:** 2026-09-08
**Status:** Proposed

## Context

ADR 064 let an alumnus start their own cohort from the portal, and `create_my_cohort` makes that
one click. The second step is the wall. To fill a cohort a leader must find people, reach them,
and discover — one refusal at a time — that most of them are already in a cohort of that type,
because `Cohort Type.max_lineages_per_member` defaults to 1 and `_guard_lineage_limit` only speaks
at save.

The directory that should answer this shows a name, a role, a city and a LinkedIn link. It has one
free-text box, no pagination past the server's cap of 100, and no contact details at all. The
`program` and `class_year` parameters `directory_search` accepts have never been sent by the UI,
and `docs/en/modules/alumni.md` promises filters that do not exist. `bio` is editable on the
profile and rendered nowhere.

The reason contact details are absent is sound: nothing in the system said which of a person's
addresses they were willing to show a peer. `CommunicationPreferences.vue` states the position
plainly — *"Contact the registrar to change these."* — and there is no write endpoint behind it to
say otherwise.

The obvious shortcut is to reuse what already exists. `Person Consent` is a channel × category
grid, and "Community" is one of its five categories, so a Community opt-out could double as "don't
show me to peers." That would be the wrong reuse, and ADR 067 §10 already ruled on the shape of
it: *"Consent belongs at collection. `Person Consent` is channel-scoped and drives comms routing;
bending it to cover data-use would break that."* Concretely, it would mean a graduate who does not
want peer email also stops receiving cohort invitations, which are sent as Community by
`_deliver_invite` — the seminary silencing itself to honour a directory preference. ADR 045 drew
this line once already, targeting announcements at `enabled` rather than `show_in_directory`,
*"directory visibility is a public-listing concern, not reachability."* This ADR is the other half
of that sentence.

Planning the work surfaced that the pieces it would rest on are not load-bearing yet.

**`verified` means almost nothing.** Only `telegram_adapter._handle_start` ever sets it, and that
one is genuine — a signed deep-link token proves possession of the chat. Everywhere else it is a
checkbox a registrar ticks. `EmailAdapter.final_status` is `"Sent"`, so an email address is never
confirmed by anything; and the reverse never happens either. `_apply_status_event` writes
`Failed`/`Bounced` onto the `Communication Log` and stops there:

```python
if new_status in ("Failed", "Bounced"):
    log.db_set({"status": new_status, "error": _("Reported by provider webhook.")}, ...)
```

Nothing writes `Person Channel Address.status`, so its `Bounced` and `Invalid` options have never
been reachable. A hard-bouncing address stays `Active` and `verified` for good. Publishing that to
peers would publish a typo — and a typo'd address is a stranger's inbox.

**The photo a person uploads is not stored, and would not be shown if it were.** Three defects in a
row. `person_fields.py` declares `Spec("image", mode=FILL_ONLY)`, and `_apply` honours
`overwrite=True` only in the `AUTHORED` branch, so `save_student_profile → update_person(image=...,
overwrite=True)` silently drops every upload after the first — the same defect `gender` was moved
out of `FILL_ONLY` for in ADR 068 phase 4. Nothing then syncs `Person.image` to `User.user_image`,
which is what the sidebar avatar reads. And `directory_search` already returns `image` while the
page renders initials.

## Decision

**Directory sharing is per-address state on the spine, deliberately outside `Person Consent`.**
`Person Channel Address` gains `share_in_directory` (Check, off by default), `source` (Select,
blank-first) and `verified_on`. The flag is named for what it is rather than for who reads it:
`Person` is the students' spine too, and ADR 042/068 push against baking a role into it. A
student's row carrying an unread flag is harmless, and is quietly right the day they graduate —
the address they already chose to share does not need choosing again.

It cannot live on `Alumni Profile`. Per-address state needs a key to an address, and Frappe cannot
Link to a child row; keying on `(channel, value)` instead drifts the moment the address is edited.

**Provenance decides who may edit, so it is a Select and not free text.** `Person Consent.source`
is a `Data` note nobody branches on. This one governs a permission, and a free-text field that
governs a permission is one typo from a privilege bug. Blank-first is the migration: every existing
row reads as not-self-service and is therefore locked, so the safe default is the do-nothing
default and no patch is needed. It is not `row.owner`, because `sync_primary_channel_addresses`
appends the primary email during whatever save happens to be running — a portal save would stamp
the alumnus as owner of a system row. Provenance has to be a stated policy, not an artefact of who
saved.

**Editing an address and sharing it are different capabilities.** An alumnus may add addresses, and
may edit or remove the ones they added; registrar rows stay locked, and `is_primary` is not theirs
to move. But *sharing* works on any row on their own Person, including the registrar-created
primary — it changes visibility, not the datum. Tying the two together would leave the typical
alumnus, who has exactly one registrar-created email, permanently unable to share anything.

**`verified` gets a definition and two feedback loops: confirmed-deliverable-and-possessed.**
Adding an address sends a Transactional confirm mail to *that address* carrying a signed link;
clicking it verifies the row. The token reuses `telegram_adapter.make_connect_token`'s shape — HMAC
under the site encryption key, no doctype — with three differences worth naming: the address is
inside the signature, so a token cannot be replayed against another row; it expires, because an
email sits in an archive forever while a Telegram deep link is pasted within seconds; and it is 32
hex characters rather than 12, since only Telegram's start-parameter grammar constrained the
original. It resolves the row by `(person, channel, value)` rather than by name, because the token
is stateless and the row may have moved.

The confirm surface is a `www` page, not a whitelisted guest method: guest-reachable by
construction, with no JSON endpoint to probe. **It must work logged out** — the mail opens in a
phone's mail client, and the address being confirmed is frequently not the login email, so "sign in
first" is both a dead end and a leak through the login redirect.

In the other direction, a provider verdict on an address is a fact about the address and not only
about one message: a `Delivered` webhook verifies the row, and a bounce marks it `Bounced` and
clears `verified`. **Only `Bounced`, never `Failed`.** `Failed` is also what an outage or a
rate-limit rejection produces, and marking on it would permanently disable good addresses during an
outage with nobody told. What this needs instead is one alias corrected: Twilio's `undelivered` is
a carrier rejecting the address, which is a bounce, while `failed` is a send attempt that
`MAX_RETRIES` already owns. Twilio channels therefore need no confirm mail — a carrier receipt is
stronger proof than a click.

**Reachability without disclosure is an audience, not a new subsystem.** An alumnus who shares no
address is still reachable, but not through a purpose-built relay: the portal already has
person-to-person messaging. `send_portal_message` composes In-App as Community, `reply_portal_message`
threads a reply back, `get_my_messaging_scope` is the stated authorization source of truth, and
`Inbox.vue` already offers Reply on any Community message with a named sender. What was missing was
only an audience: the rule engine's `Portal Messaging Rule` offers Course Instructors, All Students,
Role and so on, and none of them describes "the people in the alumni directory."

So this ADR adds one audience value, **Alumni Directory**, resolving to profiles that are `enabled`
and `show_in_directory`. Everything else follows for free — compose, threading, sanitization,
private attachments, the Inbox reply button — and the seminary decides whether alumni may write to
each other at all by configuring the rule or leaving it out, which is what the ADR 043 addendum
made the rule engine for.

Building a second endpoint instead would have shipped a visible defect. A relayed message satisfies
`Inbox.vue`'s `canReply` — Community category, named sender — so the Reply button would render, and
`reply_portal_message` would then refuse the reply, because no rule places another alumnus in the
replier's scope. The audience is what makes the button honest.

`audience="Role"` with `audience_role="Alumni"` is close enough to be worth ruling out explicitly:
it reaches every alumnus who holds the role, ignoring `show_in_directory` entirely, so a graduate
who hid themselves would still be listed in a compose picker. Directory visibility has to be the
predicate, not role membership.

**The scope is materialized for pickers, not for permission checks.** `get_my_messaging_scope`
builds every allowed recipient, and `send_portal_message` rebuilds it on each send purely to test
membership. That is affordable for a course roster and not for an alumni body. A targeted
`_may_message(target)` answers the single-recipient question in one query; the full list stays for
the staff compose picker, and the directory never asks for it.

**The sender is named; their address is not.** That falls out of the existing design rather than
being added by it — an In-App message carries `triggered_by` and nothing else. An anonymous relay
would be an abuse machine and an unanswerable message; a named one with no address in it is a
conversation the recipient controls, and answering is their choice to make.

What the directory does add is a limit, because `send_portal_message` has none. It is ledger-backed
rather than `frappe.rate_limiter`, which can key only on IP or a named form field — behind office
NAT that throttles a building and on mobile data it throttles nobody. Counting the caller's own
rows in `Communication Log` is indexed, survives a cache flush, and is already the audit record.

**Cohort invitation is a separate opt-out, enforced where it can be bypassed.** `Alumni Profile`
gains `open_to_cohort_invites` (default on). It is not the same question as directory listing —
"list me, but don't ask me to join things" is a coherent position — but the invite search requires
*both* flags, because `show_in_directory` already governs whether a leader may see the name at all,
and a search that ignored it would be a second, unmoderated way to enumerate people who asked not
to be listed. A leader who knows someone personally still has the unchanged `invite_member(email=…)`
path.

The check belongs on `invite_member`, not only in the search: it takes a raw `person` id, so a
search-side filter is advisory and the opt-out is bypassable by hand. Staff bypass it, because a
registrar seating someone is a decision and the opt-out is about unsolicited portal approaches —
the same line `_guard_size` already draws between `Cohort.max_size` as advice and
`portal_size_limit` as refusal.

**The search returns blocked candidates, disabled, with the reason.** `lineages_that_would_block`
can already answer "would this person be refused, for this cohort, right now." Hiding them would
send the leader to email; showing them silently unpickable would be worse. This is
`create_my_cohort`'s stated principle — declining to create the record it is going to reject —
applied one step earlier.

**The Alumni role is granted when the profile is created, once.** Having a
profile is what makes someone an alumnus, but the role was granted only by
`mark_as_alumni` — so a profile created any other way (a registrar entering a
graduate of another institution in Desk, `intake.make_alumni_profile`, an
import) produced someone listed in the directory who could not open it, and who
could be *sent* a directory message with no way to answer it. This is not a
hypothetical: it is what testing this ADR's own work turned up.

It hangs off `after_insert` rather than `on_update`, and `mark_as_alumni` stops
granting it separately. A role given at creation can be taken away afterwards,
and neither a later edit of the profile nor a second graduation should hand it
back — revocation is a decision, and re-granting on every save would quietly
undo it. The cost is that a profile whose `user` is filled in later gets no
role from this path; the registrar grants it, as they would for any account.

Because that also means an inbox can hold a message from someone the reader is
not permitted to answer, `get_my_inbox` now says whether each message can be
replied to, and the portal's Reply button asks rather than guesses. It was
guessing before this ADR too — any Community message from outside the reader's
scope offered a button that `reply_portal_message` then refused.

**Contact values never appear in a list payload.** They are returned one profile at a time by
`get_directory_profile`, which reports the same error for a profile that does not exist and one
that has hidden itself, so it cannot become an oracle for exactly the people who asked not to be
found. A list endpoint that returns email addresses is a scraper's endpoint.

**`Alumni Profile.current_partner_organization`** lands here as ADR 053 phase 4 specified it: a
Link beside the free text, never replacing it, populated by a non-destructive exact-match patch and
rendered as a badge only where the partner directory is enabled.

## Consequences

**Easier.** An alumnus filling a cohort can see who is available before asking. A graduate controls,
per address, what peers see, without that choice touching what the seminary may send them. `verified`
becomes a claim the system can defend, and a bounced address stops being offered — which improves
routing for every sender, not only the directory. The uploaded photo appears.

**Harder.** There are now two reachability questions about one person — may the seminary send this,
and may a peer see that — and they are answered in different places by different fields. That is
the honest cost of ADR 067 §10; collapsing them is what this ADR refuses to do. The Preferences
page grows from a form into something closer to an account-management surface.

**A weaker guarantee than it looks.** Confirmed-deliverable is not confirmed-consented. A click
proves someone reads that mailbox; it does not prove they are the alumnus. The relay's disclosure
posture, not the verification, is what keeps a mistake recoverable.

**Not decided here.** Whether students should have a directory of their own; whether a partner
organization page should list the alumni who work there (`is_alumni_employer` exists and is unread);
whether the Inbox's flat list should become a threaded conversation view now that peer replies are
routine (`in_reply_to` is already written, and nothing reads it). Nor whether a seminary that wants
peer messaging *without* a directory listing should be able to say so — today the Alumni Directory
audience borrows `show_in_directory`, which conflates two questions that may yet need separating.
The `Person Channel Address.source` values are a starting set: `Import` and `Channel Onboarding` are
declared because writers for them exist today, not because the list is closed.

**Migration.** No patch for `source`: blank is the locked, correct reading of every existing row.
No patch for the Alumni role either, and that one is a deliberate refusal rather than an
oversight — a large share of existing profiles predate the grant and their users do not hold
the role, but nothing in the data distinguishes "never granted" from "revoked on purpose", and
a backfill would silently reverse every revocation to fix a listing. Registrars grant it where
it belongs. Until they do, those people stay listed in a directory they cannot open; the Reply
button at least no longer lies to whoever writes to them.
Three patches do run — `open_to_cohort_invites` set on existing profiles, because an opt-out
introduced default-on should be stated rather than left to column DDL; a non-destructive exact-match
pass for `current_partner_organization`; and a repair for postal country, below.

**Two pre-existing defects are fixed here because this work rests on them.**
`partner/api._alumni_program_level` reads `Alumni Profile.program_completed`, a docfield ADR 069
dropped — and, as that ADR's own migration note records, Frappe leaves the column behind. The query
builder does not validate fieldnames against meta, so it returns a stale pre-migration value rather
than an error, and `NULL` for every alumnus created since. The Program Level gate on
alumni-created organizations has been quietly off, and it decides the button this work surfaces.
Rewritten over `Alumni Graduation` rows, the **most permissive level wins**: the gate already
defaults to allowed when the level is unknown, so requiring every level to allow would be stricter
than having no data at all, and a Master's graduate who also holds a certificate must not lose a
permission the Master's grants.

Separately, `get_my_communication_preferences` returns `person.country` as the mailing country and
writes the submitted one back to it — the provider-routing selector fed to `pick_account`, which
ADR 046 split `mailing_country` out of for precisely this reason. A student correcting their postal
address on the portal could move their messaging region. Fixed, with a backfill that copies
`country → mailing_country` only where the latter is empty and a postal address exists, and never
clears `country`.
