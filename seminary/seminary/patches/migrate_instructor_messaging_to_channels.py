"""Retire the Instructor Messaging App island into the comms spine (ADR 042/043).

The legacy `Instructor Messaging App` child (→ `Messaging App` master) plus
`Instructor.phone_message` powered WhatsApp/Telegram deep-link icons that opened
the instructor's *personal* app — untracked and ungoverned. This patch folds
that into the unified stack:

  - the icon/prefix metadata moves onto `Communication Channel`,
  - each instructor's WhatsApp number becomes a `Person Channel Address`,
  - the per-instructor `students_may_contact` toggle defaults on, and
  - the two retired doctypes are deleted.

Telegram links are **not** migrated: the legacy value was a phone number, but
the comms Telegram channel addresses a bot chat-id (only obtainable via the bot
/start onboarding). Those instructors are counted so ops can re-onboard them.

Runs after `create_person_spine` (every instructor already has a Person) and is
idempotent — the guard short-circuits once the legacy doctype is gone.
"""

import frappe

from seminary.install import seed_communication_channels

# Legacy Messaging App name -> Communication Channel name (they already match).
_APP_TO_CHANNEL = {"WhatsApp": "WhatsApp", "Telegram": "Telegram"}


def execute():
    if not frappe.db.exists("DocType", "Instructor Messaging App"):
        return  # already migrated

    # Channels (and their new contact metadata) must exist before addresses.
    seed_communication_channels()

    # 1) Carry any seminary-customised icon/prefix from the retired master onto
    #    the matching channel, where the channel field is still empty.
    if frappe.db.exists("DocType", "Messaging App"):
        for app in frappe.get_all(
            "Messaging App", fields=["app_name", "url_prefix", "svg_icon"]
        ):
            channel = _APP_TO_CHANNEL.get(app.app_name, app.app_name)
            if not frappe.db.exists("Communication Channel", channel):
                continue
            current = frappe.db.get_value(
                "Communication Channel",
                channel,
                ["weblink_prefix", "svg_icon"],
                as_dict=True,
            )
            updates = {}
            if app.url_prefix and not current.weblink_prefix:
                updates["weblink_prefix"] = app.url_prefix
            if app.svg_icon and not current.svg_icon:
                updates["svg_icon"] = app.svg_icon
            if updates:
                updates["portal_contactable"] = 1
                frappe.db.set_value("Communication Channel", channel, updates)

    # 2) Per-instructor: WhatsApp number -> Person Channel Address.
    by_instructor = {}
    for row in frappe.get_all(
        "Instructor Messaging App",
        filters={"parenttype": "Instructor"},
        fields=["parent", "messaging_app"],
    ):
        by_instructor.setdefault(row.parent, []).append(row.messaging_app)

    migrated = whatsapp_created = telegram_skipped = no_person = 0
    for instructor_name, apps in by_instructor.items():
        info = frappe.db.get_value(
            "Instructor", instructor_name, ["person", "phone_message"], as_dict=True
        )
        if not info or not info.person:
            no_person += 1
            continue
        migrated += 1
        phone = (info.phone_message or "").strip()
        person = frappe.get_doc("Person", info.person)
        touched = False
        for app in apps:
            app_name = frappe.db.get_value("Messaging App", app, "app_name") or app
            channel = _APP_TO_CHANNEL.get(app_name, app_name)
            if channel == "Telegram":
                # Phone is not a chat-id — Telegram needs bot onboarding.
                telegram_skipped += 1
                continue
            if channel != "WhatsApp" or not phone:
                continue
            if any(
                a.channel == channel and a.value == phone
                for a in person.channel_addresses
            ):
                continue
            person.append(
                "channel_addresses",
                {"channel": channel, "value": phone, "status": "Active"},
            )
            whatsapp_created += 1
            touched = True
        if touched:
            person.save(ignore_permissions=True)

    # 3) Default the audience toggle for existing rows (new column may be NULL).
    frappe.db.sql(
        "UPDATE `tabInstructor` SET students_may_contact = 1 "
        "WHERE students_may_contact IS NULL"
    )
    frappe.db.commit()
    print(
        f"Instructor messaging migrated: {migrated} instructor(s), "
        f"{whatsapp_created} WhatsApp address(es), "
        f"{telegram_skipped} Telegram link(s) skipped (need bot connect), "
        f"{no_person} without a Person (skipped)."
    )

    # 4) Retire the legacy doctypes — data now lives on Person + Channel.
    frappe.delete_doc(
        "DocType", "Instructor Messaging App", force=True, ignore_missing=True
    )
    frappe.delete_doc("DocType", "Messaging App", force=True, ignore_missing=True)
    frappe.db.commit()
