"""Twilio channel adapter for SMS, WhatsApp, and Voice (ADR 043/045).

One adapter serves all three: SMS and WhatsApp go through the Messages API
(WhatsApp just prefixes the To/From addresses with ``whatsapp:``); Voice places
a call through the Calls API that reads the message aloud (TwiML <Say>). The
channel comes from the Channel Provider Account, so each is its own account
pointing at the same ``twilio`` provider. Voice reuses the SMS phone number
(``resolve_address`` falls back from Voice to SMS).

Setup (per channel):
1. In the Twilio console, get the Account SID, Auth Token, and a sending number
   (SMS long code / short code, or a WhatsApp-enabled number / sender).
2. Channel Provider Account: channel=SMS (or WhatsApp), provider=twilio, settings:
   {"account_sid": "AC...", "auth_token": "...", "from_number": "+15551234567"}
   (use "messaging_service_sid" instead of "from_number" for a Messaging Service).
3. Delivery receipts are automatic: send() sets a per-message StatusCallback to
   the shared comms webhook, so Twilio advances the log to Delivered/Failed.
4. Inbound replies: point the number's "A message comes in" webhook (Twilio
   console) at the same endpoint —
   /api/method/seminary.seminary.comms.webhook?account=<account name>
   Inbound and status callbacks are verified by Twilio's X-Twilio-Signature.

Outbound: the Person Channel Address value for the channel is the phone number
(E.164, e.g. +15551234567). Bodies are sent as plain text (HTML snapshot
flattened); long SMS are segmented by Twilio automatically. The
provider_message_id is the Twilio Message SID.
"""

import base64
import hashlib
import hmac
import html
import re

import frappe
import requests
from frappe import _
from frappe.utils import strip_html

API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
CALLS_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"
WHATSAPP_CHANNEL = "WhatsApp"
VOICE_CHANNEL = "Voice"

# Twilio Call status -> our canonical Communication Log status.
_CALL_STATUS = {
    "completed": "Delivered",
    "answered": "Delivered",
    "busy": "Failed",
    "failed": "Failed",
    "no-answer": "Failed",
    "canceled": "Failed",
}


def _settings(account):
    from seminary.seminary.comms import account_settings

    return account_settings(account)


def _to_text(subject, message):
    """Flatten the HTML snapshot to plain text. Twilio segments long SMS, so no
    hard length cap is applied here."""
    text = message or ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>\s*", "\n\n", text, flags=re.I)
    text = html.unescape(strip_html(text)).strip()
    if subject:
        text = f"{subject}\n\n{text}" if text else subject
    return text


def _prefix(account):
    return "whatsapp:" if account.channel == WHATSAPP_CHANNEL else ""


class TwilioAdapter:
    # Twilio accepts the message immediately; Delivered/Failed arrives later via
    # the StatusCallback webhook.
    final_status = "Sent"

    def send(self, log, account):
        if not log.to_address:
            raise ValueError("Twilio log has no to_address (phone number)")
        settings = _settings(account)
        sid = settings.get("account_sid")
        token = settings.get("auth_token")
        if not sid or not token:
            raise ValueError(
                f"Channel Provider Account {account.name} needs account_sid and "
                "auth_token in settings"
            )
        if account.channel == VOICE_CHANNEL:
            return self._place_call(log, account, settings, sid, token)
        prefix = _prefix(account)
        data = {
            "To": f"{prefix}{log.to_address}",
            "Body": _to_text(log.subject, log.message),
            "StatusCallback": _callback_url(account.name),
        }
        if settings.get("messaging_service_sid"):
            data["MessagingServiceSid"] = settings["messaging_service_sid"]
        elif settings.get("from_number"):
            data["From"] = f"{prefix}{settings['from_number']}"
        else:
            raise ValueError(
                f"Channel Provider Account {account.name} needs from_number or "
                "messaging_service_sid in settings"
            )
        response = requests.post(
            API.format(sid=sid), data=data, auth=(sid, token), timeout=15
        )
        body = response.json()
        if response.status_code >= 400:
            raise RuntimeError(
                f"Twilio send failed ({response.status_code}): {body.get('message')}"
            )
        return body.get("sid")

    def _place_call(self, log, account, settings, sid, token):
        """Outbound Voice (IVR): place a call that reads the message aloud via
        Twilio's text-to-speech (TwiML <Say>). The from number must be
        voice-capable; Messaging Service SIDs don't apply to calls."""
        from_number = settings.get("from_number")
        if not from_number:
            raise ValueError(
                f"Channel Provider Account {account.name} needs a voice-capable "
                "from_number for Voice"
            )
        if log.media_url:
            # Play a recorded audio file (e.g. the director's message) instead
            # of text-to-speech.
            twiml = f"<Response><Play>{frappe.utils.escape_html(log.media_url)}</Play></Response>"
        else:
            text = _to_text(log.subject, log.message) or _("You have a new message.")
            twiml = f"<Response><Say>{frappe.utils.escape_html(text)}</Say></Response>"
        data = {
            "To": log.to_address,
            "From": from_number,
            "Twiml": twiml,
            "StatusCallback": _callback_url(account.name),
        }
        response = requests.post(
            CALLS_API.format(sid=sid), data=data, auth=(sid, token), timeout=15
        )
        body = response.json()
        if response.status_code >= 400:
            raise RuntimeError(
                f"Twilio call failed ({response.status_code}): {body.get('message')}"
            )
        return body.get("sid")

    def verify_webhook(self, account, settings, provided):
        """Validate Twilio's X-Twilio-Signature: base64 HMAC-SHA1, keyed by the
        auth token, over the request URL followed by the POST params sorted by
        key and concatenated as key+value."""
        token = settings.get("auth_token")
        request = getattr(frappe.local, "request", None)
        if not token or request is None:
            return False
        signature = request.headers.get("X-Twilio-Signature")
        if not signature:
            return False
        url = settings.get("public_url") or request.url
        params = request.form.to_dict() if request.form else {}
        payload = url + "".join(k + params[k] for k in sorted(params))
        expected = base64.b64encode(
            hmac.new(token.encode(), payload.encode("utf-8"), hashlib.sha1).digest()
        ).decode()
        return hmac.compare_digest(signature, expected)

    def handle_webhook(self, payload, account):
        from seminary.seminary.comms import _STATUS_ALIASES

        # Voice call status callback (CallSid + CallStatus).
        call_sid = payload.get("CallSid")
        call_status = payload.get("CallStatus")
        if call_sid and call_status:
            mapped = _CALL_STATUS.get(str(call_status).strip().lower())
            if not mapped:
                return None  # queued / ringing / in-progress — not terminal
            return {
                "kind": "status",
                "provider_message_id": call_sid,
                "status": mapped,
            }

        raw_status = payload.get("MessageStatus") or payload.get("SmsStatus")
        sid = payload.get("MessageSid") or payload.get("SmsSid")
        if raw_status and sid:
            status = _STATUS_ALIASES.get(str(raw_status).strip().lower())
            if not status:
                return None  # queued / sending / accepted etc. — not terminal
            return {
                "kind": "status",
                "provider_message_id": sid,
                "status": status,
            }
        from_address = payload.get("From")
        body = payload.get("Body")
        if from_address and body:
            return {
                "kind": "inbound",
                "from_address": _strip_prefix(from_address),
                "body": body,
                "provider_message_id": sid,
            }
        return None


def _strip_prefix(address):
    return address[len("whatsapp:") :] if address.startswith("whatsapp:") else address


def _callback_url(account_name):
    from urllib.parse import quote

    return frappe.utils.get_url(
        f"/api/method/seminary.seminary.comms.webhook?account={quote(account_name)}"
    )
