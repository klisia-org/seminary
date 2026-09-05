# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

"""Turning a postal address into coordinates (ADR 068 §7).

Coordinates are reachability data about a human — the same category as the
address they come from — so they live on the Person, and this module is the one
place that fills them. ADR 067's distance ranking consumes them; it does not
produce them.

Three rules the design rests on:

**Queued on change, never inline.** An intake form must not block on a third
party, and a provider outage must not stop someone saving an address. A failure
leaves the coordinates null, which the ADR 067 readiness pre-flight is built to
surface — a missing datum is a visible gap, not a broken save.

**Once per change, then cached.** Never on read, never on a schedule. A
person's coordinates change only when their address does, and for a hosted
school every call is billed to us.

**Vendor proxy by default.** A small seminary should not have to hold a Google
account to use a distance rule, so the hosted mode points `base_url` at our own
endpoint and carries a site token instead. Google direct is there for a school
that would rather own the key. Nominatim was rejected: its usage policy forbids
this shape of lookup, and self-hosting it means owning the data refresh
forever.
"""

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime, today

from seminary.seminary.integrations import client

SETTINGS = "Address Geocoding Settings"

#: Written on every lookup. Two jobs: an audit trail of which addresses were
#: sent to a third party, and the counter the daily ceiling reads — so the
#: ceiling cannot drift out of step with reality the way a separate tally
#: would.
SERVICE_NAME = "Geocoding"

#: Fields that, when changed, invalidate a Person's coordinates.
ADDRESS_FIELDS = (
    "address_line_1",
    "address_line_2",
    "city",
    "state",
    "pincode",
    "mailing_country",
)

#: What we write back. Kept here so the caller cannot half-fill it.
RESULT_FIELDS = (
    "latitude",
    "longitude",
    "geocoded_on",
    "geocode_precision",
    "geo_status",
)

RESOLVED = "Resolved"
#: The provider knows of no such place. Not retried: asking again costs money
#: and gets the same answer. Clears only when the address changes.
UNRESOLVABLE = "Unresolvable"
#: Network, quota, an outage. Retried by the daily sweeper, because a datum
#: missing for no better reason than "the provider was down that afternoon" is
#: a hole that never closes on its own.
FAILED = "Failed"

#: How many Persons one sweeper run will retry. A ceiling, not a target — the
#: point is to drain a backlog over days rather than spend a month's quota in
#: one night.
SWEEP_BATCH = 50

#: Google answers a bad key, an exhausted quota or a malformed request with
#: HTTP 200 and an empty `results` list — indistinguishable, by shape alone,
#: from "no such place". Verified against the live endpoint: a dummy key
#: returns `{"status": "REQUEST_DENIED", "results": [], "error_message": ...}`.
#: Treating those as no-match would mark every person `Unresolvable`, which is
#: never retried — so a mistyped API key would silently and permanently empty
#: the coordinate column. They are raised instead, which lands them in `Failed`
#: and in the error log.
PROVIDER_FAULTS = {
    "REQUEST_DENIED",
    "OVER_QUERY_LIMIT",
    "OVER_DAILY_LIMIT",
    "INVALID_REQUEST",
    "UNKNOWN_ERROR",
}


class GeocodingError(Exception):
    """The provider refused or failed the request, as opposed to not knowing
    the place."""


def _settings():
    """The one way this module reads its configuration.

    A single accessor so tests can substitute a stand-in instead of writing to
    the live Single — which they used to do, and which overwrote a developer's
    real API key with a test token the moment anything committed mid-test
    (`create_request_log` ends with `frappe.db.commit()`, so that was every
    lookup).
    """
    override = getattr(frappe.local, "_geocoding_settings", None)
    return override or frappe.get_single(SETTINGS)


@contextmanager
def using(settings):
    """Run a lookup against a specific settings document.

    The Test Connection button needs the values on screen, including ones the
    admin has typed but not yet saved — testing the saved configuration when
    someone is trying out a new key would answer the wrong question.
    """
    previous = getattr(frappe.local, "_geocoding_settings", None)
    frappe.local._geocoding_settings = settings
    try:
        yield settings
    finally:
        frappe.local._geocoding_settings = previous


def is_enabled() -> bool:
    return bool(_settings().enabled)


def address_of(person) -> str:
    """The one-line address string handed to the provider."""
    parts = [person.get(f) for f in ADDRESS_FIELDS]
    return ", ".join(p.strip() for p in parts if p and str(p).strip())


def address_changed(doc) -> bool:
    """Did this save alter the address the coordinates were derived from?"""
    before = doc.get_doc_before_save()
    if not before:
        return bool(address_of(doc))
    return any((before.get(f) or "") != (doc.get(f) or "") for f in ADDRESS_FIELDS)


def enqueue_for(person_name: str) -> None:
    """Queue a lookup after the transaction commits.

    `enqueue_after_commit` matters: without it the job can start before the
    address is visible to another connection and geocode the previous value.
    """
    frappe.enqueue(
        "seminary.seminary.integrations.geocoding.geocode_person",
        queue="short",
        enqueue_after_commit=True,
        person_name=person_name,
    )


def geocode_person(person_name: str) -> dict | None:
    """Resolve and store one Person's coordinates. Safe to call twice."""
    if not is_enabled():
        return None
    if not frappe.db.exists("Person", person_name):
        return None

    person = frappe.get_doc("Person", person_name)
    address = address_of(person)
    if not address:
        _clear(person_name, None)
        return None

    try:
        result = lookup(address)
    except Exception:
        # A provider outage must not surface as a failed save, and it must not
        # blank a coordinate we already hold — a stale point is better than no
        # point for a distance ranking, and the pre-flight reports staleness.
        frappe.log_error(frappe.get_traceback(), "geocoding: %s" % person_name)
        _mark(person_name, FAILED)
        return None

    if not result:
        _clear(person_name, UNRESOLVABLE)
        return None

    frappe.db.set_value(
        "Person",
        person_name,
        {
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "geocode_precision": result.get("precision"),
            "geocoded_on": now_datetime(),
            "geo_status": RESOLVED,
        },
        update_modified=False,
    )
    return result


#: Places API (New) hosts autocomplete and place details on its own domain,
#: separate from the Geocoding API's `maps.googleapis.com`.
PLACES_BASE_URL = "https://places.googleapis.com"

#: Places API (New) requires an explicit field mask — omitting it is an error,
#: not a default — and you are billed for the fields you ask for. Ask for the
#: minimum: an id and a label to show, then the components and the point.
AUTOCOMPLETE_MASK = (
    "suggestions.placePrediction.placeId,suggestions.placePrediction.text"
)
DETAILS_MASK = "addressComponents,location,formattedAddress"


def _places_call(path, body=None, mask=AUTOCOMPLETE_MASK):
    """One Places API (New) request, through whichever provider is configured.

    Vendor proxy is not an afterthought here: the reason autocomplete is
    proxied through this server at all is that the browser widget would have
    put a Places key in page source, and a hosted school holds no Google
    account to put there. Same switch, same key, same audit log as the
    geocoder.
    """
    settings = _settings()
    if not settings.enabled:
        return None
    key = settings.get_password("api_key", raise_exception=False)
    if not key:
        frappe.throw(_("Address Geocoding Settings is missing a server API key."))

    if settings.provider == "Vendor proxy":
        base_url = settings.base_url
        headers = {"Authorization": "Bearer %s" % key, "X-Goog-FieldMask": mask}
    else:
        base_url = PLACES_BASE_URL
        headers = {"X-Goog-Api-Key": key, "X-Goog-FieldMask": mask}

    return client.post(base_url, path, body=body, headers=headers)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60, ip_based=True)
def suggest_addresses(text: str, session_token: str = None) -> list[dict]:
    """Address predictions for a partly-typed address.

    Guest-callable because the public application form is the surface where a
    badly typed address does the most damage — and the applicant is never
    logged in. That makes it a billable endpoint open to the internet, so it is
    rate limited per IP on top of the daily ceiling: 60 a minute is far more
    than a human types and far less than a loop costs.

    Server-side on purpose. The Places JS widget would have worked with less
    code, but it requires the API key in page source — and `Vendor proxy`
    exists precisely so a hosted school holds no Google account, so there would
    have been no key of theirs to expose and no honest way to expose ours.

    `session_token` groups the keystrokes and the `resolve_address` call that
    follows into one billable session; without it every keystroke is charged
    separately.
    """
    text = (text or "").strip()
    if len(text) < 3 or not is_enabled():
        return []

    body = {"input": text}
    if session_token:
        body["sessionToken"] = session_token
    try:
        payload = _places_call("/v1/places:autocomplete", body)
    except Exception:
        # A typeahead that raises is worse than one that returns nothing: the
        # field is still typeable, and the address still saves.
        frappe.log_error(frappe.get_traceback(), "geocoding: autocomplete")
        return []

    out = []
    for suggestion in (payload or {}).get("suggestions") or []:
        prediction = suggestion.get("placePrediction") or {}
        label = (prediction.get("text") or {}).get("text")
        if prediction.get("placeId") and label:
            out.append({"place_id": prediction["placeId"], "label": label})
    return out


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=30, seconds=60, ip_based=True)
def resolve_address(place_id: str, session_token: str = None) -> dict | None:
    """The structured address and coordinates behind a chosen prediction.

    Guest-callable and rate limited for the same reason as `suggest_addresses`:
    the applicant form needs it, and a Place Details call is the more expensive
    half of a session.

    Returns the point as well as the components, so an address picked from the
    typeahead needs no separate Geocoding call afterwards — it arrives already
    located, and already spelled the way the provider spells it, which is what
    stops it coming back `Unresolvable` later.
    """
    if not place_id or not is_enabled():
        return None
    path = "/v1/places/%s" % place_id
    params = {"sessionToken": session_token} if session_token else None
    try:
        settings = _settings()
        key = settings.get_password("api_key", raise_exception=False)
        if settings.provider == "Vendor proxy":
            payload = client.get(
                settings.base_url,
                path,
                auth_header="Authorization",
                auth_value="Bearer %s" % key,
                params=params,
            )
        else:
            payload = client.get(
                PLACES_BASE_URL,
                path,
                auth_header="X-Goog-Api-Key",
                auth_value=key,
                params=dict(params or {}, fields=DETAILS_MASK),
            )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "geocoding: place details")
        return None

    return _shape_place(payload)


#: Google address component type -> (our field, which of longText/shortText).
#: `shortText` for the state because an address line wants "PE", not
#: "Pernambuco".
COMPONENT_MAP = {
    "street_number": ("_street_number", "longText"),
    "route": ("_route", "longText"),
    "subpremise": ("address_line_2", "longText"),
    "locality": ("city", "longText"),
    "postal_town": ("city", "longText"),
    "administrative_area_level_2": ("_city_fallback", "longText"),
    "administrative_area_level_1": ("state", "shortText"),
    "postal_code": ("pincode", "longText"),
    "country": ("country", "longText"),
}


def _shape_place(payload) -> dict | None:
    if not isinstance(payload, dict):
        return None
    out = {}
    for component in payload.get("addressComponents") or []:
        for kind in component.get("types") or []:
            rule = COMPONENT_MAP.get(kind)
            if rule and rule[0] not in out:
                out[rule[0]] = component.get(rule[1])

    # Google splits the street across two components; an address line wants it
    # whole.
    out["address_line_1"] = " ".join(
        p for p in (out.pop("_street_number", None), out.pop("_route", None)) if p
    )
    out.setdefault("city", out.pop("_city_fallback", None))
    out.pop("_city_fallback", None)

    location = payload.get("location") or {}
    if location.get("latitude") is not None:
        out["latitude"] = location["latitude"]
        out["longitude"] = location["longitude"]
        # A place chosen from the typeahead is as precise as the provider gets.
        out["precision"] = "PLACES"
    out["formatted_address"] = payload.get("formattedAddress")
    return out


@frappe.whitelist()
def geocode_now(person: str) -> dict:
    """Look one Person up on demand, from the form's Location button.

    Synchronous on purpose, unlike the save-time path: a person clicked a
    button and is waiting for an answer, so silence would be the wrong
    behaviour here even though it is the right one during an intake save.
    """
    frappe.has_permission("Person", "write", doc=person, throw=True)
    if not is_enabled():
        return {"ok": False, "message": _("Geocoding is not enabled.")}

    result = geocode_person(person)
    if result:
        return {"ok": True, **result}

    status = frappe.db.get_value("Person", person, "geo_status")
    if status == UNRESOLVABLE:
        message = _("The provider knows of no such address.")
    elif status == FAILED:
        message = _("The provider could not be reached. It will be retried.")
    else:
        message = _("There is no mailing address to look up.")
    return {"ok": False, "message": message}


def has_coordinates(person) -> bool:
    """Whether this Person has a usable point.

    `geo_status`, not latitude, is the presence signal. Frappe's Float columns
    are NOT NULL DEFAULT 0, so an unresolved coordinate reads as `0.0, 0.0` —
    which is a real place in the Gulf of Guinea, and a distance ranking that
    quietly treated it as "unknown" would be guessing.
    """
    if isinstance(person, str):
        person = frappe.db.get_value("Person", person, ["geo_status"], as_dict=True)
    return bool(person and person.get("geo_status") == RESOLVED)


def _clear(person_name: str, status) -> None:
    """No address, or no such place: say so rather than leaving a stale point.

    The coordinates go to 0 because the column cannot hold NULL; `geo_status`
    is what records the outcome, and stamping `geocoded_on` distinguishes "we
    looked and found nothing" from "never looked".
    """
    frappe.db.set_value(
        "Person",
        person_name,
        {
            "latitude": 0,
            "longitude": 0,
            "geocode_precision": None,
            "geocoded_on": now_datetime(),
            "geo_status": status,
        },
        update_modified=False,
    )


def _mark(person_name: str, status) -> None:
    """Record an outcome without touching a point we already hold.

    A stale coordinate beats none for a ranking, so an outage must not blank
    one — it only says the last attempt failed, which is what the sweeper and
    the ADR 067 readiness pre-flight read.
    """
    frappe.db.set_value(
        "Person",
        person_name,
        {"geocoded_on": now_datetime(), "geo_status": status},
        update_modified=False,
    )


def retry_failed_geocodes():
    """Daily: retry the lookups that failed for reasons that pass.

    Only `Failed` — an outage, a quota ceiling, a timeout. `Unresolvable` is
    left alone because asking again costs money and gets the same answer, and
    it clears by itself when someone corrects the address.
    """
    if not is_enabled():
        return
    names = frappe.get_all(
        "Person",
        filters={"geo_status": FAILED},
        pluck="name",
        limit=SWEEP_BATCH,
        order_by="geocoded_on asc",
    )
    for name in names:
        geocode_person(name)


def lookup(address: str) -> dict | None:
    """Ask the configured provider for one address. Returns None on no match."""
    settings = _settings()
    if not settings.enabled:
        return None
    _assert_within_daily_limit(settings)

    key = settings.get_password("api_key", raise_exception=False)
    if not key:
        frappe.throw(_("Address Geocoding Settings is missing a server API key."))

    if settings.provider == "Vendor proxy":
        # Our endpoint takes a site token and speaks the same response shape,
        # so the school configures nothing and we hold the upstream key.
        payload = client.get(
            settings.base_url,
            "/geocode",
            auth_header="Authorization",
            auth_value="Bearer %s" % key,
            params={"address": address},
        )
    else:
        # Google authenticates by query parameter, not by header — verified
        # against the live endpoint.
        payload = client.get(
            settings.base_url,
            "/maps/api/geocode/json",
            params={"address": address, "key": key},
        )

    try:
        _assert_provider_ok(payload)
    except GeocodingError as exc:
        _log_request(address, "Failed", error=str(exc))
        raise
    result = _shape(payload)
    _log_request(address, "Completed", output=payload.get("status"))
    return result


def _log_request(address: str, status: str, output=None, error=None) -> None:
    """Record the call as an Integration Request.

    `client.get` does not do this — `make_get_request` sets a flag and creates
    no record, despite what its wrapper's docstring used to say. Writing it
    here is what makes the daily ceiling countable and gives the school an
    auditable list of the addresses that left the building.
    """
    from frappe.integrations.utils import create_request_log

    try:
        create_request_log(
            {"address": address},
            service_name=SERVICE_NAME,
            is_remote_request=1,
            status=status,
            output=output,
            error=error,
        )
    except Exception:
        # An audit trail that breaks the thing it audits is worse than none.
        frappe.log_error(frappe.get_traceback(), "geocoding: request log")


def _assert_provider_ok(payload) -> None:
    """Separate "I will not answer" from "there is no such place"."""
    if not isinstance(payload, dict):
        return
    status = payload.get("status")
    if status in PROVIDER_FAULTS:
        raise GeocodingError(
            "%s: %s" % (status, payload.get("error_message") or "no detail given")
        )


def _shape(payload) -> dict | None:
    """Both modes answer in Google's shape; normalise to ours."""
    if not isinstance(payload, dict):
        return None
    if payload.get("status") not in (None, "OK"):
        return None
    results = payload.get("results") or []
    if not results:
        return None
    top = results[0]
    location = (top.get("geometry") or {}).get("location") or {}
    if location.get("lat") is None or location.get("lng") is None:
        return None
    return {
        "latitude": location["lat"],
        "longitude": location["lng"],
        # "ROOFTOP" and "APPROXIMATE" are not the same answer, and a distance
        # ranking built on a city centroid is noise. Store what we got so the
        # readiness check can say so — and never leave it empty on a real
        # match, because `has_coordinates` reads it as the presence signal.
        "precision": (top.get("geometry") or {}).get("location_type") or "UNKNOWN",
    }


def _assert_within_daily_limit(settings) -> None:
    """Stop a runaway loop before it spends money.

    Counted from the Integration Request rows `_log_request` writes, so the
    ceiling reads the same record the audit trail does and cannot drift out of
    step with a tally of its own.
    """
    limit = settings.daily_limit or 0
    if limit <= 0:
        return
    used = frappe.db.count(
        "Integration Request",
        {
            "integration_request_service": SERVICE_NAME,
            "creation": (">=", today()),
        },
    )
    if used >= limit:
        frappe.throw(_("Geocoding daily limit of {0} lookups reached.").format(limit))
