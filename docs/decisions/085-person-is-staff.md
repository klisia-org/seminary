# 085 — Who is staff: a derived flag on Person

**Date:** 2026-10-02
**Status:** Accepted 2026-10-02
**Related:** 042 (Person is the spine); aretenic 057 (stewards are chosen from staff)

## Context

Several features need "staff only": a picker that is not flooded by hundreds of students, and a
way to notice when an employee leaves. Seminary answers "is this person staff?" in eight places,
each with its own role set, and they disagree (Registrar is staff in some and not others). Nothing
is stored, so a list cannot be filtered by it, and an employee who is also an alumnus or a student
cannot be told apart from one who is not.

## Decision

1. **Person gains `is_staff`** (Check, read-only, derived). It is true when the person's user is
   enabled and holds at least one staff role. Alumni, Student, Partner and Cohort Participant are
   not staff roles, so an employee who is also an alumnus is staff, and a student is not.
2. **Staff roles are defined once.** `seminary.seminary.staff.staff_roles()` returns seminary's
   list (Instructor, Program Chair, Registrar, Seminary Manager, System Manager) plus the roles
   other apps add through a `staff_roles` hook.
3. **It is kept current where it changes:** when a user's roles or enabled state change, when a
   Person's user changes, and by a patch that fills it on existing sites. A change to `is_staff`
   is published as a document event, so apps can react to someone leaving.
4. The eight existing role sets stay as they are for now. Moving each onto `staff_roles()` is
   follow-up work, case by case, because some differ on purpose.

*Rejected: an active Academic Unit Membership.* It matches the org chart, but board members are
members too, and staff with no unit would be missed.

## Consequences

- Staff pickers filter on one field, and an app reacts to a leaver without polling.
- A role granted for a single task makes someone staff. Roles stay the source of truth, so the
  answer is to grant the narrower role.
- Open: the eight role sets that remain until they are moved.
