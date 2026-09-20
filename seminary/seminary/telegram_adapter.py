"""Telegram channel adapter (ADR 043).

Setup:
1. Create a bot with @BotFather and copy its token.
2. Channel Provider Account: channel=Telegram, provider=telegram, settings:
   {"bot_token": "...", "webhook_secret": "<random string>"}
3. Register the webhook (site must be publicly reachable over HTTPS):
   bench --site <site> execute seminary.seminary.telegram_adapter.setup_webhook \
       --kwargs "{'account': '<account name>'}"
4. Recipients connect from the portal Preferences page: the "Connect
   Telegram" deep link (t.me/<bot>?start=<signed token>) makes their /start
   update write the chat id onto their Person as a verified Telegram channel
   address. Bots cannot message a chat first — this onboarding IS how
   Telegram becomes reachable.

Outbound: the Person Channel Address value for the Telegram channel is the
chat id; messages send as plain text (HTML snapshot flattened) and the
provider_message_id is "<chat_id>:<message_id>" (Telegram message ids are only
unique per chat). Telegram bots get no delivery/read receipts, so logs stay
at Sent; inbound replies arrive through the shared comms.webhook endpoint,
verified by Telegram's X-Telegram-Bot-Api-Secret-Token header.
"""

import hashlib
import hmac
import html
import re
from urllib.parse import quote

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, now_datetime, strip_html
from frappe.utils.password import get_encryption_key

API = "https://api.telegram.org/bot{token}/{method}"
TELEGRAM_CHANNEL = "Telegram"


def _settings(account):
    from seminary.seminary.comms import account_settings

    return account_settings(account)


def _api(account, method, payload):
    token = _settings(account).get("bot_token")
    if not token:
        raise ValueError(
            f"Channel Provider Account {account.name} has no bot_token in settings"
        )
    response = requests.post(
        API.format(token=token, method=method), json=payload, timeout=15
    )
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data.get('description')}")
    return data["result"]


def _to_text(subject, message):
    """Flatten the HTML snapshot to plain text within Telegram's 4096 limit."""
    text = message or ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>\s*", "\n\n", text, flags=re.I)
    text = html.unescape(strip_html(text)).strip()
    if subject:
        text = f"{subject}\n\n{text}" if text else subject
    return text[:4096]


class TelegramAdapter:
    final_status = "Sent"

    def send(self, log, account):
        if not log.to_address:
            raise ValueError("Telegram log has no chat id (to_address)")
        result = _api(
            account,
            "sendMessage",
            {"chat_id": log.to_address, "text": _to_text(log.subject, log.message)},
        )
        return f"{log.to_address}:{result.get('message_id')}"

    def verify_webhook(self, account, settings, provided):
        expected = settings.get("webhook_secret")
        if not expected:
            return False
        if not provided:
            request = getattr(frappe.local, "request", None)
            if request is not None:
                provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        return bool(provided) and hmac.compare_digest(str(provided), str(expected))

    def handle_webhook(self, payload, account):
        message = payload.get("message")
        if not isinstance(message, dict):
            return None  # edited_message, callback_query etc. — not handled
        chat_id = str((message.get("chat") or {}).get("id") or "")
        text = message.get("text") or message.get("caption") or ""
        if not chat_id or not text:
            return None
        if text.startswith("/start"):
            _handle_start(account, chat_id, text)
            return None
        return {
            "kind": "inbound",
            "from_address": chat_id,
            "body": text,
            "provider_message_id": f"{chat_id}:{message.get('message_id')}",
        }


# ------------------------------------------------------- connect onboarding


#: A connect link is used within minutes of being generated. A week is already
#: generous, and it is the whole point: before this the token never expired.
CONNECT_TOKEN_TTL_DAYS = 7


def _connect_signature(payload: str) -> str:
    return hmac.new(
        get_encryption_key().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:32]


def make_connect_token(person):
    """Deep-link payload binding a /start update to a Person, for a week.

    Signed with the site encryption key so chat ids can't be attached to
    arbitrary Persons. Telegram start payloads allow `[A-Za-z0-9_-]` and at
    most 64 characters, which is why this is `person_expiry_signature` rather
    than the base64 `payload.signature` shape `address_verification` uses --
    `.` is not in Telegram's alphabet. PERS ids contain no underscore, so the
    three parts are unambiguous, and the whole token is ~51 characters.

    p005a A04-1: this was `hexdigest()[:12]`, **deterministic per Person, with
    no expiry and no revocation** -- a connect link in a forwarded message or a
    screenshot bound that stranger's chat to the Person for ever.
    `address_verification` was written later, explicitly modelled on this
    function, and does it right; this is the port that was never made (p010 H9).

    The signature covers the expiry as well as the Person, so the deadline
    cannot be edited, and it is 128 bits rather than 48.
    """
    expires = int(add_to_date(now_datetime(), days=CONNECT_TOKEN_TTL_DAYS).timestamp())
    stamp = _b36(expires)
    return f"{person}_{stamp}_{_connect_signature(f'{person}|{expires}')}"


def _b36(number: int) -> str:
    """Base36, to keep the expiry inside Telegram's 64-character budget."""
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if number <= 0:
        return "0"
    out = ""
    while number:
        number, rem = divmod(number, 36)
        out = digits[rem] + out
    return out


def verify_connect_token(payload):
    """The Person a token names, or None for anything forged, malformed or
    expired. An old two-part token is refused: it is exactly the never-expiring
    kind this replaced."""
    if not payload or payload.count("_") != 2:
        return None
    person, stamp, sig = payload.split("_")
    if not frappe.db.exists("Person", person):
        return None
    try:
        expires = int(stamp, 36)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _connect_signature(f"{person}|{expires}")):
        return None
    if expires < int(now_datetime().timestamp()):
        return None
    return person


def _handle_start(account, chat_id, text):
    parts = text.split(maxsplit=1)
    person_name = verify_connect_token(parts[1].strip() if len(parts) > 1 else "")
    if not person_name:
        _reply(
            account,
            chat_id,
            _(
                "Hi! To connect this chat to your seminary account, use the "
                "Connect Telegram link on your portal Preferences page."
            ),
        )
        return
    person = frappe.get_doc("Person", person_name)
    row = next(
        (
            r
            for r in person.channel_addresses
            if r.channel == TELEGRAM_CHANNEL and r.value == chat_id
        ),
        None,
    )
    changed = False
    if not row:
        has_primary = any(
            r.channel == TELEGRAM_CHANNEL and r.is_primary
            for r in person.channel_addresses
        )
        person.append(
            "channel_addresses",
            {
                "channel": TELEGRAM_CHANNEL,
                "value": chat_id,
                "is_primary": 0 if has_primary else 1,
                "verified": 1,
                "status": "Active",
            },
        )
        changed = True
    elif not row.verified or row.status != "Active":
        row.verified = 1
        row.status = "Active"
        changed = True
    if changed:
        person.save(ignore_permissions=True)
    _reply(
        account,
        chat_id,
        _("Connected! {0}, you'll now receive seminary messages here.").format(
            person.full_name
        ),
    )


def _reply(account, chat_id, text):
    try:
        _api(account, "sendMessage", {"chat_id": chat_id, "text": text})
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Telegram reply failed")


@frappe.whitelist()
def get_my_telegram_link():
    """Portal/desk: the deep link the session user opens to connect their
    Telegram. None when no enabled Telegram provider account exists."""
    from seminary.seminary.comms import _my_person, pick_account

    person = _my_person()
    account_name = pick_account(
        TELEGRAM_CHANNEL, frappe.db.get_value("Person", person, "country")
    )
    if not account_name:
        return None
    username = _bot_username(frappe.get_doc("Channel Provider Account", account_name))
    if not username:
        return None
    connected = frappe.db.get_value(
        "Person Channel Address",
        {
            "parenttype": "Person",
            "parent": person,
            "channel": TELEGRAM_CHANNEL,
            "verified": 1,
        },
        "name",
    )
    return {
        "url": f"https://t.me/{username}?start={make_connect_token(person)}",
        "bot": username,
        "connected": bool(connected),
    }


def _bot_username(account):
    settings = _settings(account)
    if settings.get("bot_username"):
        return settings["bot_username"]
    cache_key = f"telegram_bot_username::{account.name}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached
    try:
        me = _api(account, "getMe", {})
    except Exception:
        return None
    frappe.cache().set_value(cache_key, me.get("username"))
    return me.get("username")


@frappe.whitelist()
def register_webhook(account, base_url=None):
    """Desk button entry point (Channel Provider Account). Registers this
    account's webhook with Telegram; base_url overrides the site URL for dev
    tunnels. Returns the registered URL."""
    frappe.has_permission("Channel Provider Account", "write", throw=True)
    return setup_webhook(account, base_url=base_url or None)


def setup_webhook(account, base_url=None):
    """Register the comms webhook with Telegram for this account.
    bench --site <site> execute seminary.seminary.telegram_adapter.setup_webhook \
        --kwargs "{'account': '<name>'}"

    Telegram only accepts public HTTPS URLs. base_url overrides the site URL —
    on dev, point it at a tunnel (cloudflared/ngrok) in front of the bench."""
    acc = frappe.get_doc("Channel Provider Account", account)
    secret = _settings(acc).get("webhook_secret")
    if not secret:
        frappe.throw(_("Set webhook_secret in the account settings first."))
    path = f"/api/method/seminary.seminary.comms.webhook?account={quote(account)}"
    url = f"{base_url.rstrip('/')}{path}" if base_url else frappe.utils.get_url(path)
    if not url.startswith("https://"):
        frappe.throw(
            _(
                "Telegram requires a public HTTPS webhook URL; got {0}. "
                "Pass base_url (e.g. a cloudflared/ngrok tunnel) or set the "
                "site's host_name."
            ).format(url)
        )
    _api(
        acc,
        "setWebhook",
        {"url": url, "secret_token": secret, "allowed_updates": ["message"]},
    )
    print(f"Telegram webhook registered: {url}")
    return url
