# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Geocoding the spine (ADR 068 §7).

Coordinates are resolved from the postal address, queued on change and cached.
Nothing here talks to a provider: the HTTP call is patched out, because what
needs pinning is *when* a lookup happens and what a failure does — not whether
Google is up.

Outside the doctype folder deliberately, like `test_cohort_policy.py`: a module
in a doctype directory loads that doctype's test-record dependencies, and
Person's link graph reaches erpnext's `Company` several ways over.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import person_fields as registry
from seminary.seminary.integrations import geocoding
from seminary.seminary.tests.cohort_fixtures import make_person

GOOGLE_OK = {
    "status": "OK",
    "results": [
        {
            "geometry": {
                "location": {"lat": -8.0476, "lng": -34.877},
                "location_type": "ROOFTOP",
            }
        }
    ],
}


class FakeSettings:
    """Stand-in for the Address Geocoding Settings single.

    These tests used to configure the real Single. That was wrong twice over:
    `create_request_log` commits, so a per-class rollback could not undo it —
    and the class then wrote `zzt-token` over a developer's actual Google key
    and left `base_url` pointing at `example.test`. Both happened. Nothing here
    touches the database now.
    """

    def __init__(self, **overrides):
        self.enabled = overrides.get("enabled", 1)
        self.provider = overrides.get("provider", "Vendor proxy")
        self.base_url = overrides.get("base_url", "https://example.test")
        self.daily_limit = overrides.get("daily_limit", 0)
        self._key = overrides.get("api_key", "zzt-token")

    def get_password(self, fieldname, raise_exception=True):
        return self._key


class GeocodingTestCase(IntegrationTestCase):
    """Runs against a stand-in configuration, never the site's own."""

    def enable(self, **overrides):
        settings = FakeSettings(**overrides)
        ctx = geocoding.using(settings)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        return settings

    def setUp(self):
        super().setUp()
        # Disabled unless a test asks otherwise, so "does nothing when off" is
        # tested against a known state rather than whatever ran before.
        self.enable(enabled=0)
        # `create_request_log` ends with `frappe.db.commit()`, which would
        # commit the fixtures too — 58 test Persons reached a developer's site
        # that way. The logging itself is asserted against this mock.
        logger = patch.object(geocoding, "_log_request")
        self.logged = logger.start()
        self.addCleanup(logger.stop)


def _address(person, **values):
    person.reload()
    person.update(
        {
            "address_line_1": values.get("address_line_1", "12 Rua Teste"),
            "city": values.get("city", "Recife"),
            "state": values.get("state", "PE"),
            "pincode": values.get("pincode", "50000-000"),
        }
    )
    person.save(ignore_permissions=True)
    return person


class TestWhenALookupHappens(GeocodingTestCase):
    def test_an_address_change_queues_exactly_one_lookup(self):
        self.enable()
        person = make_person("Geo")
        with patch.object(geocoding, "enqueue_for") as queued:
            _address(person)
        queued.assert_called_once_with(person.name)

    def test_a_change_that_is_not_the_address_queues_nothing(self):
        """Every Person save would otherwise spend money on an unchanged
        address — and for a hosted school the bill is ours."""
        self.enable()
        person = _address(make_person("GeoQuiet"))
        with patch.object(geocoding, "enqueue_for") as queued:
            person.reload()
            person.web_bio = "changed something unrelated"
            person.save(ignore_permissions=True)
        queued.assert_not_called()

    def test_nothing_is_queued_while_the_integration_is_off(self):
        person = make_person("GeoOff")
        with patch.object(geocoding, "enqueue_for") as queued:
            _address(person)
        queued.assert_not_called()

    def test_the_address_string_skips_blanks(self):
        person = make_person("GeoJoin")
        person.address_line_1 = "12 Rua Teste"
        person.address_line_2 = None
        person.city = "Recife"
        self.assertNotIn(", ,", geocoding.address_of(person))
        self.assertIn("12 Rua Teste", geocoding.address_of(person))


class TestStoringTheResult(GeocodingTestCase):
    def test_a_match_is_stored_with_its_precision(self):
        self.enable()
        person = _address(make_person("GeoStore"))
        with patch.object(geocoding.client, "get", return_value=GOOGLE_OK):
            geocoding.geocode_person(person.name)

        row = frappe.db.get_value(
            "Person",
            person.name,
            ["latitude", "longitude", "geocode_precision", "geocoded_on"],
            as_dict=True,
        )
        self.assertAlmostEqual(row.latitude, -8.0476, places=4)
        self.assertAlmostEqual(row.longitude, -34.877, places=3)
        # A rooftop and a city centroid are not the same answer, and a distance
        # ranking built on the latter is noise.
        self.assertEqual(row.geocode_precision, "ROOFTOP")
        self.assertTrue(row.geocoded_on)

    def test_a_provider_failure_leaves_the_previous_point_alone(self):
        """A stale coordinate beats none for a ranking, and the status is what
        reports that the last attempt did not land."""
        self.enable()
        person = _address(make_person("GeoFail"))
        with patch.object(geocoding.client, "get", return_value=GOOGLE_OK):
            geocoding.geocode_person(person.name)

        with patch.object(geocoding.client, "get", side_effect=OSError("boom")):
            geocoding.geocode_person(person.name)

        self.assertAlmostEqual(
            frappe.db.get_value("Person", person.name, "latitude"), -8.0476, places=4
        )
        self.assertEqual(
            frappe.db.get_value("Person", person.name, "geo_status"), geocoding.FAILED
        )

    def test_the_sweeper_retries_a_failure_but_not_an_unresolvable(self):
        """A datum missing because the provider was down one afternoon is a
        hole that never closes on its own. One that is missing because no such
        place exists costs money to re-ask and gets the same answer."""
        self.enable()
        failed = _address(make_person("GeoSweepFail"))
        gone = _address(make_person("GeoSweepGone"))
        with patch.object(geocoding.client, "get", side_effect=OSError("boom")):
            geocoding.geocode_person(failed.name)
        with patch.object(
            geocoding.client,
            "get",
            return_value={"status": "ZERO_RESULTS", "results": []},
        ):
            geocoding.geocode_person(gone.name)

        with patch.object(geocoding, "geocode_person") as retried:
            geocoding.retry_failed_geocodes()
        attempted = {call.args[0] for call in retried.call_args_list}
        self.assertIn(failed.name, attempted)
        self.assertNotIn(gone.name, attempted)

    def test_no_match_clears_rather_than_leaving_a_wrong_point(self):
        self.enable()
        person = _address(make_person("GeoNoMatch"))
        with patch.object(geocoding.client, "get", return_value=GOOGLE_OK):
            geocoding.geocode_person(person.name)
        self.assertTrue(geocoding.has_coordinates(person.name))

        with patch.object(
            geocoding.client,
            "get",
            return_value={"status": "ZERO_RESULTS", "results": []},
        ):
            geocoding.geocode_person(person.name)

        # Frappe's Float columns cannot hold NULL, so the coordinates read as
        # 0.0 — which is a real place. `geocode_precision` is what says whether
        # the point means anything.
        self.assertFalse(geocoding.has_coordinates(person.name))
        row = frappe.db.get_value(
            "Person", person.name, ["geocoded_on", "geo_status"], as_dict=True
        )
        self.assertTrue(row.geocoded_on, "we looked; that is different from never")
        self.assertEqual(row.geo_status, geocoding.UNRESOLVABLE)

    def test_a_person_with_no_address_is_not_looked_up(self):
        self.enable()
        person = make_person("GeoNoAddress")
        with patch.object(geocoding.client, "get") as called:
            geocoding.geocode_person(person.name)
        called.assert_not_called()

    def test_a_disabled_integration_stores_nothing(self):
        person = _address(make_person("GeoDisabled"))
        with patch.object(geocoding.client, "get", return_value=GOOGLE_OK) as called:
            geocoding.geocode_person(person.name)
        called.assert_not_called()
        self.assertFalse(geocoding.has_coordinates(person.name))


#: Captured verbatim from the live endpoint on 2026-09-04 by calling
#: `maps.googleapis.com/maps/api/geocode/json?address=...&key=<invalid>`.
#: Note the HTTP status is **200** and `results` is empty — by shape alone this
#: is indistinguishable from "no such place", which is exactly the trap.
GOOGLE_BAD_KEY = {
    "error_message": "The provided API key is invalid. ",
    "results": [],
    "status": "REQUEST_DENIED",
}


class TestProviderFaultsAreNotNoMatches(GeocodingTestCase):
    """A refused request is not an unknown address.

    `Unresolvable` is never retried, so folding a bad key into it would empty
    the coordinate column permanently and silently — the daily sweeper would
    skip every affected person forever.
    """

    def test_a_rejected_key_is_a_failure_not_an_unresolvable_address(self):
        self.enable()
        person = _address(make_person("GeoBadKey"))
        with patch.object(geocoding.client, "get", return_value=GOOGLE_BAD_KEY):
            geocoding.geocode_person(person.name)

        self.assertEqual(
            frappe.db.get_value("Person", person.name, "geo_status"),
            geocoding.FAILED,
            "a bad API key was recorded as 'no such place' and will never retry",
        )

    def test_every_provider_fault_raises_rather_than_returning_nothing(self):
        for status in geocoding.PROVIDER_FAULTS:
            with self.subTest(status=status):
                with self.assertRaises(geocoding.GeocodingError):
                    geocoding._assert_provider_ok({"status": status, "results": []})

    def test_zero_results_is_still_an_honest_no_match(self):
        geocoding._assert_provider_ok({"status": "ZERO_RESULTS", "results": []})
        self.assertIsNone(geocoding._shape({"status": "ZERO_RESULTS", "results": []}))

    def test_the_error_message_reaches_the_log(self):
        with self.assertRaisesRegex(geocoding.GeocodingError, "API key is invalid"):
            geocoding._assert_provider_ok(GOOGLE_BAD_KEY)


def _unsaved_settings(**overrides):
    """An in-memory settings document for the doc-method tests.

    `frappe.get_single` would hand back the site's own row, and mutating it is
    how a real API key got overwritten with a test token.
    """
    doc = frappe.new_doc("Address Geocoding Settings")
    doc.enabled = overrides.get("enabled", 1)
    doc.provider = overrides.get("provider", "Vendor proxy")
    doc.base_url = overrides.get("base_url", "https://example.test")
    doc.daily_limit = overrides.get("daily_limit", 0)
    doc.api_key = overrides.get("api_key", "zzt-token")
    return doc


class TestTheSupportAffordances(GeocodingTestCase):
    """The button and the widget exist to make a silent failure visible.

    Lookups are queued and their failures deliberately do not surface at save
    time, so without these a misconfigured key looks exactly like "nobody has
    an address yet" — and arrives as a support ticket instead.
    """

    def test_test_connection_reports_the_providers_own_refusal(self):
        self.enable()
        settings = _unsaved_settings()
        with patch.object(geocoding.client, "get", return_value=GOOGLE_BAD_KEY):
            result = settings.test_connection()
        self.assertFalse(result["ok"])
        self.assertIn("API key is invalid", result["message"])

    def test_test_connection_reports_a_success_with_coordinates(self):
        self.enable()
        settings = _unsaved_settings()
        with patch.object(geocoding.client, "get", return_value=GOOGLE_OK):
            result = settings.test_connection()
        self.assertTrue(result["ok"])
        self.assertEqual(result["precision"], "ROOFTOP")
        self.assertIn("Pennsylvania", result["address"])

    def test_test_connection_says_so_when_disabled(self):
        settings = _unsaved_settings(enabled=0)
        result = settings.test_connection()
        self.assertFalse(result["ok"])
        self.assertIn("not enabled", result["message"])

    def test_an_endpoint_that_is_not_a_geocoder_is_named_as_such(self):
        """A vendor-proxy URL pointed at the wrong service answers 200 with
        nothing useful; "no match" for a landmark address is the tell."""
        self.enable()
        settings = _unsaved_settings()
        with patch.object(geocoding.client, "get", return_value={"results": []}):
            result = settings.test_connection()
        self.assertFalse(result["ok"])
        self.assertIn("not a geocoding service", result["message"])

    def test_geocode_now_returns_the_reason_it_could_not(self):
        self.enable()
        person = _address(make_person("GeoOnDemand"))
        with patch.object(
            geocoding.client,
            "get",
            return_value={"status": "ZERO_RESULTS", "results": []},
        ):
            result = geocoding.geocode_now(person.name)
        self.assertFalse(result["ok"])
        self.assertIn("no such address", result["message"])

    def test_every_lookup_is_recorded_for_audit(self):
        """Two jobs: an auditable list of the addresses that left the building,
        and the counter the daily ceiling reads."""
        self.enable()
        with patch.object(geocoding.client, "get", return_value=GOOGLE_OK):
            geocoding.lookup("somewhere")
        self.logged.assert_called_once()
        self.assertEqual(self.logged.call_args.args[1], "Completed")

        self.logged.reset_mock()
        with patch.object(geocoding.client, "get", return_value=GOOGLE_BAD_KEY):
            with self.assertRaises(geocoding.GeocodingError):
                geocoding.lookup("somewhere")
        self.assertEqual(self.logged.call_args.args[1], "Failed")

    def test_geocode_now_returns_the_point_on_success(self):
        self.enable()
        person = _address(make_person("GeoOnDemandOk"))
        with patch.object(geocoding.client, "get", return_value=GOOGLE_OK):
            result = geocoding.geocode_now(person.name)
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["latitude"], -8.0476, places=4)


AUTOCOMPLETE_OK = {
    "suggestions": [
        {
            "placePrediction": {
                "placeId": "PID-1",
                "text": {"text": "12 Rua Teste, Recife"},
            }
        },
        {
            "placePrediction": {
                "placeId": "PID-2",
                "text": {"text": "12 Rua Teste, Olinda"},
            }
        },
    ]
}

PLACE_DETAILS_OK = {
    "formattedAddress": "12 Rua Teste, Recife - PE, 50000-000, Brazil",
    "location": {"latitude": -8.0476, "longitude": -34.877},
    "addressComponents": [
        {"longText": "12", "shortText": "12", "types": ["street_number"]},
        {"longText": "Rua Teste", "shortText": "Rua Teste", "types": ["route"]},
        {"longText": "Recife", "shortText": "Recife", "types": ["locality"]},
        {
            "longText": "Pernambuco",
            "shortText": "PE",
            "types": ["administrative_area_level_1"],
        },
        {"longText": "50000-000", "shortText": "50000-000", "types": ["postal_code"]},
        {"longText": "Brazil", "shortText": "BR", "types": ["country"]},
    ],
}


class TestAutocompleteIsProxied(GeocodingTestCase):
    """No API key may reach a browser.

    The obvious build — Google's `PlaceAutocompleteElement` — needs the key in
    page source. That is Google's model, but it cannot work here: `Vendor proxy`
    exists so a hosted school holds no Google account, so there is no key of
    theirs to expose and no honest way to expose ours.
    """

    def test_the_endpoints_are_reachable_by_a_guest(self):
        """The public application form is the surface that matters most, and an
        applicant is never logged in."""
        for fn in (geocoding.suggest_addresses, geocoding.resolve_address):
            with self.subTest(fn=fn.__name__):
                self.assertIn(fn, frappe.guest_methods)

    def test_the_billable_endpoints_are_rate_limited(self):
        """Guest-callable and billable is an expensive combination to leave
        open; the per-IP limit sits on top of the daily ceiling."""
        for fn in (geocoding.suggest_addresses, geocoding.resolve_address):
            with self.subTest(fn=fn.__name__):
                self.assertTrue(
                    getattr(fn, "__wrapped__", None),
                    "%s is not wrapped by a rate limiter" % fn.__name__,
                )

    def test_no_endpoint_hands_out_a_key(self):
        self.assertFalse(
            hasattr(geocoding, "autocomplete_config"),
            "the browser-key endpoint is gone; autocomplete is proxied",
        )
        self.assertFalse(
            frappe.get_meta("Address Geocoding Settings").get_field("browser_api_key"),
            "a browser key field invites putting a key in page source",
        )

    def test_suggestions_are_returned_as_id_and_label(self):
        self.enable()
        with patch.object(geocoding.client, "post", return_value=AUTOCOMPLETE_OK):
            out = geocoding.suggest_addresses("12 Rua Teste")
        self.assertEqual(
            out,
            [
                {"place_id": "PID-1", "label": "12 Rua Teste, Recife"},
                {"place_id": "PID-2", "label": "12 Rua Teste, Olinda"},
            ],
        )

    def test_a_short_query_never_reaches_the_provider(self):
        """Every keystroke would otherwise be billable."""
        self.enable()
        with patch.object(geocoding.client, "post") as called:
            self.assertEqual(geocoding.suggest_addresses("12"), [])
        called.assert_not_called()

    def test_the_session_token_is_passed_through(self):
        """It groups the keystrokes and the details call into one billable
        session; without it each keystroke is charged separately."""
        self.enable()
        with patch.object(
            geocoding.client, "post", return_value=AUTOCOMPLETE_OK
        ) as call:
            # nosec B106 — a Places session token groups requests for billing;
            # it is not a credential.
            geocoding.suggest_addresses(
                "12 Rua Teste", session_token="tok-1"
            )  # nosec B106
        self.assertEqual(call.call_args.kwargs["body"]["sessionToken"], "tok-1")

    def test_a_provider_failure_returns_no_suggestions_rather_than_raising(self):
        """A typeahead that raises breaks a form the user could otherwise still
        type into by hand."""
        self.enable()
        with patch.object(geocoding.client, "post", side_effect=OSError("boom")):
            with patch.object(frappe, "log_error"):
                self.assertEqual(geocoding.suggest_addresses("12 Rua Teste"), [])

    def test_nothing_is_suggested_while_disabled(self):
        with patch.object(geocoding.client, "post") as called:
            self.assertEqual(geocoding.suggest_addresses("12 Rua Teste"), [])
        called.assert_not_called()

    def test_the_field_mask_is_sent(self):
        """Places API (New) errors without one, and bills for what it names."""
        self.enable()
        with patch.object(
            geocoding.client, "post", return_value=AUTOCOMPLETE_OK
        ) as call:
            geocoding.suggest_addresses("12 Rua Teste")
        self.assertIn("X-Goog-FieldMask", call.call_args.kwargs["headers"])

    def test_google_mode_sends_the_key_as_a_header_not_a_query(self):
        self.enable(provider="Google", api_key="server-key")  # pragma: allowlist secret
        with patch.object(
            geocoding.client, "post", return_value=AUTOCOMPLETE_OK
        ) as call:
            geocoding.suggest_addresses("12 Rua Teste")
        headers = call.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Goog-Api-Key"], "server-key")
        self.assertEqual(call.call_args.args[0], geocoding.PLACES_BASE_URL)

    def test_vendor_proxy_sends_the_site_token_to_our_endpoint(self):
        self.enable(
            provider="Vendor proxy",
            base_url="https://host.test",
            api_key="site-token",  # pragma: allowlist secret
        )
        with patch.object(
            geocoding.client, "post", return_value=AUTOCOMPLETE_OK
        ) as call:
            geocoding.suggest_addresses("12 Rua Teste")
        self.assertEqual(call.call_args.args[0], "https://host.test")
        self.assertEqual(
            call.call_args.kwargs["headers"]["Authorization"], "Bearer site-token"
        )


class TestResolvingAChosenAddress(GeocodingTestCase):
    def test_the_components_are_unpacked_into_our_fields(self):
        self.enable()
        with patch.object(geocoding.client, "get", return_value=PLACE_DETAILS_OK):
            # nosec B106 — see above: a billing session id, not a secret.
            out = geocoding.resolve_address(
                "PID-1", session_token="tok-1"
            )  # nosec B106
        self.assertEqual(out["address_line_1"], "12 Rua Teste")
        self.assertEqual(out["city"], "Recife")
        # An address line wants "PE", not "Pernambuco".
        self.assertEqual(out["state"], "PE")
        self.assertEqual(out["pincode"], "50000-000")
        self.assertEqual(out["country"], "Brazil")

    def test_it_arrives_already_located(self):
        """The point comes back with the address, so an autocompleted address
        needs no separate Geocoding call at all."""
        self.enable()
        with patch.object(geocoding.client, "get", return_value=PLACE_DETAILS_OK):
            out = geocoding.resolve_address("PID-1")
        self.assertAlmostEqual(out["latitude"], -8.0476, places=4)
        self.assertAlmostEqual(out["longitude"], -34.877, places=3)
        self.assertTrue(out["precision"])

    def test_a_failure_returns_nothing_rather_than_raising(self):
        self.enable()
        with patch.object(geocoding.client, "get", side_effect=OSError("boom")):
            with patch.object(frappe, "log_error"):
                self.assertIsNone(geocoding.resolve_address("PID-1"))


class TestPayloadShaping(IntegrationTestCase):
    def test_a_malformed_payload_is_not_a_coordinate(self):
        for payload in (None, "", [], {}, {"status": "OK"}, {"results": [{}]}):
            with self.subTest(payload=payload):
                self.assertIsNone(geocoding._shape(payload))

    def test_a_missing_longitude_is_rejected(self):
        payload = {
            "status": "OK",
            "results": [{"geometry": {"location": {"lat": 1.0}}}],
        }
        self.assertIsNone(geocoding._shape(payload))


class TestCoordinatesAreDerived(IntegrationTestCase):
    def test_they_are_declared_derived_and_sensitive(self):
        for field in ("latitude", "longitude"):
            spec = registry.SPEC_BY_PERSON_FIELD[field]
            with self.subTest(field=field):
                self.assertTrue(spec.derived)
                self.assertTrue(spec.sensitive)
                # Nobody types a latitude, so there is no spine keyword for it
                # and "mandatory" can only mean resolvable.
                self.assertFalse(spec.settable)

    def test_they_are_held_at_permlevel_one(self):
        meta = frappe.get_meta("Person")
        for field in (
            "latitude",
            "longitude",
            "geocoded_on",
            "geocode_precision",
            "geo_status",
        ):
            with self.subTest(field=field):
                self.assertEqual(meta.get_field(field).permlevel, 1)


class TestSettingsRefuseAHalfConfiguration(GeocodingTestCase):
    def test_enabling_without_a_key_is_refused(self):
        """It would otherwise fail silently forever: lookups leave coordinates
        null by design, so a missing key looks exactly like 'nobody has an
        address yet'.

        The stored password is removed explicitly rather than assigned `""`:
        Frappe treats an empty Password field as "unchanged" and keeps the
        value already on file, so the naive version of this test passes on a
        fresh site and quietly stops testing anything once a key exists.
        """
        from frappe.utils.password import remove_encrypted_password

        remove_encrypted_password(
            "Address Geocoding Settings", "Address Geocoding Settings", "api_key"
        )
        settings = _unsaved_settings()
        settings.enabled = 1
        settings.base_url = "https://example.test"
        settings.api_key = ""
        with self.assertRaisesRegex(frappe.ValidationError, "API key"):
            settings.save(ignore_permissions=True)
