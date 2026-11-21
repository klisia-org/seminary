# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Students' own time zones (decisions/100d-a §9).

Frappe's User has ``time_zone``, but it is filled with the site's zone when the
account is made, so it says nothing about the person. The portal reports the
browser's zone at sign-in: a zone still at the site default is replaced, and a
student whose own zone differs is asked before it changes.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import frappe
from frappe import _
from frappe.utils import get_system_timezone


def _valid(tz):
    if not tz or not isinstance(tz, str) or len(tz) > 64:
        return None
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return tz


def own_zone(user):
    """The user's own zone, or None while it is only the site's default."""
    tz = frappe.db.get_value("User", user, "time_zone")
    if not tz or tz == get_system_timezone():
        return None
    return tz


def zone_or_site(user):
    return own_zone(user) or get_system_timezone()


@frappe.whitelist(methods=["POST"])
def report(tz):
    """The browser's zone at sign-in: written while the user has none of their
    own; otherwise ``ask`` when it differs."""
    user = frappe.session.user
    if user == "Guest":
        return {}
    tz = _valid(tz)
    if not tz:
        return {}
    stored = frappe.db.get_value("User", user, "time_zone")
    if not stored or stored == get_system_timezone():
        if tz != stored:
            frappe.db.set_value("User", user, "time_zone", tz)
        return {"time_zone": tz}
    if stored != tz:
        return {"time_zone": stored, "ask": True, "browser": tz}
    return {"time_zone": stored}


@frappe.whitelist(methods=["POST"])
def set_my_time_zone(tz):
    if frappe.session.user == "Guest":
        frappe.throw(_("Sign in first."), frappe.PermissionError)
    tz = _valid(tz)
    if not tz:
        frappe.throw(_("That is not a time zone."))
    frappe.db.set_value("User", frappe.session.user, "time_zone", tz)
    return tz


@frappe.whitelist()
def my_time_zone():
    if frappe.session.user == "Guest":
        return {}
    return {
        "time_zone": frappe.db.get_value("User", frappe.session.user, "time_zone"),
        "site": get_system_timezone(),
    }


def offset_minutes(tz, at=None):
    """The zone's offset from UTC now (or at a naive UTC datetime), in minutes."""
    if not tz:
        return None
    zone = ZoneInfo(tz)
    moment = (at or datetime.utcnow()).replace(tzinfo=ZoneInfo("UTC")).astimezone(zone)
    return int(moment.utcoffset().total_seconds() // 60)
