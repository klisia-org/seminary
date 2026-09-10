"""Confirm that a channel address reaches the person who claimed it (ADR 070).

`Person Channel Address.verified` used to mean whatever a registrar ticked.
Telegram was the one honest exception — pressing Start in the bot with a signed
deep-link token proves possession — and this module gives Email the same kind of
proof, because `EmailAdapter.final_status` is only "Sent" and can never confirm
anything on its own. Twilio channels need nothing here: a carrier's Delivered
webhook is stronger evidence than a click, and `comms._set_address_state` acts
on it.

The token follows `telegram_adapter.make_connect_token` — an HMAC under the site
encryption key, with no doctype behind it — and differs in three ways that the
medium forces:

* the address is inside the signature, so a token cannot be replayed against a
  different row on the same Person;
* it expires, because an email sits in an archive indefinitely while a Telegram
  deep link is pasted within seconds;
* the digest is 32 hex characters rather than 12, since only Telegram's
  start-parameter grammar constrained the original.

The confirming surface is `www/verify-address`, a plain page rather than a
whitelisted guest method: it must work with no session at all (the mail opens in
a phone's mail client, and the address being confirmed is frequently not the
login email), and a page leaves no JSON endpoint to probe.
"""

import base64
import hashlib
import hmac

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime
from frappe.utils.password import get_encryption_key

TOKEN_TTL_DAYS = 7
VERIFICATION_TEMPLATE = "address-verification"


def _signature(payload: str) -> str:
    return hmac.new(
        get_encryption_key().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:32]


def make_token(person: str, channel: str, value: str) -> str:
    """A confirm token for one address on one Person."""
    expires = int(add_to_date(now_datetime(), days=TOKEN_TTL_DAYS).timestamp())
    payload = f"{person}|{channel}|{(value or '').lower()}|{expires}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{encoded}.{_signature(payload)}"


def read_token(token: str) -> dict | None:
    """Decode and authenticate a token. None for anything malformed or forged;
    an expired token still decodes, so the page can say so."""
    if not token or "." not in token:
        return None
    encoded, _sep, sig = token.rpartition(".")
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = base64.urlsafe_b64decode(encoded + padding).decode()
    except Exception:
        return None
    parts = payload.split("|")
    if len(parts) != 4:
        return None
    person, channel, value, expires = parts
    if not hmac.compare_digest(sig, _signature(payload)):
        return None
    try:
        expires = int(expires)
    except ValueError:
        return None
    return {
        "person": person,
        "channel": channel,
        "value": value,
        "expires": expires,
        "expired": expires < int(now_datetime().timestamp()),
    }


def apply_token(token: str) -> dict:
    """Confirm the address a token names.

    The row is re-resolved by (person, channel, value) rather than by row name:
    the token carries no row id because the row may have been edited or removed
    since the mail went out, and the address is what was actually proved.

    States: confirmed | already | expired | invalid | gone.
    """
    data = read_token(token)
    if not data:
        return {"state": "invalid"}
    if data["expired"]:
        return {"state": "expired", "channel": data["channel"], "value": data["value"]}

    row = frappe.db.get_value(
        "Person Channel Address",
        {
            "parenttype": "Person",
            "parent": data["person"],
            "channel": data["channel"],
            "value": data["value"],
        },
        ["name", "verified"],
        as_dict=True,
    )
    if not row:
        return {"state": "gone", "channel": data["channel"], "value": data["value"]}
    if row.verified:
        return {"state": "already", "channel": data["channel"], "value": data["value"]}

    # Written straight to the child row. A Person.save() here would run as
    # Guest and fire propagation plus a queued geocode, and could throw on an
    # unrelated pre-existing duplicate — losing a confirmation the person has
    # already made. Status resets to Active because mail arriving at an address
    # is the end of whatever bounce marked it.
    frappe.db.set_value(
        "Person Channel Address",
        row.name,
        {"verified": 1, "verified_on": now_datetime(), "status": "Active"},
        update_modified=False,
    )
    return {"state": "confirmed", "channel": data["channel"], "value": data["value"]}


def confirm_url(person: str, channel: str, value: str) -> str:
    token = make_token(person, channel, value)
    return frappe.utils.get_url(f"/verify-address?t={token}")


def send_verification(person: str, channel: str, value: str, row: str) -> str | None:
    """Mail the confirm link to the address being confirmed.

    `to_address` is load-bearing: without it `send_message` falls back to
    `resolve_address`, which would send the confirmation to the person's
    primary address and confirm nothing. Transactional, because a confirmation
    is account service rather than outreach and must not be silenced by a
    Community opt-out. The dedupe key gives one mail per row per day for free —
    `_insert_log` returns None on a repeat, so the caller can say so honestly
    instead of reporting a send that did not happen.
    """
    from seminary.seminary import comms

    if channel != comms.EMAIL_CHANNEL:
        return None
    return comms.send(
        person,
        VERIFICATION_TEMPLATE,
        to_address=value,
        channel=comms.EMAIL_CHANNEL,
        category="Transactional",
        context={
            "address": value,
            "url": confirm_url(person, channel, value),
            "days": TOKEN_TTL_DAYS,
        },
        reference_doctype="Person",
        reference_name=person,
        dedupe_key=f"verify::{row}::{frappe.utils.today()}",
    )


@frappe.whitelist(methods=["POST"])
def request_verification(row):
    """Portal: send (or re-send) the confirmation for one of my own addresses."""
    from seminary.seminary import comms

    _person, info = comms._my_address_row(row)
    if info.channel != comms.EMAIL_CHANNEL:
        frappe.throw(
            _(
                "{0} addresses are confirmed automatically once a message "
                "reaches them."
            ).format(_(info.channel))
        )
    log = send_verification(info.parent, info.channel, info.value, info.name)
    if not log:
        return {"sent": False, "reason": "already_sent_today"}
    return {"sent": True}
