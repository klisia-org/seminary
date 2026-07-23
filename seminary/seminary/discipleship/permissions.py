"""Record-level scoping for the Discipleship / Community subsystem (ADR 064).

Portal users (students, alumni, invited pastors) see only the cohorts they
belong to; a cohort leader additionally sees the split-off subtree beneath any
cohort they lead. Staff bypass entirely. A user with no resolvable Person or no
memberships sees nothing (`1=0`).

Phase 1 scopes the cohort spine (Cohort, Cohort Membership). The post-family
scoping (Cohort Post / Comment / Reaction, which is additionally *visibility*-
aware) arrives with those doctypes in Phase 2.
"""

import frappe

from seminary.seminary.person import find_person

STAFF_BYPASS = {"System Manager", "Seminary Manager", "Registrar", "Program Chair"}


def _should_restrict(user):
    if not user or user == "Administrator":
        return False
    return not (set(frappe.get_roles(user)) & STAFF_BYPASS)


def _descendants(roots):
    """All cohorts at or below `roots`, walking parent_cohort downward."""
    seen = set(roots)
    frontier = list(roots)
    while frontier:
        children = frappe.get_all(
            "Cohort", filters={"parent_cohort": ["in", frontier]}, pluck="name"
        )
        fresh = [c for c in children if c not in seen]
        seen.update(fresh)
        frontier = fresh
    return seen


def visible_cohorts(user=None):
    """The set of Cohort names a (restricted) user may see: cohorts they are an
    active member of, plus the subtree beneath any cohort they actively lead."""
    if not user:
        user = frappe.session.user
    person = find_person(user=user)
    if not person:
        return set()
    memberships = frappe.get_all(
        "Cohort Membership",
        filters={"person": person, "active": 1},
        fields=["cohort", "is_leader"],
    )
    cohorts = {m.cohort for m in memberships}
    led = [m.cohort for m in memberships if m.is_leader]
    if led:
        cohorts |= _descendants(led)
    return cohorts


def led_cohorts(user=None):
    """Cohorts the user actively leads, plus their split-off subtree — the scope
    a leader may moderate."""
    if not user:
        user = frappe.session.user
    person = find_person(user=user)
    if not person:
        return set()
    led = frappe.get_all(
        "Cohort Membership",
        filters={"person": person, "active": 1, "is_leader": 1},
        pluck="cohort",
    )
    return _descendants(led) if led else set()


def _in_clause(table, field, names):
    joined = ", ".join(frappe.db.escape(n) for n in names)
    return f"(`tab{table}`.`{field}` in ({joined}))"


# --- Cohort (scoped by its own name) ---
def cohort_query(user=None):
    if not _should_restrict(user):
        return ""
    names = visible_cohorts(user)
    if not names:
        return "1=0"
    return _in_clause("Cohort", "name", names)


def cohort_has(doc, ptype=None, user=None):
    if not _should_restrict(user):
        return True
    return doc.name in visible_cohorts(user)


# --- Cohort Membership (scoped by its cohort, plus the user's own rows) ---
def membership_query(user=None):
    if not _should_restrict(user):
        return ""
    if not user:
        user = frappe.session.user
    person = find_person(user=user)
    clauses = []
    names = visible_cohorts(user)
    if names:
        clauses.append(_in_clause("Cohort Membership", "cohort", names))
    if person:
        clauses.append(
            f"(`tabCohort Membership`.`person` = {frappe.db.escape(person)})"
        )
    if not clauses:
        return "1=0"
    return "(" + " OR ".join(clauses) + ")"


def membership_has(doc, ptype=None, user=None):
    if not _should_restrict(user):
        return True
    if not user:
        user = frappe.session.user
    person = find_person(user=user)
    if person and doc.person == person:
        return True
    return doc.cohort in visible_cohorts(user)


# ---------------------------------------------------------------------------
# Post family (Cohort Post / Comment / Reaction) — visibility-aware scoping.
#
# Every post carries a cohort, but a blanket "cohort IN my_cohorts" would leak
# private/direct posts to the whole cohort. Comments and reactions cache the
# post's cohort/visibility/author/recipient (fetch_from) so the same clause
# applies to all three; `author_field` names the *post author* column on each
# (`author` on the post itself, `post_author` on the children).
# ---------------------------------------------------------------------------


def _visibility_clause(user, table, author_field, status_field=None, own_field=None):
    if not _should_restrict(user):
        return ""
    person = find_person(user=user)
    me = frappe.db.escape(person) if person else None
    t = f"`tab{table}`"
    parts = [f"{t}.`visibility` = 'portal_users'"]
    cohorts = visible_cohorts(user)
    if cohorts:
        joined = ", ".join(frappe.db.escape(c) for c in cohorts)
        parts.append(
            f"({t}.`visibility` = 'cohort_only' AND {t}.`cohort` in ({joined}))"
        )
    if me:
        parts.append(f"({t}.`visibility` = 'private' AND {t}.`{author_field}` = {me})")
        parts.append(
            f"({t}.`visibility` = 'direct' AND ({t}.`{author_field}` = {me} "
            f"OR {t}.`direct_recipient` = {me}))"
        )
    clause = "(" + " OR ".join(parts) + ")"
    # Drafts / blocked content are visible only to their own author.
    if status_field and own_field:
        allowed = "'published', 'pinned'" if status_field == "status" else "'published'"
        owner = f"{t}.`{own_field}` = {me}" if me else "0"
        clause = f"({clause} AND ({t}.`{status_field}` in ({allowed}) OR {owner}))"
    return clause


def _visibility_has(doc, user, author_field, status_field=None, own_field=None):
    if not _should_restrict(user):
        return True
    person = find_person(user=user)
    vis = doc.get("visibility")
    if status_field:
        published = {"published", "pinned"}
        if doc.get(status_field) not in published and not (
            person and doc.get(own_field) == person
        ):
            return False
    if vis == "portal_users":
        return True
    if vis == "cohort_only":
        return doc.get("cohort") in visible_cohorts(user)
    if vis == "private":
        return bool(person) and doc.get(author_field) == person
    if vis == "direct":
        return bool(person) and person in (
            doc.get(author_field),
            doc.get("direct_recipient"),
        )
    return False


def post_query(user=None):
    return _visibility_clause(
        user or frappe.session.user, "Cohort Post", "author", "status", "author"
    )


def post_has(doc, ptype=None, user=None):
    return _visibility_has(
        doc, user or frappe.session.user, "author", "status", "author"
    )


def comment_query(user=None):
    user = user or frappe.session.user
    base = _visibility_clause(
        user, "Cohort Post Comment", "post_author", "status", "author"
    )
    if not base:  # staff bypass
        return ""
    # private replies: only the writer, the post author, and cohort leaders.
    person = find_person(user=user)
    me = frappe.db.escape(person) if person else "''"
    t = "`tabCohort Post Comment`"
    parts = [
        f"{t}.`is_private` = 0",
        f"{t}.`author` = {me}",
        f"{t}.`post_author` = {me}",
    ]
    led = led_cohorts(user)
    if led:
        joined = ", ".join(frappe.db.escape(c) for c in led)
        parts.append(f"{t}.`cohort` in ({joined})")
    return f"({base} AND (" + " OR ".join(parts) + "))"


def comment_has(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not _visibility_has(doc, user, "post_author", "status", "author"):
        return False
    if int(getattr(doc, "is_private", 0) or 0) and _should_restrict(user):
        person = find_person(user=user)
        if person and person in (doc.get("author"), doc.get("post_author")):
            return True
        return doc.get("cohort") in led_cohorts(user)
    return True


def reaction_query(user=None):
    return _visibility_clause(
        user or frappe.session.user, "Cohort Post Reaction", "post_author"
    )


def reaction_has(doc, ptype=None, user=None):
    return _visibility_has(doc, user or frappe.session.user, "post_author")


# ---------------------------------------------------------------------------
# Cohort Content Flag — moderators (leaders of the target's cohort) + the
# reporter see a flag; everyone else is blind to the moderation queue.
# ---------------------------------------------------------------------------
def flag_query(user=None):
    if not _should_restrict(user):
        return ""
    if not user:
        user = frappe.session.user
    person = find_person(user=user)
    clauses = []
    led = led_cohorts(user)
    if led:
        clauses.append(_in_clause("Cohort Content Flag", "cohort", led))
    if person:
        clauses.append(
            f"(`tabCohort Content Flag`.`reporter` = {frappe.db.escape(person)})"
        )
    if not clauses:
        return "1=0"
    return "(" + " OR ".join(clauses) + ")"


def flag_has(doc, ptype=None, user=None):
    if not _should_restrict(user):
        return True
    if not user:
        user = frappe.session.user
    person = find_person(user=user)
    if person and doc.reporter == person:
        return True
    return doc.cohort in led_cohorts(user)
