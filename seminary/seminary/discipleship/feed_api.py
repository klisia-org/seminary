"""Whitelisted feed endpoints for the Community frontend (Phase 2).

Reads go through frappe.get_list so the visibility scoping in permissions.py
applies automatically; writes check membership/visibility then insert with
ignore_permissions, the same posture as the partner portal API.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, now

from seminary.seminary.person import find_person
from seminary.seminary.discipleship.permissions import (
    STAFF_BYPASS,
    led_cohorts,
    my_channels,
    post_has,
    visible_cohorts,
)

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


def cohort_channels(cohort):
    """The channels a cohort offers: its type's (decisions/101 section 1)."""
    cohort_type = frappe.db.get_value("Cohort", cohort, "cohort_type")
    if not cohort_type:
        return []
    return frappe.get_all(
        "Cohort Type Channel",
        filters={"parenttype": "Cohort Type", "parent": cohort_type},
        pluck="channel",
        order_by="idx asc",
    )


def _require_channel(cohort, channel):
    if channel not in cohort_channels(cohort):
        frappe.throw(
            _("{0} is not a channel of this cohort.").format(channel),
            frappe.ValidationError,
        )


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
    _require_channel(cohort, channel)
    if not visibility:
        visibility = (
            frappe.db.get_value("Cohort", cohort, "visibility") or "cohort_only"
        )
    # ADR 076: writing to every mentor across a cohort subtree is a leadership
    # act, so it takes the same authority as the leader broadcast. Enforced here
    # and not only in the composer -- the Select is hidden for others, but a
    # hidden control is not a permission.
    if visibility == "mentors" and not (_is_staff() or cohort in led_cohorts()):
        frappe.throw(
            _("Only staff or a leader of this cohort can post to mentors."),
            frappe.PermissionError,
        )
    if visibility == "direct":
        # The recipient must be someone the author can already reach, so the
        # picker can never promise a post the permission layer would hide.
        if not direct_recipient:
            frappe.throw(_("A direct post needs a recipient."))
        if not _is_staff() and not _reachable_person(direct_recipient):
            frappe.throw(
                _("You can only write to people in your cohorts."),
                frappe.PermissionError,
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
    mine=None,
):
    filters = {"status": ["in", ["published", "pinned"]]}
    # `cohort` omitted means the All-posts view: no cohort filter at all, so
    # get_list's permission clause alone decides -- portal-wide posts, plus the
    # cohort_only posts of cohorts I belong to, plus my own private/direct. That
    # is exactly "all posts I may see", and it needs no query of its own.
    #
    # A selected cohort means *that* cohort, nothing widened: with All available,
    # mixing other cohorts' portal-wide posts into a single-cohort view would
    # make the two options overlap instead of compose.
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
    if int(mine or 0):
        filters["author"] = find_person(user=frappe.session.user) or ""
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
def search_posts(query, cohort=None, limit=30):
    """Search over one cohort's posts, or every post the caller may see —
    title/content plus topic and scripture-reference matches. get_list
    applies the visibility permission clause."""
    query = (query or "").strip()
    if len(query) < 2:
        return []
    like = f"%{query}%"
    scope = {"status": ["in", ["published", "pinned"]]}
    if cohort:
        scope["cohort"] = cohort
    names = set(
        frappe.get_list(
            "Cohort Post",
            filters=scope,
            or_filters=[["title", "like", like], ["content", "like", like]],
            pluck="name",
            page_length=int(limit),
        )
    )
    topics = frappe.get_all(
        "Cohort Post Topic", filters={"topic_name": ["like", like]}, pluck="name"
    )
    if topics:
        names.update(
            frappe.get_all(
                "Cohort Post Topic Link",
                filters={"topic": ["in", topics]},
                pluck="parent",
            )
        )
    names.update(
        frappe.get_all(
            "Cohort Post Scripture Ref",
            filters={"display": ["like", like]},
            pluck="parent",
        )
    )
    if not names:
        return []
    posts = frappe.get_list(
        "Cohort Post",
        filters={"name": ["in", list(names)], **scope},
        fields=_FEED_FIELDS,
        order_by="creation desc",
        page_length=int(limit),
    )
    _decorate_posts(posts)
    return posts


@frappe.whitelist()
def suggest_topics(query, limit=8):
    """Existing topics matching `query`, each with how many posts the caller
    can read use it (decisions/101 section 5.6). A topic only on posts the
    caller cannot read is not offered: its name alone may say too much."""
    query = (query or "").strip().lstrip("#").strip()
    if not query:
        return []
    topics = frappe.get_all(
        "Cohort Post Topic",
        filters={"topic_name": ["like", f"%{query}%"]},
        pluck="name",
        limit=100,
    )
    if not topics:
        return []
    links = frappe.get_all(
        "Cohort Post Topic Link",
        filters={"topic": ["in", topics], "parenttype": "Cohort Post"},
        fields=["parent", "topic"],
    )
    if not links:
        return []
    readable = set(
        frappe.get_list(
            "Cohort Post",
            filters={
                "name": ["in", list({link.parent for link in links})],
                "status": ["in", ["published", "pinned"]],
            },
            pluck="name",
            limit_page_length=0,
        )
    )
    counts = {}
    for link in links:
        if link.parent in readable:
            counts[link.topic] = counts.get(link.topic, 0) + 1
    q = query.lower()
    ranked = sorted(
        counts.items(),
        key=lambda kv: (not kv[0].lower().startswith(q), -kv[1], kv[0].lower()),
    )
    return [{"topic": t, "posts": n} for t, n in ranked[: int(limit)]]


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
            "is_private",
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
    # private replies: only the post author, the reply's writer, and cohort
    # leaders/staff may see them.
    from seminary.seminary.discipleship.permissions import led_cohorts

    viewer = find_person(user=frappe.session.user)
    can_lead = _is_staff() or doc.cohort in led_cohorts(frappe.session.user)
    comments = [
        c
        for c in comments
        if not c.get("is_private")
        or can_lead
        or c["author"] == viewer
        or doc.author == viewer
    ]
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
    post,
    content,
    parent_comment=None,
    anchor_type="General",
    anchor_data=None,
    is_private=0,
):
    person = _my_person()
    post_doc = frappe.get_doc("Cohort Post", post)
    if not post_has(post_doc, user=frappe.session.user):
        frappe.throw(_("You cannot reply to this post."), frappe.PermissionError)
    # portal-wide posts invite extra-cohort engagement; cohort/private posts stay
    # members-only (plus the post author).
    party = person == post_doc.author
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
        "is_private": 1 if int(is_private or 0) else 0,
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
    # decisions/101 section 3: a reaction that saves (Pray) keeps the post in
    # the person's Saved list. Only a post-level reaction does; taking it back
    # removes only the save it made. Neither touches the post itself.
    saves = not target and frappe.db.get_value(
        "Cohort Reaction Type", reaction_type, "saves_post"
    )
    if existing:
        frappe.delete_doc("Cohort Post Reaction", existing, ignore_permissions=True)
        if saves:
            made = frappe.db.exists(
                "Cohort Post Save", {"person": person, "post": post, "via_reaction": 1}
            )
            if made:
                frappe.delete_doc("Cohort Post Save", made, ignore_permissions=True)
        return {"reacted": False, "saved": _is_saved(person, post)}
    allowed = channel_reactions(post_doc.channel)
    if allowed and reaction_type not in allowed:
        frappe.throw(_("That reaction is not offered in this channel."))
    frappe.get_doc(
        {
            "doctype": "Cohort Post Reaction",
            "post": post,
            "comment": comment,
            "person": person,
            "reaction_type": reaction_type,
        }
    ).insert(ignore_permissions=True)
    if saves and not _is_saved(person, post):
        frappe.get_doc(
            {
                "doctype": "Cohort Post Save",
                "person": person,
                "post": post,
                "via_reaction": 1,
            }
        ).insert(ignore_permissions=True)
    return {"reacted": True, "saved": _is_saved(person, post)}


def _is_saved(person, post):
    return bool(frappe.db.exists("Cohort Post Save", {"person": person, "post": post}))


def channel_reactions(channel):
    """The reactions a channel offers (decisions/101 section 2). Empty means
    the channel was never given a list, and every enabled reaction applies."""
    if not channel:
        return []
    return frappe.get_all(
        "Cohort Channel Reaction",
        filters={"parenttype": "Cohort Channel", "parent": channel},
        pluck="reaction_type",
        order_by="idx asc",
    )


# --------------------------------------------------------------------------- #
# Read-state / unread
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def mark_seen(cohort=None, channel=None):
    """Mark a channel (or every channel, when channel is omitted) as read up to
    now — advances the 'new posts' baseline.

    Without a cohort this is the All-posts view, where the badge summed every
    cohort: clearing only one would leave a stale count, so it clears them all.
    """
    person = _my_person()
    if not person:
        return {"ok": False}
    cohorts = [cohort] if cohort else sorted(visible_cohorts())
    for c in cohorts:
        if channel:
            channels = [channel]
        else:
            channels = frappe.get_all(
                "Cohort Post",
                filters={"cohort": c, "status": ["in", ["published", "pinned"]]},
                distinct=True,
                pluck="channel",
            )
        for ch in channels:
            _upsert_seen(person, c, ch)
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
def unread_counts(cohort=None):
    """Per-channel unread post count for the caller.

    With a cohort, that cohort alone. Without one — the All-posts view — the
    counts are summed across every cohort the caller belongs to, because read
    state is keyed per (person, cohort, channel) and a channel is global: the
    same "Prayer" chip stands for prayer posts in all of them.

    Channels are site-wide (`Cohort Channel` has no cohort link), which is what
    makes the sum meaningful rather than a category error.
    """
    person = _my_person()
    if not person:
        return {}
    cohorts = [cohort] if cohort else sorted(visible_cohorts())
    if not cohorts:
        return {}

    seen = {}
    for r in frappe.get_all(
        "Cohort Feed Read State",
        filters={"person": person, "cohort": ["in", cohorts]},
        fields=["cohort", "channel", "last_seen"],
    ):
        seen[(r.cohort, r.channel)] = r.last_seen

    out = {}
    for c in cohorts:
        channels = frappe.get_all(
            "Cohort Post",
            filters={"cohort": c, "status": ["in", ["published", "pinned"]]},
            distinct=True,
            pluck="channel",
        )
        for ch in channels:
            filters = {
                "cohort": c,
                "channel": ch,
                "status": ["in", ["published", "pinned"]],
                "author": ["!=", person],
            }
            last = seen.get((c, ch))
            if last:
                filters["creation"] = [">", last]
            n = len(frappe.get_list("Cohort Post", filters=filters, pluck="name"))
            if n:
                out[ch] = out.get(ch, 0) + n
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
    was_answered = doc.prayer_answered
    doc.prayer_answered = 1
    if note:
        doc.prayer_answer_note = note
    doc.save(ignore_permissions=True)
    if not was_answered:
        frappe.enqueue(
            "seminary.seminary.discipleship.feed_api.tell_praying_partners",
            post=doc.name,
            queue="short",
            enqueue_after_commit=True,
            now=bool(frappe.flags.in_test),
        )
    return doc.name


def praying_partners(post):
    """People who reacted to the post with a reaction that saves it (Pray),
    saved or not since, who can still read it (decisions/101 section 3.4)."""
    doc = frappe.get_doc("Cohort Post", post)
    saving = frappe.get_all(
        "Cohort Reaction Type", filters={"saves_post": 1}, pluck="name"
    )
    if not saving:
        return []
    people = set(
        frappe.get_all(
            "Cohort Post Reaction",
            filters={
                "post": post,
                "reaction_type": ["in", saving],
                "comment": ["is", "not set"],
            },
            pluck="person",
        )
    )
    people.discard(doc.author)
    out = []
    for person in sorted(people):
        user = frappe.db.get_value("Person", person, "user")
        # Someone with no account cannot have reacted, but a Person can lose
        # their user; without one there is no reader to check, so skip.
        if user and post_has(doc, user=user):
            out.append(person)
    return out


def tell_praying_partners(post):
    from seminary.seminary import comms

    doc = frappe.get_doc("Cohort Post", post)
    author = frappe.db.get_value("Person", doc.author, "full_name") or ""
    title = doc.title or _("a prayer request")
    subject = _("{0}'s prayer was answered").format(author)
    message = _("<p>{0} marked “{1}” answered.</p>").format(
        frappe.utils.escape_html(author), frappe.utils.escape_html(title)
    )
    if doc.prayer_answer_note:
        message += "<blockquote>{0}</blockquote>".format(
            frappe.utils.escape_html(doc.prayer_answer_note)
        )
    for person in praying_partners(post):
        for channel in ("In-App", "Email"):
            try:
                comms.send_message(
                    channel=channel,
                    subject=subject,
                    message=message,
                    person=person,
                    category="Community",
                    reference_doctype="Cohort Post",
                    reference_name=doc.name,
                    dedupe_key=f"prayer-answered:{doc.name}:{person}:{channel}",
                )
            except Exception:
                frappe.log_error(title=f"Answered prayer notice failed: {post}")


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
    video_url=None,
):
    _require_author_or_staff(post)
    doc = frappe.get_doc("Cohort Post", post)
    if title is not None:
        doc.title = title
    if content is not None:
        doc.content = content  # controller re-sanitizes
    if video_url is not None:
        doc.video_url = video_url  # controller requires it for Sermon Lab posts
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
            "Cohort",
            r.cohort,
            ["cohort_name", "status", "visibility", "cohort_type"],
            as_dict=True,
        )
        if c and c.status == "Active":
            kind = (
                frappe.db.get_value(
                    "Cohort Type",
                    c.cohort_type,
                    ["school_meeting_allowed", "meetings_in_calendar_feed"],
                    as_dict=True,
                )
                if c.cohort_type
                else None
            ) or {}
            out.append(
                {
                    "name": r.cohort,
                    "cohort_name": c.cohort_name,
                    "cohort_type": c.cohort_type,
                    "is_leader": r.is_leader,
                    "role": r.role,
                    "visibility": c.visibility,
                    "school_meeting_allowed": kind.get("school_meeting_allowed") or 0,
                    "calendar_feed": kind.get("meetings_in_calendar_feed") or 0,
                }
            )
    return out


def _reachable_person(person):
    """Whether `person` shares a cohort the caller can see (ADR 076)."""
    cohorts = visible_cohorts()
    if not cohorts:
        return False
    return bool(
        frappe.get_all(
            "Cohort Membership",
            filters={
                "person": person,
                "cohort": ["in", list(cohorts)],
                "active": 1,
            },
            limit=1,
        )
    )


@frappe.whitelist()
def search_recipients(query, limit=10):
    """Type-ahead over people the caller may write to directly (ADR 076).

    Scoped to `visible_cohorts` rather than every Person on the site: as cohort
    lineage grows an unscoped picker is both unusable and wrong, because it
    offers recipients the permission layer would then refuse. The list is never
    enumerated, only searched, so lineage size does not matter.

    Returns the cohort name alongside each person, because the same name can
    appear in several and the author needs to tell them apart.
    """
    query = (query or "").strip()
    if len(query) < 2:
        return []
    cohorts = visible_cohorts()
    if not cohorts:
        return []
    me = _my_person()
    rows = frappe.db.sql(
        """
        SELECT DISTINCT m.person, p.full_name, c.cohort_name
        FROM `tabCohort Membership` m
        JOIN `tabPerson` p ON p.name = m.person
        LEFT JOIN `tabCohort` c ON c.name = m.cohort
        WHERE m.active = 1
          AND m.cohort IN %(cohorts)s
          AND p.full_name LIKE %(like)s
          AND m.person != %(me)s
        ORDER BY p.full_name ASC
        LIMIT %(limit)s
        """,
        {
            "cohorts": tuple(cohorts),
            "like": "%" + query + "%",
            "me": me or "",
            "limit": int(limit),
        },
        as_dict=True,
    )
    return rows


@frappe.whitelist()
def list_channels(cohort=None):
    """The channels on offer (decisions/101 section 1): one cohort's, or
    those of every cohort the caller can see. Staff in no cohort see all.
    Each carries the reactions it offers (section 2)."""
    if cohort:
        if not (_is_staff() or cohort in visible_cohorts()):
            frappe.throw(_("You cannot see this cohort."), frappe.PermissionError)
        offered = set(cohort_channels(cohort))
    else:
        offered = my_channels()
        if not offered and _is_staff():
            offered = None
    filters = {"enabled": 1}
    if offered is not None:
        filters["name"] = ["in", list(offered) or [""]]
    rows = frappe.get_all(
        "Cohort Channel",
        filters=filters,
        fields=["name", "channel_name", "channel_kind", "description"],
        order_by="sort_order asc, channel_name asc",
    )
    for r in rows:
        r["reactions"] = channel_reactions(r.name)
    return rows


@frappe.whitelist()
def list_reaction_types():
    return frappe.get_all(
        "Cohort Reaction Type",
        filters={"enabled": 1},
        fields=["name", "label", "glyph", "saves_post"],
        order_by="sort_order asc",
    )


@frappe.whitelist()
def channel_counts(cohort=None):
    """Visible published posts per channel, for the rail."""
    filters = {"status": ["in", ["published", "pinned"]]}
    if cohort:
        filters["cohort"] = cohort
    out = {}
    for channel in frappe.get_list("Cohort Post", filters=filters, pluck="channel"):
        out[channel] = out.get(channel, 0) + 1
    return out


@frappe.whitelist()
def community_summary():
    """The rail and the header: each cohort with its type, size and new posts,
    and when the caller last read anything (decisions/101 section 5)."""
    person = _my_person()
    cohorts = my_cohorts_list()
    names = [c["name"] for c in cohorts]
    sizes = {}
    if names:
        for cohort in frappe.get_all(
            "Cohort Membership",
            filters={"cohort": ["in", names], "active": 1},
            pluck="cohort",
        ):
            sizes[cohort] = sizes.get(cohort, 0) + 1
    total = 0
    for c in cohorts:
        c["members"] = sizes.get(c["name"], 0)
        c["new"] = sum(unread_counts(c["name"]).values())
        total += c["new"]
    last = frappe.get_all(
        "Cohort Feed Read State",
        filters={"person": person},
        pluck="last_seen",
        order_by="last_seen desc",
        limit=1,
    )
    return {"cohorts": cohorts, "new": total, "since": last[0] if last else None}


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
    "reference_doctype",
    "reference_name",
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
            (r.get(field), r.reaction_type), {"count": 0, "mine": False, "people": []}
        )
        bucket["count"] += 1
        bucket["people"].append(r.person)
        if person and r.person == person:
            bucket["mine"] = True
    # Who reacted, by name, for the hover list (decisions/101 section 2.2).
    everyone = {p for v in summary.values() for p in v["people"]}
    names = (
        {
            p.name: p.full_name
            for p in frappe.get_all(
                "Person",
                filters={"name": ["in", list(everyone)]},
                fields=["name", "full_name"],
            )
        }
        if everyone
        else {}
    )
    for row in rows:
        row["reactions"] = [
            {
                "reaction_type": rt,
                "glyph": glyphs.get(rt),
                "count": v["count"],
                "mine": v["mine"],
                "people": [names.get(p) or p for p in v["people"][:20]],
            }
            for (tid, rt), v in summary.items()
            if tid == row["name"]
        ]


def _attach_reference_labels(posts):
    """`p["on_behalf_of"]` = {label, route} for a post written about a record,
    from the app that owns the record (hook `cohort_post_reference_label`:
    a callable taking the post rows of one doctype and returning
    {post name: {label, route}}). koinonia labels prayer requests posted for
    a Donor (p018). The route is the app's to decide, so only staff get one."""
    hooks = frappe.get_hooks("cohort_post_reference_label") or {}
    by_doctype = {}
    for p in posts:
        if p.get("reference_doctype") in hooks and p.get("reference_name"):
            by_doctype.setdefault(p["reference_doctype"], []).append(p)
    for doctype, rows in by_doctype.items():
        path = hooks[doctype]
        labels = (
            frappe.get_attr(path[-1] if isinstance(path, list) else path)(rows) or {}
        )
        for p in rows:
            if p["name"] in labels:
                p["on_behalf_of"] = labels[p["name"]]


def _decorate_posts(posts):
    if not posts:
        return
    _attach_names(posts, "author")
    _attach_reference_labels(posts)
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
