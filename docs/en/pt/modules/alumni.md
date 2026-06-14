# Alumni

When a student finishes their program they don't disappear from the seminary's
life — they become part of its network. The **Alumni** module keeps a lasting
record of every graduate, lets graduates maintain their own contact and
professional details, and offers an opt-in **directory** so alumni can find one
another. It is deliberately light: graduates manage most of their own
information from the portal, and staff only step in to admit someone to the
alumni rolls or to keep the data honest.

## Overview

The module is built around a single record, the **Alumni Profile**, plus the
**Alumni** role that unlocks the alumni area of the portal.

```
Program Enrollment (graduated)  --Mark as Alumni-->  Alumni Profile  +  Alumni role
                                                          │
                                                          ├─ the graduate edits their own profile
                                                          └─ opt-in entry in the alumni directory
```

- An **Alumni Profile** holds who the graduate is, what they completed, where
  they are now, and how to reach them.
- The **Alumni** role is granted automatically when a profile is created. It is
  what gives the graduate access to the **Alumni** menu on the portal.

## Becoming an alumnus

There are two ways a profile comes into being.

### From a graduating student (the normal path)

Staff (Registrar, Program Chair, or Seminary Manager) open the student's
**Program Enrollment** and choose **Mark as Alumni**. The system only allows
this when:

- the Program Enrollment is **submitted**,
- the program is **not** an ongoing program (ongoing programs never transition
  to alumni status), and
- the student is **graduation-eligible** according to the Program Audit.

When those hold, a profile is created automatically — the graduate's name,
program completed, originating enrollment, and **class year** (taken from the
enrollment's conclusion date) are all filled in for you, and the graduate
receives the **Alumni** role. Each person can have only one profile; marking an
already-converted student again simply returns the existing one.

### Honorary, transfer, or board members (manual)

Not every alumnus comes through a graduation. To add an honorary graduate, a
board member, or someone whose study predates the system, create an **Alumni
Profile** by hand. The only requirement is a **linked User account** — that is
what ties the profile to a login and lets the person manage it on the portal.

## The alumni profile

A profile is organized into a few simple sections:

- **Identity** — name, email (kept in sync with the linked User), the original
  Student record if there is one, a photo, and two switches: **Enabled** and
  **Show in Directory**.
- **Academic** — program completed, class year, and the enrollment they
  graduated from.
- **Professional** — current role, organization, and LinkedIn.
- **Mailing address** and a free-text **Bio**.

Two flags govern visibility, and **both** must be on for a profile to appear in
the directory:

| Flag                  | Meaning                                                                                                                  |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Enabled**           | The profile is active. Turn it off to retire a record without deleting it.               |
| **Show in Directory** | The graduate has chosen to be listed. Graduates control this themselves from the portal. |

## What the graduate sees on the portal

Once they have the Alumni role, graduates see an **Alumni** entry in the portal
menu. From there they can:

- **Edit their own profile** — name, current role and organization, LinkedIn,
  city, country, bio, and whether they appear in the directory. (Academic facts
  like program and class year are set by the seminary and are not
  self-editable.)
- **Search the directory** — browse fellow alumni by name, role, organization,
  or city, and filter by **program** or **class year**.

The directory only ever shows profiles that are both **Enabled** and **Show in
Directory**, so a graduate who would rather stay private simply leaves the
directory switch off. Directory access itself requires the Alumni role — it is
not public.

## Day-to-day for staff

| Task                                           | Where                                                            |
| ---------------------------------------------- | ---------------------------------------------------------------- |
| Admit a graduating student to the alumni rolls | Program Enrollment → **Mark as Alumni**                          |
| Add an honorary / board / pre-system alumnus   | New **Alumni Profile** with a linked User                        |
| Retire a record without deleting it            | Untick **Enabled** on the profile                                |
| Remove someone from the directory              | Untick **Show in Directory** (or ask them to) |
| Correct a graduate's academic details          | Edit the Alumni Profile directly                                 |

## Related

- [Graduation Request](graduation-request.md) — the step that confirms a student
  has actually graduated.
- [Programs](program.md) — where "ongoing" programs (which never transition to
  alumni) are defined.
- [User Roles](../administration/user-roles.md) — what the **Alumni** role can
  and cannot do.
