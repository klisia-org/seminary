# 110 — LTI 1.3 and LTI Advantage tools

**Date:** 2026-11-24
**Status:** Accepted 2026-11-24; implemented 2026-11-24
**Amends:** 108 §4 (LTI links come across)
**Delivers:** LMS-STD-01 (Yes)
**Related:** 082 (due dates), 105 (teaching roles), 107 (chapter release), 108 (course migration),
p009 (SCORM grade passback)

## Context

Schools use outside tools inside their courses: publisher textbooks, Bible and language software,
video platforms, plagiarism checkers. Every major LMS connects them through LTI 1.3. Seminary
can't, so 108 skips LTI links in imported courses and asks the school to rebuild them. Reviewers
ask for LTI Advantage: Deep Linking (choose content in the tool), Names and Roles (the class
list), and Assignment and Grade Services (scores back). LTI 1.1 alone is outdated. Seminary acts
as the *platform*. Python LTI libraries are written for tools, so the platform side is ours to
build, on PyJWT and `cryptography`, which Frappe already ships.

## Decision

1. **LTI Tool** registers one tool per site. It holds our generated client id and deployment id,
   the tool's login, launch and redirect URLs, its key-set URL, the services it may use, and two
   privacy checkboxes: *Send name* and *Send email*, both off by default. It can be registered by
   pasting a Dynamic Registration URL, or by hand.
2. **Platform keys.** The site has one RS256 signing key, stored encrypted and published at
   `/lti/jwks` with its `kid`. Rotation adds a new key and keeps the old one published for a day.
3. **Launch.** A Course Lesson can be an LTI link, like a SCORM lesson: *LTI Tool*, a resource
   link id, and custom parameters. Opening it runs the OIDC third-party login, then sends a
   signed id_token. Nonce and state are single-use and expire in five minutes. It opens in a new
   window by default, or embedded if the tool allows it. The launch honours 107's release dates
   and prerequisites. Observers and mentors see the link but can't launch it.
4. **Roles** come from 105: students launch as Learner. A category that *Edits course content*
   launches as Instructor. A category that only *Grades* launches as Instructor and
   TeachingAssistant.
5. **Deep Linking 2.0.** Anyone who may edit the course can *Add from tool* in a chapter. Each
   returned link becomes an LTI lesson. A returned line item becomes a Scheduled Course Assess
   Criteria row with weight 0, as 108 imports graded work.
6. **Names and Roles** returns the section's active enrollments and teaching staff with the roles
   in §4. It includes names and emails only if the tool sends them at launch (§1).
7. **Assignment and Grade Services.** Each LTI lesson is one line item. A tool may read it, with
   the mapped criterion's title and 082's due date as `endDateTime`. It may not create or delete
   line items. Every score posted is kept on an **LTI Score**. It reaches the gradebook only
   through the lesson's mapped criterion, under p009's rules: competency sections stand down, a
   grader's hand-entered number wins, the cell shows where its number came from, and only
   `FullyGraded` scores report.
8. **Tokens.** `/lti/token` takes a client-credentials grant signed with the tool's key
   (`private_key_jwt`). It issues hour-long tokens for the scopes the tool was granted, limited to
   the courses with that tool's lessons.

Rejected: letting tools create gradebook rows through AGS. It is simpler for tools, but it would
change course weights without an instructor. Using Frappe's OAuth provider for tokens: it
authenticates with a client secret, and LTI requires a signed assertion.

## Consequences

Faculty can add a publisher's or vendor's material from inside the course, and the scores come
back. Schools register a tool once per site. Privacy defaults to sending no names or emails, so
a tool that needs them must be turned on deliberately. Scores are a tool's claim. Unlike SCORM,
they come server to server, but they are still gated by the instructor's mapping. Seminary will
not be 1EdTech certified at first. The build is tested against 1EdTech's reference tool and a
real tool (Moodle as a tool). Imported courses keep their LTI links when the tool is registered
first (108 §4).

## As built

- The routes are a page renderer (`lti/renderer.py`), not `/api/method/`: the protocol fixes
  their URLs, bodies and media types.
- §3: the tool returns the browser with a cross-site request that carries no Frappe session,
  because the cookie is SameSite=Lax. So `/lti/auth` takes the user from the launch hint: one
  user, five minutes, used once, answered only to a registered redirect URL. If a session is
  present, it must be the same user. The auth and deep-link pages carry their own CSP, because
  the site's policy has `form-action 'self'`.
- §8: Frappe treats any `Authorization: Bearer` header it doesn't know as a failed login, before
  routing. A `before_request` hook moves the header aside for `/lti/` paths only.
- §2: the first key is often created on a GET, so that request is flagged to commit.
- `sub` is per tool, keyed with the site's secret, like the SCORM learner id.
- §7: an older `timestamp` changes nothing. Scores for anyone not on the active roster are
  refused.
- 108 §4: a tool is matched on the host of its launch or login URL. Packs (041) and template
  copies (014) carry the tool, the URL, the custom parameters and the mapping. A pack names the
  tool, or failing that the host it is matched by.

