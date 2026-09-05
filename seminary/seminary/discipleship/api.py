"""Cohort self-management operations (ADR 064, Phase 1).

Leaders invite members and, where their Cohort Type allows it, split / multiply
a cohort — always retaining leadership and lineage. These whitelisted methods
are the guarded entry points; they check leader capability (or staff) and then
write with ignore_permissions, the same posture as the partner portal API.

Onboarding of brand-new people rides ensure_person() (ADR 042 — the single
mutation point). Delivering invites over comms.send() and auto-enrolling billable
cohorts into their backing course land in later phases; this phase just moves the
membership records correctly.
"""

import frappe
from frappe import _
from frappe.utils import today, cint

from seminary.seminary.person import ensure_person, find_person
from seminary.seminary.discipleship.permissions import STAFF_BYPASS


COHORT_PARTICIPANT_ROLE = "Cohort Participant"


def _is_staff(user):
    return bool(set(frappe.get_roles(user)) & STAFF_BYPASS) or user == "Administrator"


def _grant_participant_role(user):
    if (
        user
        and frappe.db.exists("Role", COHORT_PARTICIPANT_ROLE)
        and not frappe.db.exists(
            "Has Role", {"parent": user, "role": COHORT_PARTICIPANT_ROLE}
        )
    ):
        # A leader inviting a pastor is a non-staff portal user; add_roles() saves
        # the User, so it needs elevated permissions like the rest of onboarding.
        u = frappe.get_doc("User", user)
        u.flags.ignore_permissions = True
        u.add_roles(COHORT_PARTICIPANT_ROLE)


def _ensure_participant_user(person_doc):
    """Provision a light portal User for an external invitee (a pastor with no
    account yet) and grant the Cohort Participant role. Existing users are left
    alone. Returns the user id, or None when the Person has no email."""
    if person_doc.user:
        return person_doc.user
    email = person_doc.primary_email
    if not email:
        return None
    if frappe.db.exists("User", email):
        user = email
    else:
        u = frappe.get_doc(
            {
                # System User like Student/Alumni portal users — the Cohort
                # Participant role carries desk_access so they don't error at
                # /app, and get_list works (Website Users can't query these
                # doctypes). They're still redirected to /seminary/community.
                "doctype": "User",
                "email": email,
                "first_name": person_doc.first_name or email,
                "last_name": person_doc.last_name or "",
                "send_welcome_email": 0,
            }
        )
        u.flags.no_welcome_mail = True
        u.insert(ignore_permissions=True)
        user = u.name
    _grant_participant_role(user)
    person_doc.db_set("user", user, update_modified=False)
    return user


def _deliver_invite(membership, person_doc):
    """Send the invite over the comms ledger (In-App + Email), never ad-hoc mail."""
    from seminary.seminary import comms

    cohort_name = (
        frappe.db.get_value("Cohort", membership.cohort, "cohort_name")
        or membership.cohort
    )
    subject = _("You've been invited to {0}").format(cohort_name)
    message = _(
        "You've been invited to join the cohort <b>{0}</b>. Sign in and open the "
        "Community to accept. If this is your first time, use “Forgot password” on "
        "the login page to set your password."
    ).format(cohort_name)
    inviter_user = frappe.session.user
    try:
        if person_doc.user:
            comms.send_message(
                channel="In-App",
                subject=subject,
                message=message,
                person=person_doc.name,
                category="Community",
                reference_doctype="Cohort Membership",
                reference_name=membership.name,
                triggered_by=inviter_user,
            )
        if person_doc.primary_email:
            comms.send_message(
                channel="Email",
                subject=subject,
                message=message,
                person=person_doc.name,
                to_address=person_doc.primary_email,
                category="Community",
                reference_doctype="Cohort Membership",
                reference_name=membership.name,
                triggered_by=inviter_user,
            )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "cohort invite delivery failed")


def _onboard_and_notify(membership):
    person_doc = frappe.get_doc("Person", membership.person)
    _ensure_participant_user(person_doc)  # provisions only brand-new externals
    person_doc.reload()
    _deliver_invite(membership, person_doc)


def _ancestors_inclusive(cohort):
    """The cohort and every ancestor up its parent chain (cycle-safe)."""
    chain, seen, cur = [cohort], {cohort}, cohort
    while True:
        parent = frappe.db.get_value("Cohort", cur, "parent_cohort")
        if not parent or parent in seen:
            break
        chain.append(parent)
        seen.add(parent)
        cur = parent
    return chain


def _assert_not_archived(cohort):
    """An archived cohort is a record, not a group (ADR 066 section 7.6).

    Archiving used to flip a field nothing read: leaders kept every power over a
    cohort they had declared finished. It now ends the powers and keeps the
    record -- members still see the cohort and its history, because archiving a
    group should not delete anyone's account of having been in it, but nothing
    further is added to it.

    Reactivating is deliberately not blocked; it is the way back.
    """
    if frappe.db.get_value("Cohort", cohort, "status") == "Archived":
        frappe.throw(
            _(
                "{0} is archived. Reactivate it before changing its members or "
                "its shape."
            ).format(frappe.db.get_value("Cohort", cohort, "cohort_name") or cohort)
        )


def _require_leader(cohort, user=None):
    """Ensure the caller may manage `cohort`: staff, or an active leader of the
    cohort or any of its ancestors (subtree oversight). Returns the caller's
    Person (or None for staff without one)."""
    user = user or frappe.session.user
    person = find_person(user=user)
    if _is_staff(user):
        return person
    if person and frappe.db.exists(
        "Cohort Membership",
        {
            "cohort": ["in", _ancestors_inclusive(cohort)],
            "person": person,
            "active": 1,
            "is_leader": 1,
        },
    ):
        return person
    frappe.throw(
        _("Only a cohort leader may manage this cohort."), frappe.PermissionError
    )


def _active_count(cohort):
    return frappe.db.count("Cohort Membership", {"cohort": cohort, "active": 1})


def _warn_if_full(cohort):
    """The ceiling is advice about a healthy group size, not a limit.

    A registrar deliberately seating a thirteenth student in a group of twelve
    knows the group is full; refusing them means the record stops matching the
    room (ADR 066 section 7.4). Automated cuts are sized by the rule
    (`Cohort Type.automation_max_size`), so what reaches here is always someone
    making a decision, and a decision is exactly what a warning is for.
    """
    max_size = frappe.db.get_value("Cohort", cohort, "max_size") or 0
    if max_size and _active_count(cohort) >= max_size:
        frappe.msgprint(
            _("This cohort is at its suggested size of {0}. Adding anyway.").format(
                max_size
            ),
            indicator="orange",
            alert=True,
        )


@frappe.whitelist()
def invite_member(
    cohort,
    person=None,
    email=None,
    first_name=None,
    last_name=None,
    mobile=None,
    role="Member",
):
    """Invite a Person into a cohort. Provide an existing `person`, or a name +
    email (+ optional mobile) to get-or-create one via ensure_person, so the
    Person and User are created properly up front. Starts Invited until login."""
    inviter = _require_leader(cohort)
    _assert_not_archived(cohort)
    if role not in ("Member", "Mentor"):
        frappe.throw(_("Role must be Member or Mentor."))
    _warn_if_full(cohort)

    if not person:
        if not (email and first_name):
            frappe.throw(_("A first name and email are required to invite someone."))
        person = ensure_person(
            email, first_name=first_name, last_name=last_name, mobile=mobile
        )

    existing = frappe.db.exists(
        "Cohort Membership",
        {
            "cohort": cohort,
            "person": person,
            "invite_status": ["in", ["Invited", "Active"]],
        },
    )
    if existing:
        frappe.throw(_("That person already has a pending or active membership here."))

    membership = frappe.get_doc(
        {
            "doctype": "Cohort Membership",
            "cohort": cohort,
            "person": person,
            "role": role,
            "invite_status": "Invited",
            "invited_by": inviter,
        }
    ).insert(ignore_permissions=True)
    _onboard_and_notify(membership)
    return membership.name


@frappe.whitelist()
def accept_invite(membership):
    """Accept a pending invite. Callable by the invited person or by staff."""
    doc = frappe.get_doc("Cohort Membership", membership)
    user = frappe.session.user
    if not _is_staff(user) and find_person(user=user) != doc.person:
        frappe.throw(
            _("You can only accept your own invitation."), frappe.PermissionError
        )
    if doc.invite_status != "Invited":
        frappe.throw(_("This membership is not a pending invite."))
    # No size check here. The seating decision was made by whoever sent the
    # invite; warning the invitee about it tells them nothing they can act on.
    doc.invite_status = "Active"
    doc.joined_on = today()
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def resend_invite(membership):
    """Re-deliver a pending invite (In-App + Email) — for a leader to nudge."""
    doc = frappe.get_doc("Cohort Membership", membership)
    _require_leader(doc.cohort)
    _assert_not_archived(doc.cohort)
    if doc.invite_status != "Invited":
        frappe.throw(_("This membership is not a pending invite."))
    person_doc = frappe.get_doc("Person", doc.person)
    _ensure_participant_user(person_doc)  # in case the account wasn't provisioned
    person_doc.reload()
    _deliver_invite(doc, person_doc)
    return True


@frappe.whitelist()
def my_pending_invites():
    """The caller's pending cohort invitations — drives the in-app accept/decline
    banner (reliable where an after-login hook is not, e.g. first login via a
    password-reset link)."""
    person = find_person(user=frappe.session.user)
    if not person:
        return []
    out = []
    for m in frappe.get_all(
        "Cohort Membership",
        filters={"person": person, "invite_status": "Invited"},
        fields=["name", "cohort", "invited_by"],
    ):
        out.append(
            {
                "membership": m.name,
                "cohort": m.cohort,
                "cohort_name": frappe.db.get_value("Cohort", m.cohort, "cohort_name")
                or m.cohort,
                "invited_by": (
                    frappe.db.get_value("Person", m.invited_by, "full_name")
                    if m.invited_by
                    else None
                ),
            }
        )
    return out


@frappe.whitelist()
def decline_invite(membership):
    """Decline a pending invite (callable by the invited person or staff)."""
    doc = frappe.get_doc("Cohort Membership", membership)
    user = frappe.session.user
    if not _is_staff(user) and find_person(user=user) != doc.person:
        frappe.throw(
            _("You can only decline your own invitation."), frappe.PermissionError
        )
    if doc.invite_status != "Invited":
        frappe.throw(_("This membership is not a pending invite."))
    doc.invite_status = "Removed"
    doc.left_on = today()
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def leave_cohort(membership):
    """A member leaves their own cohort."""
    doc = frappe.get_doc("Cohort Membership", membership)
    if find_person(user=frappe.session.user) != doc.person and not _is_staff(
        frappe.session.user
    ):
        frappe.throw(
            _("You can only leave on your own behalf."), frappe.PermissionError
        )
    doc.invite_status = "Left"
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def remove_member(membership):
    """A leader removes a member from their cohort."""
    doc = frappe.get_doc("Cohort Membership", membership)
    _require_leader(doc.cohort)
    _assert_not_archived(doc.cohort)
    if doc.is_leader:
        frappe.throw(_("Reassign leadership before removing a leader."))
    doc.invite_status = "Removed"
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def split_cohort(cohort, new_cohort_name, member_ids, new_leader=None):
    """Split a cohort: create a child cohort (inheriting lineage + type), move the
    selected active memberships into it, and seat its leader. Requires the Cohort
    Type to allow self-split."""
    _require_leader(cohort)
    _assert_not_archived(cohort)
    parent = frappe.get_doc("Cohort", cohort)
    ct = frappe.get_cached_doc("Cohort Type", parent.cohort_type)
    if not ct.allow_self_split and not _is_staff(frappe.session.user):
        frappe.throw(_("Cohorts of this type may not be split."))

    if not new_leader:
        new_leader = find_person(user=frappe.session.user)
    if not new_leader:
        frappe.throw(_("A new leader (Person) is required to split."))

    member_ids = frappe.parse_json(member_ids) or []

    child = frappe.get_doc(
        {
            "doctype": "Cohort",
            "cohort_name": new_cohort_name,
            "cohort_type": parent.cohort_type,
            "leader": new_leader,
            "parent_cohort": parent.name,
            "visibility": parent.visibility,
            "max_size": parent.max_size,
            "status": "Active",
        }
    ).insert(ignore_permissions=True)

    moved = 0
    for mid in member_ids:
        m = frappe.get_doc("Cohort Membership", mid)
        if m.cohort != parent.name or not m.active:
            continue
        if m.person == parent.leader:
            # the parent keeps its own leader
            continue
        if m.person == new_leader:
            # already seated as the child's leader (Cohort.after_insert); just
            # release them from the parent so they aren't in both.
            m.invite_status = "Left"
            m.save(ignore_permissions=True)
            moved += 1
            continue
        m.cohort = child.name
        m.save(ignore_permissions=True)
        moved += 1

    # Keep the parent's leader connected to their offshoot as a Mentor, so they
    # retain ownership/visibility of what they multiplied. (Management authority
    # over the child already flows from lineage — they lead an ancestor.)
    if (
        parent.leader
        and parent.leader != new_leader
        and not frappe.db.exists(
            "Cohort Membership",
            {"cohort": child.name, "person": parent.leader, "active": 1},
        )
    ):
        frappe.get_doc(
            {
                "doctype": "Cohort Membership",
                "cohort": child.name,
                "person": parent.leader,
                "role": "Mentor",
                "is_leader": 0,
                "invite_status": "Active",
            }
        ).insert(ignore_permissions=True)

    frappe.msgprint(
        _("Created {0} and moved {1} member(s).").format(child.name, moved),
        alert=True,
    )
    return child.name


@frappe.whitelist()
def set_cohort_status(cohort, status):
    """Archive or reactivate a cohort."""
    if status not in ("Active", "Archived"):
        frappe.throw(_("Status must be Active or Archived."))
    _require_leader(cohort)
    frappe.db.set_value("Cohort", cohort, "status", status)
    return status


@frappe.whitelist()
def create_cohort(cohort_name, cohort_type, leader):
    """Staff creates a root cohort (parentless). Leaders grow the tree from there
    via split_cohort."""
    frappe.only_for(list(STAFF_BYPASS))
    doc = frappe.get_doc(
        {
            "doctype": "Cohort",
            "cohort_name": cohort_name,
            "cohort_type": cohort_type,
            "leader": leader,
            "status": "Active",
        }
    ).insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def cohort_members(cohort):
    """The 'My Cohort' roster: each active member with contact + engagement
    signals (last visit, last post) so a leader can see who's disengaged."""
    user = frappe.session.user
    person = find_person(user=user)
    is_member = frappe.db.exists(
        "Cohort Membership", {"cohort": cohort, "person": person, "active": 1}
    )
    if not _is_staff(user) and not is_member:
        frappe.throw(_("You are not a member of this cohort."), frappe.PermissionError)

    members = []
    for m in frappe.get_all(
        "Cohort Membership",
        filters={"cohort": cohort, "invite_status": ["in", ["Active", "Invited"]]},
        fields=["name", "person", "role", "is_leader", "joined_on", "invite_status"],
    ):
        info = (
            frappe.db.get_value(
                "Person",
                m.person,
                ["full_name", "primary_email", "primary_mobile"],
                as_dict=True,
            )
            or {}
        )
        members.append(
            {
                "membership": m.name,
                "person": m.person,
                "name": info.get("full_name") or m.person,
                "email": info.get("primary_email"),
                "mobile": info.get("primary_mobile"),
                "role": m.role,
                "is_leader": m.is_leader,
                "invite_status": m.invite_status,
                "joined_on": m.joined_on,
                "last_visited": frappe.db.get_value(
                    "Cohort Feed Read State",
                    {"person": m.person, "cohort": cohort},
                    "last_seen",
                    order_by="last_seen desc",
                ),
                "last_post_on": frappe.db.get_value(
                    "Cohort Post",
                    {"cohort": cohort, "author": m.person},
                    "creation",
                    order_by="creation desc",
                ),
            }
        )
    # leaders first, then active members, then pending invites; then by name
    members.sort(
        key=lambda x: (
            0 if x["is_leader"] else 1,
            0 if x["invite_status"] == "Active" else 1,
            x["name"] or "",
        )
    )
    can_lead = _is_staff(user) or bool(
        frappe.db.exists(
            "Cohort Membership",
            {"cohort": cohort, "person": person, "active": 1, "is_leader": 1},
        )
    )
    ct = frappe.db.get_value("Cohort", cohort, "cohort_type")
    allow_split = (
        bool(frappe.db.get_value("Cohort Type", ct, "allow_self_split"))
        if ct
        else False
    )
    return {"members": members, "is_leader": can_lead, "allow_split": allow_split}


@frappe.whitelist()
def reassign_leader(cohort, new_leader):
    """Hand cohort leadership to another active member."""
    _require_leader(cohort)
    _assert_not_archived(cohort)
    nm = frappe.db.get_value(
        "Cohort Membership",
        {"cohort": cohort, "person": new_leader, "active": 1},
        "name",
    )
    if not nm:
        frappe.throw(_("The new leader must be an active member."))
    old = frappe.db.get_value("Cohort", cohort, "leader")
    frappe.db.set_value("Cohort", cohort, "leader", new_leader)
    frappe.db.set_value("Cohort Membership", nm, {"is_leader": 1, "role": "Mentor"})
    if old and old != new_leader:
        om = frappe.db.get_value(
            "Cohort Membership", {"cohort": cohort, "person": old, "active": 1}, "name"
        )
        if om:
            frappe.db.set_value("Cohort Membership", om, "is_leader", 0)
    return new_leader


# --------------------------------------------------------------------------- #
# Seeding cohorts from a course's student groups (reverse enrollment direction)
# --------------------------------------------------------------------------- #
def _require_course_staff(course_schedule):
    """Staff, or an instructor of this course schedule, may manage its cohorts."""
    user = frappe.session.user
    if _is_staff(user):
        return
    inst = frappe.db.get_value("Instructor", {"user": user}, "name")
    if inst and frappe.db.exists(
        "Course Schedule Instructors",
        {"parent": course_schedule, "instructor": inst},
    ):
        return
    frappe.throw(
        _("Only staff or an instructor of this course may manage its cohorts."),
        frappe.PermissionError,
    )


def _resolve_instructor_person(group_instructor):
    """A group instructor (stored as a User id by the Configure Student Groups UI)
    resolved to a Person via the identity spine, with Instructor fallbacks."""
    if not group_instructor:
        return None
    person = find_person(user=group_instructor)
    if person:
        return person
    return frappe.db.get_value(
        "Instructor", {"user": group_instructor}, "person"
    ) or frappe.db.get_value("Instructor", group_instructor, "person")


@frappe.whitelist()
def cohort_seed_preview(course_schedule):
    """The 'Community Cohort' section data: each student group of a cohort-forming
    course with its members (resolved to Person), a suggested instructor-leader,
    whether a cohort already exists, and which students already belong to a cohort
    of this type."""
    from seminary.seminary.discipleship.enrollment import (
        course_cohort_binding,
        student_person,
        active_cohort_of_type,
    )
    from seminary.seminary.utils import get_student_groups

    _require_course_staff(course_schedule)
    _course, cohort_type = course_cohort_binding(course_schedule)
    if not cohort_type:
        return {"forms_cohort": False, "cohort_type": None, "groups": []}

    grouped = {}
    for r in get_student_groups(course_schedule):
        g = grouped.setdefault(
            r["student_group"],
            {
                "student_group": r["student_group"],
                "group_name": r.get("group_name"),
                "group_instructor": r.get("group_instructor"),
                "students": [],
            },
        )
        person = student_person(r["student"])
        g["students"].append(
            {
                "student": r["student"],
                "student_name": r.get("student_name"),
                "person": person,
                "already_in_cohort": (
                    active_cohort_of_type(person, cohort_type) if person else None
                ),
            }
        )

    groups = []
    for g in grouped.values():
        inst_person = _resolve_instructor_person(g["group_instructor"])
        groups.append(
            {
                **g,
                "instructor_person": inst_person,
                "instructor_name": (
                    frappe.db.get_value("Person", inst_person, "full_name")
                    if inst_person
                    else g["group_instructor"]
                ),
                "existing_cohort": frappe.db.get_value(
                    "Cohort", {"source_student_group": g["student_group"]}, "name"
                ),
            }
        )
    return {"forms_cohort": True, "cohort_type": cohort_type, "groups": groups}


@frappe.whitelist()
def cohort_placement_status(course_schedule):
    """Reconciliation view: every active enrolled student on the roster with their
    placement status in a cohort of this type (Placed / Invited / Not placed), plus
    the active cohorts of this type available as assignment targets."""
    from seminary.seminary.discipleship.enrollment import (
        course_cohort_binding,
        student_person,
        active_cohort_of_type,
        pending_cohort_of_type,
    )
    from seminary.seminary.utils import get_roster

    _require_course_staff(course_schedule)
    _course, cohort_type = course_cohort_binding(course_schedule)
    if not cohort_type:
        return {"cohort_type": None, "students": [], "cohorts": []}

    students = []
    for r in get_roster(course_schedule):
        if not r.get("active") or r.get("audit_bool"):
            continue
        person = student_person(r["student"])
        placed = active_cohort_of_type(person, cohort_type) if person else None
        invited = (
            None
            if placed
            else (pending_cohort_of_type(person, cohort_type) if person else None)
        )
        students.append(
            {
                "student": r["student"],
                "student_name": r.get("stuname_roster"),
                "email": r.get("stuemail_rc"),
                "person": person,
                "status": (
                    "Placed" if placed else ("Invited" if invited else "Not placed")
                ),
                "cohort": placed or invited,
            }
        )
    students.sort(key=lambda s: (s["status"] == "Placed", s["student_name"] or ""))

    cohorts = frappe.get_all(
        "Cohort",
        filters={"cohort_type": cohort_type, "status": "Active"},
        fields=["name", "cohort_name", "source_course_schedule"],
    )
    return {"cohort_type": cohort_type, "students": students, "cohorts": cohorts}


@frappe.whitelist()
def create_cohorts_from_student_groups(
    course_schedule, include_instructor_as_leader=0, leaders_by_group=None
):
    """Create one self-managing Community Cohort per student group of a
    cohort-forming course, seeded with the group's students as active members and
    a leader (each group's instructor, or a chosen student). Idempotent: groups
    that already have a cohort are skipped, and (when cohorts persist) students
    already in a cohort of this type are not re-placed — so re-running across a
    course sequence is a safe no-op."""
    from seminary.seminary.discipleship.enrollment import (
        course_cohort_binding,
        student_person,
        active_cohort_of_type,
        cohorts_persist,
        live_cei_for_student_course,
    )
    from seminary.seminary.utils import get_student_groups

    _require_course_staff(course_schedule)
    course, cohort_type = course_cohort_binding(course_schedule)
    if not cohort_type:
        frappe.throw(_("This course does not form community cohorts."))

    include_instructor = cint(include_instructor_as_leader)
    leaders = frappe.parse_json(leaders_by_group) if leaders_by_group else {}
    persist = cohorts_persist(cohort_type)

    grouped = {}
    for r in get_student_groups(course_schedule):
        grouped.setdefault(
            r["student_group"],
            {
                "group_name": r.get("group_name"),
                "group_instructor": r.get("group_instructor"),
                "students": [],
            },
        )["students"].append(r["student"])

    created, skipped = [], []
    for sg, g in grouped.items():
        if frappe.db.exists("Cohort", {"source_student_group": sg}):
            skipped.append({"student_group": sg, "reason": "cohort already exists"})
            continue

        if include_instructor:
            leader_person = _resolve_instructor_person(g["group_instructor"])
            leader_student = None
            if not leader_person:
                skipped.append({"student_group": sg, "reason": "no instructor to lead"})
                continue
        else:
            leader_student = leaders.get(sg)
            leader_person = student_person(leader_student) if leader_student else None
            if not leader_person:
                skipped.append({"student_group": sg, "reason": "no leader chosen"})
                continue

        # New members only (dedup across the course sequence when cohorts persist).
        new_members = []
        for st in g["students"]:
            person = student_person(st)
            if not person:
                continue
            if persist and active_cohort_of_type(person, cohort_type):
                continue
            new_members.append((st, person))

        # The leader is seated by Cohort.after_insert; don't double-seat them.
        seatable = [(st, p) for st, p in new_members if p != leader_person]
        leader_is_new = bool(leader_student) and any(
            st == leader_student for st, _ in new_members
        )
        if not seatable and not leader_is_new:
            skipped.append(
                {"student_group": sg, "reason": "all members already placed"}
            )
            continue

        cohort = frappe.get_doc(
            {
                "doctype": "Cohort",
                "cohort_name": g["group_name"] or sg,
                "cohort_type": cohort_type,
                "leader": leader_person,
                "status": "Active",
                "source_course_schedule": course_schedule,
                "source_student_group": sg,
            }
        ).insert(ignore_permissions=True)

        seeded = 0
        for st, person in seatable:
            max_size = frappe.db.get_value("Cohort", cohort.name, "max_size") or 0
            if max_size and _active_count(cohort.name) >= max_size:
                break
            frappe.get_doc(
                {
                    "doctype": "Cohort Membership",
                    "cohort": cohort.name,
                    "person": person,
                    "role": "Member",
                    "invite_status": "Active",
                    "joined_on": today(),
                    "course_enrollment": live_cei_for_student_course(st, course),
                }
            ).insert(ignore_permissions=True)
            seeded += 1

        created.append(
            {
                "cohort": cohort.name,
                "cohort_name": cohort.cohort_name,
                "student_group": sg,
                "leader": leader_person,
                "seeded": seeded,
            }
        )

    return {"created": created, "skipped": skipped}


@frappe.whitelist()
def place_student_in_cohort(course_schedule, student, cohort):
    """Reconciliation action: place a straggler enrolled student into an existing
    cohort of this course's type, as a pending invite they accept."""
    from seminary.seminary.discipleship.enrollment import (
        course_cohort_binding,
        student_person,
        active_cohort_of_type,
    )

    _require_course_staff(course_schedule)
    _course, cohort_type = course_cohort_binding(course_schedule)
    if not cohort_type:
        frappe.throw(_("This course does not form community cohorts."))
    if frappe.db.get_value("Cohort", cohort, "cohort_type") != cohort_type:
        frappe.throw(_("That cohort is not of this course's cohort type."))
    _assert_not_archived(cohort)
    person = student_person(student)
    if not person:
        frappe.throw(_("This student has no linked person record."))
    if active_cohort_of_type(person, cohort_type):
        frappe.throw(_("This student is already in a cohort of this type."))
    if frappe.db.exists(
        "Cohort Membership",
        {
            "cohort": cohort,
            "person": person,
            "invite_status": ["in", ["Invited", "Active"]],
        },
    ):
        frappe.throw(_("This student already has a pending or active membership here."))
    _warn_if_full(cohort)
    membership = frappe.get_doc(
        {
            "doctype": "Cohort Membership",
            "cohort": cohort,
            "person": person,
            "role": "Member",
            "invite_status": "Invited",
            "invited_by": find_person(user=frappe.session.user),
        }
    ).insert(ignore_permissions=True)
    _onboard_and_notify(membership)
    return membership.name


# --------------------------------------------------------------------------- #
# Leader-to-leader communication (Inbox broadcast, ADR 043 comms)
# --------------------------------------------------------------------------- #
def _leader_recipients(user):
    """Staff reach every cohort leader; a leader reaches the leaders of the
    cohorts in their own subtree (their descendant leaders)."""
    from seminary.seminary.discipleship.permissions import led_cohorts

    if _is_staff(user):
        return set(
            frappe.get_all(
                "Cohort Membership",
                filters={"active": 1, "is_leader": 1},
                pluck="person",
            )
        )
    cohorts = led_cohorts(user)
    if not cohorts:
        return set()
    return set(
        frappe.get_all(
            "Cohort Membership",
            filters={"cohort": ["in", list(cohorts)], "active": 1, "is_leader": 1},
            pluck="person",
        )
    )


@frappe.whitelist()
def can_broadcast():
    from seminary.seminary.discipleship.permissions import led_cohorts

    user = frappe.session.user
    return _is_staff(user) or bool(led_cohorts(user))


@frappe.whitelist()
def broadcast_to_leaders(subject, message, email=0):
    """Send an In-App (+ optional Email) message to the leaders the sender may
    reach. Fans out through the comms ledger (ADR 043) — lands in each leader's
    portal Inbox."""
    from seminary.seminary import comms
    from seminary.seminary.api import sanitize_html
    from seminary.seminary.discipleship.permissions import led_cohorts

    user = frappe.session.user
    if not (_is_staff(user) or led_cohorts(user)):
        frappe.throw(
            _("Only leaders or staff can message leaders."), frappe.PermissionError
        )
    subject = (subject or "").strip()
    body = sanitize_html(message or "")
    if not subject or not body:
        frappe.throw(_("A subject and message are required."))

    sender = find_person(user=user)
    recipients = _leader_recipients(user)
    recipients.discard(sender)
    sent = 0
    for person in recipients:
        try:
            comms.send_message(
                channel="In-App",
                subject=subject,
                message=body,
                person=person,
                category="Community",
                triggered_by=user,
            )
            if int(email or 0):
                addr = frappe.db.get_value("Person", person, "primary_email")
                if addr:
                    comms.send_message(
                        channel="Email",
                        subject=subject,
                        message=body,
                        person=person,
                        to_address=addr,
                        category="Community",
                        triggered_by=user,
                    )
            sent += 1
        except Exception:
            frappe.log_error(frappe.get_traceback(), "leader broadcast failed")
    return {"sent": sent}
