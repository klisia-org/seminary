"""decisions/101: channels by cohort type, reactions by channel.

Nothing a site shows may change on upgrade (section 1.4, 2.1): every existing
cohort type offers every enabled channel, every channel offers every enabled
reaction and is a default, and existing types remind 24 and 1 hours before a
meeting as new ones do. Pray saves the post. Replies and reactions learn their
post's channel, which the permission clause now reads.

Child rows are written directly: saving each Cohort Type would run its whole
validation on records that predate several of its rules."""

import frappe

from seminary.seminary.doctype.cohort_type.cohort_type import DEFAULT_REMINDER_HOURS


def _add_rows(parenttype, parent, parentfield, child, values):
    start = frappe.db.count(child, {"parent": parent, "parentfield": parentfield})
    for i, row in enumerate(values, start=start + 1):
        frappe.get_doc(
            {
                "doctype": child,
                "parent": parent,
                "parenttype": parenttype,
                "parentfield": parentfield,
                "idx": i,
                **row,
            }
        ).db_insert()


def execute():
    channels = frappe.get_all(
        "Cohort Channel",
        filters={"enabled": 1},
        pluck="name",
        order_by="sort_order asc, channel_name asc",
    )
    reactions = frappe.get_all(
        "Cohort Reaction Type",
        filters={"enabled": 1},
        pluck="name",
        order_by="sort_order asc",
    )

    frappe.db.sql("update `tabCohort Channel` set is_default = 1")
    for channel in frappe.get_all("Cohort Channel", pluck="name"):
        if not frappe.db.exists("Cohort Channel Reaction", {"parent": channel}):
            _add_rows(
                "Cohort Channel",
                channel,
                "reactions",
                "Cohort Channel Reaction",
                [{"reaction_type": r} for r in reactions],
            )

    if frappe.db.exists("Cohort Reaction Type", "Pray"):
        frappe.db.set_value("Cohort Reaction Type", "Pray", "saves_post", 1)

    for cohort_type in frappe.get_all("Cohort Type", pluck="name"):
        if not frappe.db.exists("Cohort Type Channel", {"parent": cohort_type}):
            _add_rows(
                "Cohort Type",
                cohort_type,
                "channels",
                "Cohort Type Channel",
                [{"channel": c} for c in channels],
            )
        if not frappe.db.exists(
            "Cohort Type Meeting Reminder", {"parent": cohort_type}
        ):
            _add_rows(
                "Cohort Type",
                cohort_type,
                "meeting_reminders",
                "Cohort Type Meeting Reminder",
                [{"hours_before": h} for h in DEFAULT_REMINDER_HOURS],
            )
    frappe.db.sql(
        "update `tabCohort Type` set meetings_in_calendar_feed = 1"
        " where meetings_in_calendar_feed is null"
    )

    for table in ("Cohort Post Comment", "Cohort Post Reaction"):
        frappe.db.sql(
            f"""update `tab{table}` t
            join `tabCohort Post` p on p.name = t.post
            set t.channel = p.channel
            where ifnull(t.channel, '') = ''"""  # nosec B608: fixed table names
        )
