# 068 — Person-first identity, the shared-attribute registry, and geolocation

**Date:** 2026-09-03
**Status:** Proposed — supersedes ADR 042 §3–§4 and closes ADR 046's deferred address reconciliation

## Context

ADR 067 stalled on data that was not there: its two matching rules need `gender` and coordinates for
both the student and the mentor, and the spine holds neither for most people. Asking *why* found
something larger than 067's own gaps.

**042's central decision was right.** Person as a spine *beside* the role doctypes has paid off —
Partner Contact (053), internship supervisors (054), Academic Unit Membership (062) and Cohort
Membership (066) all key on Person for people who hold no academic role at all. `External Examiner` is
the shape working as intended: `person` reqd and writable, `examiner_name`/`email` as
`fetch_from person.*` + `read_only`, autoname `EXAM-.#####`, controller body `pass`.

Two of 042's clauses were not right.

**There is no canonical list of what a shared human attribute is.** Each seam invented its own subset
and the subsets disagree. `ensure_person()` accepts names, mobile, language, country, image and gender
but **no address at all**, so 046's "registrar-intake snapshot seeds the Person" has never once been
true. `propagate_to_roles()` pushes six fields to Student, six to Applicant, two to Instructor, one to
Alumni Profile — no gender, no address, anywhere. `_apply()` clobbers only `IDENTITY_FIELDS`, leaving
`gender`, `country`, `image` and `language` permanently fill-only even under `overwrite=True`;
`FILL_ONLY_FIELDS` is declared and referenced nowhere. And 042's own protection mechanism,
`read_only_depends_on: eval:doc.person`, shipped on exactly five Student fields — precisely the five
that `propagate_to_roles` pushes. The protected set and the propagated set are the same arbitrary
subset, and every field outside it is an unmanaged second home. This is the mechanism behind the spine
feeling like "another doctype to manage".

**Three of the four role doctypes are keyed on mutable personal data** — the exact data 042 exists to
make non-authoritative. `Instructor` autonames `format:{instructor_name}` with 21 doctypes holding a
Link to it (14 in seminary, 7 in aretenic), which is why `person.py` sets `targets["Instructor"] = {}`
deliberately and a corrected name on the spine stays stale forever. `Alumni Profile` autonames
`field:email`, in the app whose ADR says email is data and never a key. `Student Applicant` welds the
given name into the docname and every audit trail. Only `Student` is clean.

042 §3 chose `read_only_depends_on` over `fetch_from` for one stated reason — *"which leaves them
typeable on the creation form where `fetch_from` would not."* Making the Person exist first removes
that reason, and with it the need for a hand-maintained propagation list.

The system is pre-production and holds only test data. Every change here is cheap now and expensive
later.

## Decision

### 1. Person first, everywhere but one named place

`person` becomes **reqd and writable** on `Student`, `Instructor` and `Alumni Profile` (it is
`read_only` today, and `reqd` + `read_only` would make them uncreatable). A single
`seminary/seminary/intake.py` creates a role record against a Person that already exists; each role
controller's `_resolve_person` is deleted. This is not optional tidying: `_validate_links` runs before
`before_insert`, so a `person` set inside `validate()` is only fetched on the *second* save.

**`Student Applicant` is the single exception, and it is named as one.** A guest genuinely has no User
and cannot write a Person, so intake captures onto the applicant and `after_insert` promotes through
`ensure_person()`. 042 §4 was right about this. What changes is that it stops being one of two
symmetric "onboarding heads" and becomes the one documented exception to a single rule.

We rejected requiring registration before application. It is the only shape that removes the exception
entirely, and it costs real admissions conversion and forces a separate path for staff-keyed paper
applications.

### 2. One registry names every shared human attribute

`seminary/seminary/person_fields.py` is the only place a shared attribute is declared. It drives
`ensure_person`/`update_person`'s signatures, `_apply`'s branching, `propagate_to_roles`' targets, the
`fetch_from`/`read_only` flags in the doctype JSONs, and 067's mandatory-field curation. A test asserts
the JSONs agree with the registry, so adding a field and forgetting a doctype fails the suite rather
than becoming the next hole.

Write semantics are declared, not inferred: `AUTHORED` fields are last-write-wins under
`overwrite=True` but **never blank** (a cleared intake field is an omission, not a correction);
`FILL_ONLY` fields only fill blanks. `FILL_ONLY_FIELDS` is deleted and `IDENTITY_FIELDS` folded in.

### 3. A role binding is a Mirror or a Snapshot — declared, never inferred

This is the distinction 042 did not draw, and it is the one that matters most.

A **Mirror** is `fetch_from person.*` + `read_only`, always current. It answers *"who is this person
now"*: the identity fields on Student, Instructor and Alumni Profile, a gradebook row, an attendance
row, a faculty picker.

A **Snapshot** carries **no `fetch_from`**. It is written once by the controller at a named capture
moment and never re-fetched. It answers *"what was recorded at the time"*.

`Program Enrollment.student_name` is a snapshot implemented as a mirror. It is `fetch_from:
student.student_name` on a submittable doctype, and it is the name that reaches the diploma. A student
who changes their name after a degree is complete must **not** have that name change on the completed
enrollment; whether they may change it on an open enrollment is school policy. Today the field
re-fetches on every save including `on_update_after_submit`, so any later touch of a completed
enrollment silently rewrites the legal name. `Graduation Request.phonetic_name_snapshot` has the same
contradiction in its own name. Only the last hop is correct — `Diploma.legal_name` and `phonetic_name`
are plain `Data` with no `fetch_from`.

```
Person.full_name → Student.student_name → Program Enrollment.student_name → Diploma.legal_name
   Mirror              Mirror              SNAPSHOT (currently a mirror)     already a snapshot
```

Every downstream `fetch_from` of a registry field is classified. Program Enrollment, Graduation
Request, Withdrawal Request, Student Log and Student Leave Application become snapshots; attendance,
group membership, gradebook and submissions stay mirrors. Program Enrollment captures at enrollment,
permits staff re-sync while open, and freezes once completed or conferred. The precedent already
exists: `Partner Job Application.primary_email`/`primary_mobile` are controller-filled snapshots whose
`fetch_from` was deliberately removed.

### 4. Mirror the read-heavy columns; delete the rest

`student_name` alone has ~248 source references — 31 in reports (five inside raw SQL in report JSON),
three print formats, 20+ doctypes mirroring it downstream, and oikonomos using it as a `title_field`.
Deleting it is a rewrite whose report and print-format half fails silently at render. So the columns
with real readers stay, as read-only `fetch_from` mirrors, and only the columns with almost none are
deleted: Student's six address fields (read outside the form in two places, one of which already
prefers the Person), plus `date_of_birth`, `blood_group`, `nationality` and `phonetic_name`, all moved
onto Person first.

Two Frappe facts constrain this and are recorded here because the design depends on them. **`read_only`
is not enforced server-side** — only `permlevel` is, and `db.set_value` checks nothing — so what
actually prevents drift is that the next `.save()` re-fetches and overwrites; every bypass still has to
be fixed on its own merits. And **a null source blanks the mirror**, which is correct mirror semantics
but defeats `person.py`'s "never blank a required email mirror" guard. We therefore guarantee the
source instead of guarding the target: `reqd` is dropped from mirror fields and an
`assert_reachable(doc)` in `Instructor`/`Alumni Profile.validate` throws naming the *Person*.

### 5. Opaque primary keys for all four role doctypes

`Instructor` → `INST-.#####`, `Alumni Profile` → `ALUM-.#####`, `Student Applicant` → `APP-.#####`.
`Student` is already opaque, which is what keeps oikonomos (3 `Link → Student`, no Instructor links)
and frappe_giving (none) entirely out of scope; aretenic's 8 `Link → Instructor` fields are in scope
and `rename_doc` handles them, since it queries `tabDocField` rather than scanning per app.

`allow_rename` is off on Instructor and explicitly `0` on Alumni Profile, so the patch must flip both
and run post-sync. `show_title_field_in_link` is set on none of the three, so without adding it every
faculty picker would render `INST-00001`.

Once the keys are opaque, `propagate_to_roles` can finally carry `Instructor.instructor_name` and
`Alumni Profile.email`, which were excluded only because they were docnames. Both mirrors are `unique`,
and propagation writes with a bare `db.set_value`, so pushes to a unique mirror are pre-checked rather
than raising `IntegrityError` out of `Person.on_update`.

### 6. Person absorbs the attributes that had nowhere to live

`date_of_birth`, `nationality`, `phonetic_name` and `mailing_country`, plus a sensitive block —
`blood_group`, `marital_status`, `ethnicity` — at `permlevel: 1`. Person has zero permlevel-1 rows
today, and without adding them the fields would be silently unwritable for Registrar and Seminary
Manager while still working for Administrator, which is how such a mistake survives a smoke test.

`mailing_country` is separate from `country` on purpose. `country` drives comms provider routing (042
§6, 043) and `alumni_profile.mailing_country` already fetches it, conflating a postal address with an
SMS provider selector. Without the distinct field, deleting `Student.country` would make a student's
self-service profile edit write their postal country into the routing selector.

`Student Applicant.gender` is a Select of the literals `Male`/`Female` while `Person.gender` is a Link
to `Gender`, and `setup_genders()` enables the *translated* names — so every hand-off is guarded by
`frappe.db.exists("Gender", …)`, the guard `person_import_batch.py` already uses.

### 7. Geolocation belongs to the spine, not to the mentor engine

Coordinates are reachability data about a human, the same category as the postal address 046 put on
the spine. `Person` gains `latitude`, `longitude`, `geocoded_on` and `geocode_precision` at
`permlevel: 1` — a home coordinate is more sensitive than the address it came from, because it is
trivially mappable.

A `Geocoding Settings` single, modelled on `Pexels Settings`, selects Google or a **vendor-proxied**
mode in which our own endpoint carries a site token, so hosted schools configure nothing.
`integrations/geocoding.py` goes through the existing `integrations/client.py` helper and so inherits
Integration Request logging, the pattern `bible.py` and `pexels.py` follow. Nominatim was rejected: its
usage policy forbids this shape of lookup, and self-hosting means owning the data refresh forever.

Geocoding is **queued on address change and never inline** — an intake form must not block on a third
party and a failure must not fail the save. It runs once per change and caches; never on read, never on
a schedule, because for hosted schools every call is billed to us and a person's coordinates change only
when their address does. Failures leave the coordinates null, which 067's readiness check surfaces.

Coordinates are `derived`: nobody types a latitude, so "mandatory" for them can only mean *resolvable*,
checked by a pre-flight rather than by `reqd` on a form.

ADR 067 keeps the distance ranking and what it means for placement; this ADR owns having the coordinate
at all.

### 8. The bypasses are closed as part of the work

Each of these is a live defect independent of this ADR's merits, and each would survive the
architecture unless named: `save_student_profile` writes a student's own address and mobile straight
onto `Student` with `db.set_value`, so every self-service edit diverges permanently and is then
reverted by the next Person save; `save_instructor_profile` sets `instructor_name` without renaming, so
`name` and `instructor_name` diverge; `enroll_student`'s bare mapper drops the `contacts` child table,
discarding emergency contacts and references at admission; `_apply_person_address` writes with
`db.set_value` and so would bypass the geocode trigger too; `Student.validate_user` creates a User
inside `validate()`, committing the User and its role grant even when the Student then fails.

## Consequences

**Easier.** One declared list of shared attributes, enforced by a test rather than by memory. One
writer for personal data, with `fetch_from` maintaining the read side instead of a hand-written push
list. A legal name change becomes a field update rather than a rename cascade through 21 link tables,
and a corrected name finally reaches every instructor. 067's Phase I-bis disappears entirely, and its
`Mandatory Personal Field` doctype becomes a thin curation layer over this registry instead of a second
parallel one.

**Harder.** Gender capture narrows: `Student.update_person_links` is today the only path that writes a
gender to the spine, and mirroring `Student.gender` removes it. Person is writable by Seminary Manager
and Registrar only, so afterwards gender arrives from the applicant form, the importer, or a Registrar
in Desk — nowhere else. That is precisely the datum 067's `match_gender` rule depends on, so 067's
readiness pre-flight must account for it.

**Known and deferred.** For the chains that stay mirrors, multi-hop freshness is unchanged:
`propagate_to_roles` writes hook-free and `fetch_from` refreshes only on each document's own save, so
the third hop (`Course Enrollment Individual.student_name`) stays stale until something touches it.
Fixing it means either cascading propagation down declared chains or re-fetching on read. This is a
mirror-side limitation only — the snapshot chain is not stale, it is correct.

Also deferred: backfilling coordinates for people who already have addresses; a retention decision for
`social_security_number`, which is a plaintext field on a public form that is dropped at admission and
never purged (and note that because Frappe leaves the column when a docfield is removed, "deleting" it
later is not deletion); and the applicant record remaining the sole home for the doctrinal signature,
testimony and disability accommodation request.

**Not adopted.** Frappe's `Address` and `Contact` remain rejected — a large engine built on core
doctypes breaks on upgrade, and this is the reason the mailing address lives on Person in the first
place (046). `Student`, `Instructor` and `Student Applicant` are vendored into seminary
(`required_apps = []`), so reshaping *them* carries no upgrade risk at all.

`comms.send_to_role` and `communication_triggers` create Person rows as a side effect of messaging.
This is correct — staff need spine rows — but it is a third creation head and is recorded here so the
next reader does not mistake it for a leak.

## Phasing

1. The registry, deriving `person.py` from it. No behaviour change.
2. Person absorbs the missing attributes, with permlevel rows and the backfill.
3. Opaque primary keys, with `allow_rename`, `show_title_field_in_link`, and the applicant payment
   endpoint gated (sequential ids make an untokenised guest endpoint materially easier to enumerate).
4. Mirrors, deletions, and the Mirror/Snapshot classification.
5. `intake.py`, `person` reqd, and the bypasses.
6. Geolocation.
7. The applicant boundary and the per-program web forms.
8. Tests, and the revision of 067.

Phases 2 → 3 → 4 are patch-ordered and must stay in that order; `patches.txt` has no dependency
declarations, so file order is the contract.
