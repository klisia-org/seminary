"""Whitelisted feed endpoints for the Community frontend (Phase 2).

Reads go through frappe.get_list so the visibility scoping in permissions.py
applies automatically; writes check membership/visibility then insert with
ignore_permissions, the same posture as the partner portal API.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, now

from seminary.seminary.person import find_person
from seminary.seminary.discipleship.permissions import STAFF_BYPASS, post_has

_ANCHOR_FIELDS = {
    "Timestamp": ("timestamp_s",),
    "VerseRange": ("verse_start_ord", "verse_end_ord"),
    "TextRange": ("range_from", "range_to"),
    "Region": ("page", "x_pct", "y_pct"),
}


def _is_staff(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or bool(set(frappe.get_roles(user)) & STAFF_BYPASS)


def _my_person():
    person = find_person(user=frappe.session.user)
    if not person:
        frappe.throw(_("You need a linked Person record to use the community."))
    return person


def _is_member(cohort, person):
    return bool(
        frappe.db.exists(
            "Cohort Membership", {"cohort": cohort, "person": person, "active": 1}
        )
    )


# --------------------------------------------------------------------------- #
# Posts
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def create_post(
    cohort,
    channel,
    content=None,
    title=None,
    visibility=None,
    direct_recipient=None,
    reference_doctype=None,
    reference_name=None,
    status="published",
    topics=None,
    scripture=None,
    video_url=None,
):
    person = _my_person()
    if not _is_member(cohort, person) and not _is_staff():
        frappe.throw(_("Only cohort members can post here."), frappe.PermissionError)
    if not visibility:
        visibility = (
            frappe.db.get_value("Cohort", cohort, "visibility") or "cohort_only"
        )
    doc = frappe.get_doc(
        {
            "doctype": "Cohort Post",
            "cohort": cohort,
            "channel": channel,
            "author": person,
            "title": title,
            "content": content,
            "visibility": visibility,
            "direct_recipient": direct_recipient,
            "status": status,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "video_url": video_url,
        }
    )
    _apply_tags(doc, topics, scripture)
    doc.insert(ignore_permissions=True)
    return doc.name


def _as_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return frappe.parse_json(value)
    return value


def _ensure_topic(name):
    name = (name or "").strip()
    if not name:
        return None
    if frappe.db.exists("Cohort Post Topic", name):
        return name
    return (
        frappe.get_doc({"doctype": "Cohort Post Topic", "topic_name": name})
        .insert(ignore_permissions=True)
        .name
    )


def _apply_tags(doc, topics, scripture):
    """Attach topic + scripture children. Topics are get-or-created; each
    scripture string is expanded into one row per canonical segment."""
    from seminary.seminary.integrations.bible import parse_reference_segments

    for name in _as_list(topics):
        topic = _ensure_topic(name)
        if topic:
            doc.append("topics", {"topic": topic})
    for ref in _as_list(scripture):
        for seg in parse_reference_segments(ref):
            doc.append("scripture_refs", seg)


@frappe.whitelist()
def list_feed(
    cohort=None,
    channel=None,
    start=0,
    limit=20,
    answered=None,
    visibility=None,
    saved_only=None,
):
    filters = {"status": ["in", ["published", "pinned"]]}
    if cohort:
        filters["cohort"] = cohort
    if channel:
        filters["channel"] = channel
    if visibility:
        filters["visibility"] = visibility
    if int(saved_only or 0):
        person = find_person(user=frappe.session.user)
        saved = (
            frappe.get_all("Cohort Post Save", filters={"person": person}, pluck="post")
            if person
            else []
        )
        filters["name"] = ["in", saved or [""]]
    if answered is not None and answered != "":
        # prayer channels split into an active list (0) and answered prayers (1)
        filters["prayer_answered"] = int(answered)
    posts = frappe.get_list(
        "Cohort Post",
        filters=filters,
        fields=_FEED_FIELDS,
        order_by="creation desc",
        start=int(start),
        page_length=int(limit),
    )
    # pinned to the top of the page (secondary to recency)
    posts.sort(key=lambda p: 0 if p.status == "pinned" else 1)
    _decorate_posts(posts)
    return posts


@frappe.whitelist()
def get_thread(post):
    doc = frappe.get_doc("Cohort Post", post)
    if not post_has(doc, user=frappe.session.user):
        frappe.throw(_("You cannot view this post."), frappe.PermissionError)
    head = doc.as_dict()
    _decorate_posts([head])
    _attach_links([head])
    comments = frappe.get_all(
        "Cohort Post Comment",
        filters={"post": post, "status": "published"},
        fields=[
            "name",
            "parent_comment",
            "author",
            "content",
            "anchor_type",
            "timestamp_s",
            "verse_start_ord",
            "verse_end_ord",
            "anchor_ref",
            "range_from",
            "range_to",
            "page",
            "x_pct",
            "y_pct",
            "creation",
        ],
        order_by="creation asc",
    )
    _attach_names(comments, "author")
    _attach_reactions(comments, target="comment")
    # foreground intra-cohort voices: tag each reply and rank members first
    # (secondary to recency), so extra-cohort replies on portal-wide posts sink.
    members = set(
        frappe.get_all(
            "Cohort Membership",
            filters={"cohort": doc.cohort, "active": 1},
            pluck="person",
        )
    )
    for c in comments:
        c["author_membership"] = (
            "cohort_member" if c["author"] in members else "outside"
        )
    comments.sort(key=lambda c: 0 if c["author_membership"] == "cohort_member" else 1)
    viewer = find_person(user=frappe.session.user)
    if viewer:
        _mark_thread_seen(viewer, post)
    return {"post": head, "comments": comments}


def _mark_thread_seen(person, post):
    name = frappe.db.exists(
        "Cohort Thread Read State", {"person": person, "post": post}
    )
    if name:
        frappe.db.set_value("Cohort Thread Read State", name, "last_seen", now())
    else:
        frappe.get_doc(
            {
                "doctype": "Cohort Thread Read State",
                "person": person,
                "post": post,
                "last_seen": now(),
            }
        ).insert(ignore_permissions=True)


# --------------------------------------------------------------------------- #
# Comments
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def add_comment(
    post, content, parent_comment=None, anchor_type="General", anchor_data=None
):
    person = _my_person()
    post_doc = frappe.get_doc("Cohort Post", post)
    if not post_has(post_doc, user=frappe.session.user):
        frappe.throw(_("You cannot reply to this post."), frappe.PermissionError)
    # portal-wide posts invite extra-cohort engagement; cohort/private/direct
    # posts stay members-only (plus the author/recipient of a direct post).
    party = person in (post_doc.author, post_doc.direct_recipient)
    portal_wide = post_doc.visibility == "portal_users"
    if not (portal_wide or party or _is_member(post_doc.cohort, person) or _is_staff()):
        frappe.throw(_("Only cohort members can reply here."), frappe.PermissionError)
    values = {
        "doctype": "Cohort Post Comment",
        "post": post,
        "parent_comment": parent_comment,
        "author": person,
        "content": content,
        "anchor_type": anchor_type or "General",
    }
    anchor = frappe.parse_json(anchor_data) if anchor_data else {}
    if (
        anchor_type == "VerseRange"
        and anchor.get("ref")
        and not anchor.get("verse_start_ord")
    ):
        # resolve a human passage ("Jn 3:16-18") into canonical ordinals server-side
        from seminary.seminary.integrations.bible import parse_reference_segments

        seg = parse_reference_segments(anchor["ref"])[0]
        values["verse_start_ord"] = seg["verse_start_ord"]
        values["verse_end_ord"] = seg["verse_end_ord"]
        values["anchor_ref"] = seg["display"]
    else:
        for f in _ANCHOR_FIELDS.get(anchor_type, ()):
            if anchor.get(f) is not None:
                values[f] = anchor[f]
        if anchor.get("anchor_ref"):
            values["anchor_ref"] = anchor["anchor_ref"]
    doc = frappe.get_doc(values).insert(ignore_permissions=True)
    return doc.name


# --------------------------------------------------------------------------- #
# Reactions
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def toggle_save(post):
    """Bookmark / un-bookmark a post for the current person."""
    person = _my_person()
    existing = frappe.db.exists("Cohort Post Save", {"person": person, "post": post})
    if existing:
        frappe.delete_doc("Cohort Post Save", existing, ignore_permissions=True)
        return {"saved": False}
    frappe.get_doc(
        {"doctype": "Cohort Post Save", "person": person, "post": post}
    ).insert(ignore_permissions=True)
    return {"saved": True}


@frappe.whitelist()
def toggle_reaction(reaction_type, post=None, comment=None):
    person = _my_person()
    if comment and not post:
        post = frappe.db.get_value("Cohort Post Comment", comment, "post")
    if not post:
        frappe.throw(_("Nothing to react to."))
    post_doc = frappe.get_doc("Cohort Post", post)
    if not post_has(post_doc, user=frappe.session.user):
        frappe.throw(_("You cannot react here."), frappe.PermissionError)
    target = comment or None
    rows = frappe.get_all(
        "Cohort Post Reaction",
        filters={"post": post, "person": person, "reaction_type": reaction_type},
        fields=["name", "comment"],
    )
    existing = next((r.name for r in rows if (r.comment or None) == target), None)
    if existing:
        frappe.delete_doc("Cohort Post Reaction", existing, ignore_permissions=True)
        return {"reacted": False}
    frappe.get_doc(
        {
            "doctype": "Cohort Post Reaction",
            "post": post,
            "comment": comment,
            "person": person,
            "reaction_type": reaction_type,
        }
    ).insert(ignore_permissions=True)
    return {"reacted": True}


# --------------------------------------------------------------------------- #
# Read-state / unread
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def mark_seen(cohort, channel=None):
    """Mark a channel (or every channel in the cohort, when channel is omitted)
    as read up to now — advances the 'new posts' baseline."""
    person = _my_person()
    if channel:
        channels = [channel]
    else:
        channels = frappe.get_all(
            "Cohort Post",
            filters={"cohort": cohort, "status": ["in", ["published", "pinned"]]},
            distinct=True,
            pluck="channel",
        )
    for ch in channels:
        _upsert_seen(person, cohort, ch)
    return True


def _upsert_seen(person, cohort, channel):
    name = frappe.db.exists(
        "Cohort Feed Read State",
        {"person": person, "cohort": cohort, "channel": channel},
    )
    if name:
        frappe.db.set_value("Cohort Feed Read State", name, "last_seen", now())
    else:
        frappe.get_doc(
            {
                "doctype": "Cohort Feed Read State",
                "person": person,
                "cohort": cohort,
                "channel": channel,
                "last_seen": now(),
            }
        ).insert(ignore_permissions=True)


@frappe.whitelist()
def unread_counts(cohort):
    """Per-channel unread post count for the caller in one cohort."""
    person = _my_person()
    channels = frappe.get_all(
        "Cohort Post",
        filters={"cohort": cohort, "status": ["in", ["published", "pinned"]]},
        distinct=True,
        pluck="channel",
    )
    seen = {
        r.channel: r.last_seen
        for r in frappe.get_all(
            "Cohort Feed Read State",
            filters={"person": person, "cohort": cohort},
            fields=["channel", "last_seen"],
        )
    }
    out = {}
    for ch in channels:
        filters = {
            "cohort": cohort,
            "channel": ch,
            "status": ["in", ["published", "pinned"]],
            "author": ["!=", person],
        }
        if seen.get(ch):
            filters["creation"] = [">", seen[ch]]
        out[ch] = len(frappe.get_list("Cohort Post", filters=filters, pluck="name"))
    return out


# --------------------------------------------------------------------------- #
# Prayer & journal
# --------------------------------------------------------------------------- #
def _require_author_or_staff(post):
    author = frappe.db.get_value("Cohort Post", post, "author")
    if _is_staff() or find_person(user=frappe.session.user) == author:
        return
    frappe.throw(_("Only the author can do this."), frappe.PermissionError)


@frappe.whitelist()
def mark_prayer_answered(post, note=None):
    """Move a prayer request into Answered prayers, with an optional testimony."""
    _require_author_or_staff(post)
    doc = frappe.get_doc("Cohort Post", post)
    doc.prayer_answered = 1
    if note:
        doc.prayer_answer_note = note
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def reopen_prayer(post):
    """Return an answered prayer to the active list."""
    _require_author_or_staff(post)
    doc = frappe.get_doc("Cohort Post", post)
    doc.prayer_answered = 0
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def link_post(post, linked_post, relation_type="reflection"):
    """Connect another post (e.g. a private journal/reflection) to this one, so
    it can resurface when a prayer is answered."""
    _require_author_or_staff(post)
    if linked_post == post:
        frappe.throw(_("A post cannot link to itself."))
    if relation_type not in ("related", "journal", "reflection"):
        relation_type = "related"
    doc = frappe.get_doc("Cohort Post", post)
    if any(r.linked_post == linked_post for r in doc.links):
        return post
    doc.append("links", {"linked_post": linked_post, "relation_type": relation_type})
    doc.save(ignore_permissions=True)
    return post


@frappe.whitelist()
def unlink_post(post, linked_post):
    _require_author_or_staff(post)
    doc = frappe.get_doc("Cohort Post", post)
    doc.links = [r for r in doc.links if r.linked_post != linked_post]
    doc.save(ignore_permissions=True)
    return post


def _attach_links(posts):
    """Attach the visible posts each post links to (journal / reflection ties),
    scoped through get_list so a private journal only surfaces for its author."""
    for p in posts:
        rows = frappe.get_all(
            "Cohort Post Link",
            filters={"parent": p["name"]},
            fields=["linked_post", "relation_type"],
        )
        if not rows:
            p["linked_posts"] = []
            continue
        rel = {r.linked_post: r.relation_type for r in rows}
        visible = frappe.get_list(
            "Cohort Post",
            filters={"name": ["in", list(rel)]},
            fields=["name", "title", "channel_kind", "content", "prayer_answered"],
        )
        p["linked_posts"] = [
            {
                "name": v.name,
                "title": v.title,
                "channel_kind": v.channel_kind,
                "relation_type": rel.get(v.name),
            }
            for v in visible
        ]


# --------------------------------------------------------------------------- #
# Author edit / delete
# --------------------------------------------------------------------------- #
def _require_comment_author_or_staff(comment):
    author = frappe.db.get_value("Cohort Post Comment", comment, "author")
    if _is_staff() or find_person(user=frappe.session.user) == author:
        return
    frappe.throw(_("Only the author can do this."), frappe.PermissionError)


@frappe.whitelist()
def edit_post(
    post,
    title=None,
    content=None,
    visibility=None,
    direct_recipient=None,
    topics=None,
    scripture=None,
):
    _require_author_or_staff(post)
    doc = frappe.get_doc("Cohort Post", post)
    if title is not None:
        doc.title = title
    if content is not None:
        doc.content = content  # controller re-sanitizes
    if visibility:
        doc.visibility = visibility
        doc.direct_recipient = direct_recipient if visibility == "direct" else None
    if topics is not None:
        doc.topics = []
        for name in _as_list(topics):
            topic = _ensure_topic(name)
            if topic:
                doc.append("topics", {"topic": topic})
    if scripture is not None:
        from seminary.seminary.integrations.bible import parse_reference_segments

        doc.scripture_refs = []
        for ref in _as_list(scripture):
            for seg in parse_reference_segments(ref):
                doc.append("scripture_refs", seg)
    doc.save(ignore_permissions=True)  # on_update propagates scope to children
    return doc.name


@frappe.whitelist()
def delete_post(post):
    _require_author_or_staff(post)
    comment_names = frappe.get_all(
        "Cohort Post Comment", filters={"post": post}, pluck="name"
    )
    for cn in comment_names:
        frappe.db.delete(
            "Cohort Content Flag",
            {"target_doctype": "Cohort Post Comment", "target_name": cn},
        )
    frappe.db.delete(
        "Cohort Content Flag", {"target_doctype": "Cohort Post", "target_name": post}
    )
    frappe.db.delete("Cohort Post Reaction", {"post": post})
    frappe.db.delete("Cohort Post Comment", {"post": post})
    frappe.db.delete("Cohort Thread Read State", {"post": post})
    frappe.db.delete("Cohort Post Link", {"linked_post": post})
    frappe.delete_doc("Cohort Post", post, ignore_permissions=True, force=True)
    return True


@frappe.whitelist()
def edit_comment(comment, content):
    _require_comment_author_or_staff(comment)
    doc = frappe.get_doc("Cohort Post Comment", comment)
    doc.content = content
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def delete_comment(comment):
    _require_comment_author_or_staff(comment)
    _delete_comment_subtree(comment)
    return True


def _delete_comment_subtree(comment):
    for child in frappe.get_all(
        "Cohort Post Comment", filters={"parent_comment": comment}, pluck="name"
    ):
        _delete_comment_subtree(child)
    frappe.db.delete("Cohort Post Reaction", {"comment": comment})
    frappe.db.delete(
        "Cohort Content Flag",
        {"target_doctype": "Cohort Post Comment", "target_name": comment},
    )
    frappe.delete_doc(
        "Cohort Post Comment", comment, ignore_permissions=True, force=True
    )


# --------------------------------------------------------------------------- #
# Catalog / lookups for the UI
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def my_cohorts_list():
    """Active cohorts the caller belongs to, for the community cohort switcher."""
    person = _my_person()
    out = []
    for r in frappe.get_all(
        "Cohort Membership",
        filters={"person": person, "active": 1},
        fields=["cohort", "is_leader", "role"],
    ):
        c = frappe.db.get_value(
            "Cohort", r.cohort, ["cohort_name", "status", "visibility"], as_dict=True
        )
        if c and c.status == "Active":
            out.append(
                {
                    "name": r.cohort,
                    "cohort_name": c.cohort_name,
                    "is_leader": r.is_leader,
                    "role": r.role,
                    "visibility": c.visibility,
                }
            )
    return out


@frappe.whitelist()
def list_channels():
    return frappe.get_all(
        "Cohort Channel",
        filters={"enabled": 1},
        fields=["name", "channel_name", "channel_kind", "icon"],
        order_by="sort_order asc, channel_name asc",
    )


@frappe.whitelist()
def list_reaction_types():
    return frappe.get_all(
        "Cohort Reaction Type",
        filters={"enabled": 1},
        fields=["name", "label", "glyph"],
        order_by="sort_order asc",
    )


# --------------------------------------------------------------------------- #
# Cross-channel discovery (scripture overlap + related)
# --------------------------------------------------------------------------- #
_FEED_FIELDS = [
    "name",
    "title",
    "content",
    "channel",
    "channel_kind",
    "cohort",
    "author",
    "visibility",
    "direct_recipient",
    "status",
    "creation",
    "prayer_answered",
    "prayer_answered_on",
    "prayer_answer_note",
    "video_url",
]


def _overlap_parents(start_ord, end_ord, exclude_post=None):
    filters = {
        "verse_start_ord": ["<=", end_ord],
        "verse_end_ord": [">=", start_ord],
    }
    if exclude_post:
        filters["parent"] = ["!=", exclude_post]
    return frappe.get_all("Cohort Post Scripture Ref", filters=filters, pluck="parent")


def _scoped_posts(names, limit=30):
    """Fetch published posts by name through get_list, so the visibility
    permission clause filters out anything the caller may not see."""
    names = [n for n in set(names) if n]
    if not names:
        return []
    posts = frappe.get_list(
        "Cohort Post",
        filters={"name": ["in", names], "status": ["in", ["published", "pinned"]]},
        fields=_FEED_FIELDS,
        order_by="creation desc",
        page_length=int(limit),
    )
    _decorate_posts(posts)
    return posts


@frappe.whitelist()
def posts_for_passage(ref, limit=30):
    """Every visible post whose scripture range overlaps the given passage —
    the cross-channel payoff (a sermon, a challenge, a prayer on this text)."""
    from seminary.seminary.integrations.bible import parse_reference_segments

    names = set()
    for seg in parse_reference_segments(ref):
        names.update(_overlap_parents(seg["verse_start_ord"], seg["verse_end_ord"]))
    return _scoped_posts(names, limit)


@frappe.whitelist()
def related_posts(post, limit=8):
    """Posts connected to this one — sharing a topic or overlapping Scripture."""
    names = set()
    topics = frappe.get_all(
        "Cohort Post Topic Link", filters={"parent": post}, pluck="topic"
    )
    if topics:
        names.update(
            frappe.get_all(
                "Cohort Post Topic Link",
                filters={"topic": ["in", topics], "parent": ["!=", post]},
                pluck="parent",
            )
        )
    for seg in frappe.get_all(
        "Cohort Post Scripture Ref",
        filters={"parent": post},
        fields=["verse_start_ord", "verse_end_ord"],
    ):
        names.update(
            _overlap_parents(seg.verse_start_ord, seg.verse_end_ord, exclude_post=post)
        )
    names.discard(post)
    return _scoped_posts(names, limit)


# --------------------------------------------------------------------------- #
# Decoration helpers
# --------------------------------------------------------------------------- #
def _attach_names(rows, field):
    people = {r.get(field) for r in rows if r.get(field)}
    names = (
        {
            p.name: p.full_name
            for p in frappe.get_all(
                "Person",
                filters={"name": ["in", list(people)]},
                fields=["name", "full_name"],
            )
        }
        if people
        else {}
    )
    for r in rows:
        r["author_name"] = names.get(r.get(field))


def _attach_reactions(rows, target):
    """Attach a reaction summary [{reaction_type, glyph, count, mine}] to rows,
    where `target` is 'post' or 'comment' (the id field on each row is 'name')."""
    if not rows:
        return
    person = find_person(user=frappe.session.user)
    ids = [r["name"] for r in rows]
    field = "post" if target == "post" else "comment"
    reactions = frappe.get_all(
        "Cohort Post Reaction",
        filters={field: ["in", ids]},
        fields=[field, "reaction_type", "person", "comment"],
    )
    glyphs = {
        r.name: r.glyph
        for r in frappe.get_all("Cohort Reaction Type", fields=["name", "glyph"])
    }
    summary = {}
    for r in reactions:
        # post-level rows have no comment; skip comment-level rows when
        # summarizing a post, and vice-versa.
        if target == "post" and r.comment:
            continue
        bucket = summary.setdefault(
            (r.get(field), r.reaction_type), {"count": 0, "mine": False}
        )
        bucket["count"] += 1
        if person and r.person == person:
            bucket["mine"] = True
    for row in rows:
        row["reactions"] = [
            {
                "reaction_type": rt,
                "glyph": glyphs.get(rt),
                "count": v["count"],
                "mine": v["mine"],
            }
            for (tid, rt), v in summary.items()
            if tid == row["name"]
        ]


def _decorate_posts(posts):
    if not posts:
        return
    _attach_names(posts, "author")
    _attach_reactions(posts, target="post")
    me = find_person(user=frappe.session.user)
    ids = [p["name"] for p in posts]
    topic_map, scr_map = {}, {}
    for r in frappe.get_all(
        "Cohort Post Topic Link",
        filters={"parent": ["in", ids]},
        fields=["parent", "topic"],
    ):
        topic_map.setdefault(r.parent, []).append(r.topic)
    for r in frappe.get_all(
        "Cohort Post Scripture Ref",
        filters={"parent": ["in", ids]},
        fields=["parent", "display", "resolved_ref"],
    ):
        scr_map.setdefault(r.parent, []).append(
            {"display": r.display, "resolved_ref": r.resolved_ref}
        )
    # read-state: per-channel (new-posts divider) + per-thread (new-reply badge)
    fseen, tseen = {}, {}
    if me:
        cohort = posts[0]["cohort"]
        for r in frappe.get_all(
            "Cohort Feed Read State",
            filters={"person": me, "cohort": cohort},
            fields=["channel", "last_seen"],
        ):
            fseen[r.channel] = r.last_seen
        for r in frappe.get_all(
            "Cohort Thread Read State",
            filters={"person": me, "post": ["in", ids]},
            fields=["post", "last_seen"],
        ):
            tseen[r.post] = r.last_seen
    saved_set = set()
    if me:
        saved_set = set(
            frappe.get_all(
                "Cohort Post Save",
                filters={"person": me, "post": ["in", ids]},
                pluck="post",
            )
        )
    for p in posts:
        p["topics"] = topic_map.get(p["name"], [])
        p["scripture"] = scr_map.get(p["name"], [])
        p["is_mine"] = bool(me and p["author"] == me)
        p["saved"] = p["name"] in saved_set
        p["comment_count"] = frappe.db.count(
            "Cohort Post Comment", {"post": p["name"], "status": "published"}
        )
        # a post is "new" if it arrived since you last read its channel (not yours)
        fls = fseen.get(p["channel"])
        p["is_new"] = bool(
            me
            and fls
            and p["author"] != me
            and get_datetime(p["creation"]) > get_datetime(fls)
        )
        # unread replies: since you last opened the thread; for your own posts
        # with no prior view, every reply by someone else is unread.
        tls = tseen.get(p["name"])
        nc = {"post": p["name"], "status": "published"}
        if me:
            nc["author"] = ["!=", me]
        if tls:
            nc["creation"] = [">", tls]
            p["new_comments"] = frappe.db.count("Cohort Post Comment", nc)
        elif p["is_mine"]:
            p["new_comments"] = frappe.db.count("Cohort Post Comment", nc)
        else:
            p["new_comments"] = 0
        # foreground intra-cohort engagement: is the author a member of the
        # post's own cohort (vs an outside / portal voice)?
        p["author_membership"] = (
            "cohort_member"
            if frappe.db.exists(
                "Cohort Membership",
                {"cohort": p["cohort"], "person": p["author"], "active": 1},
            )
            else "outside"
        )
