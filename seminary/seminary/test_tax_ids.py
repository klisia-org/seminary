# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt

"""Per-country tax identifiers (ADR 071).

The registry class is where the "adding a country is one entry" claim is
actually checked: every rule has to be internally consistent, and the contract
handed to the browser has to stay free of the arithmetic it deliberately does
not carry.
"""

import json
import re

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from seminary.seminary import person as spine
from seminary.seminary import tax_ids
from seminary.seminary.tests.cohort_fixtures import make_person
from seminary.seminary.tax_ids import (
    BOTH,
    ORGANIZATION,
    PERSON,
    Form,
    Rule,
    assert_tax_id,
    clean_tax_id,
    client_rule,
    format_tax_id,
    problem_with,
)

VALID_CPF = "111.444.777-35"
VALID_CNPJ = "11.222.333/0001-81"


class UnitTestTaxIdRegistry(UnitTestCase):
    """Every rule must be true about itself, whoever wrote it."""

    def test_every_rule_is_keyed_by_an_uppercase_alpha_2_code(self):
        for rule in tax_ids.RULES:
            self.assertRegex(rule.country, r"^[A-Z]{2}$", msg=rule.country)

    def test_no_country_is_declared_twice(self):
        self.assertEqual(len(tax_ids.RULES), len(tax_ids.RULES_BY_COUNTRY))

    def test_every_pattern_compiles_and_is_anchored(self):
        # An unanchored pattern handed to `new RegExp` matches a substring, so
        # the browser would accept values the server refuses.
        for rule in tax_ids.RULES:
            for form in rule.forms:
                re.compile(form.pattern)
                self.assertTrue(form.pattern.startswith("^"), msg=form.name)
                self.assertTrue(form.pattern.endswith("$"), msg=form.name)

    def test_every_example_passes_its_own_form(self):
        """The specimen in the error message must itself be valid.

        Nothing else stops a new country shipping a message that tells the
        user to type something the same rule would refuse.
        """
        for rule in tax_ids.RULES:
            for form in rule.forms:
                cleaned = tax_ids.strip(form.example, rule)
                self.assertRegex(cleaned, form.pattern, msg=form.name)
                if form.checksum:
                    self.assertTrue(form.checksum(cleaned), msg=form.name)

    def test_every_mask_has_one_placeholder_per_accepted_character(self):
        for rule in tax_ids.RULES:
            for form in rule.forms:
                if not (form.mask and form.example):
                    continue
                self.assertEqual(
                    form.mask.count("#"),
                    len(tax_ids.strip(form.example, rule)),
                    msg=form.name,
                )

    def test_the_client_contract_carries_no_algorithm(self):
        """The line the whole design rests on: shape crosses to the browser,
        arithmetic does not."""
        contract = client_rule("BR")
        json.dumps(contract)  # serialisable at all
        for form in contract["forms"]:
            self.assertIsInstance(form["checksum"], bool, msg=form["name"])
            self.assertNotIn("algorithm", form)

    def test_the_client_contract_is_serialisable_for_every_rule(self):
        for rule in tax_ids.RULES:
            json.dumps(client_rule(rule.country))

    def test_a_reserved_gateways_key_does_not_reach_the_client(self):
        # `gateways` is declared for the country/gateway-eligibility work so
        # that lands as a key here rather than as a second country table.
        rule = Rule(
            country="ZZ",
            label="Test",
            forms=(Form("Test", r"^\d{2}$", mask="##", example="42"),),
            gateways=("asaas",),
        )
        tax_ids.RULES_BY_COUNTRY["ZZ"] = rule
        try:
            self.assertNotIn("gateways", client_rule("ZZ"))
        finally:
            del tax_ids.RULES_BY_COUNTRY["ZZ"]


class UnitTestBrazilianDocuments(UnitTestCase):
    def test_a_valid_cpf_and_cnpj_are_accepted(self):
        self.assertIsNone(problem_with(VALID_CPF, "BR", PERSON))
        self.assertIsNone(problem_with(VALID_CNPJ, "BR", ORGANIZATION))

    def test_a_transposed_digit_is_refused(self):
        self.assertIsNotNone(problem_with("111.444.777-53", "BR", PERSON))
        self.assertIsNotNone(problem_with("11.222.333/0001-18", "BR", ORGANIZATION))

    def test_repeated_digits_are_refused(self):
        # These satisfy the mod-11 arithmetic and are not real documents.
        self.assertIsNotNone(problem_with("111.111.111-11", "BR", PERSON))
        self.assertIsNotNone(problem_with("11.111.111/1111-11", "BR", ORGANIZATION))

    def test_the_wrong_length_is_refused(self):
        self.assertIsNotNone(problem_with("1114447773", "BR", PERSON))

    def test_a_person_may_not_give_a_cnpj(self):
        # A CNPJ is well-formed, but not a document a human is issued.
        self.assertIsNotNone(problem_with(VALID_CNPJ, "BR", PERSON))

    def test_an_organization_may_not_give_a_cpf(self):
        self.assertIsNotNone(problem_with(VALID_CPF, "BR", ORGANIZATION))

    def test_either_is_accepted_when_the_subject_is_not_narrowed(self):
        self.assertIsNone(problem_with(VALID_CPF, "BR", BOTH))
        self.assertIsNone(problem_with(VALID_CNPJ, "BR", BOTH))

    def test_the_stored_form_is_stripped_of_punctuation(self):
        self.assertEqual(clean_tax_id(VALID_CPF, "BR"), "11144477735")
        self.assertEqual(clean_tax_id(VALID_CNPJ, "BR"), "11222333000181")

    def test_the_displayed_form_is_masked(self):
        self.assertEqual(format_tax_id("11144477735", "BR", PERSON), VALID_CPF)
        self.assertEqual(
            format_tax_id("11222333000181", "BR", ORGANIZATION), VALID_CNPJ
        )

    def test_the_message_names_the_document_and_shows_a_specimen(self):
        message = problem_with("111.444.777-53", "BR", PERSON)
        self.assertIn("CPF", message)
        self.assertIn("111.444.777-35", message)

    def test_a_country_name_resolves_as_well_as_a_code(self):
        self.assertEqual(tax_ids.rule_for("Brazil").country, "BR")
        self.assertEqual(tax_ids.rule_for("br").country, "BR")


class UnitTestUnconfiguredCountries(UnitTestCase):
    def test_an_unconfigured_country_accepts_free_text(self):
        # The registry is an allowlist of rules someone has checked, not a
        # claim about the world.
        self.assertIsNone(problem_with("whatever-42", "ZW", PERSON))
        self.assertEqual(clean_tax_id("whatever-42", "ZW"), "whatever-42")

    def test_no_country_at_all_accepts_free_text(self):
        self.assertIsNone(problem_with("whatever-42", None, PERSON))

    def test_the_contract_says_it_is_unconfigured(self):
        contract = client_rule("ZW")
        self.assertFalse(contract["configured"])
        self.assertNotIn("forms", contract)

    def test_a_blank_value_is_never_refused(self):
        # Whether a tax ID is *required* is curated on Mandatory Personal
        # Field, not decided here.
        for value in ("", None, "   "):
            self.assertIsNone(problem_with(value, "BR", PERSON), msg=repr(value))
            self.assertIsNone(assert_tax_id(value, "BR", PERSON), msg=repr(value))

    def test_assert_throws_on_a_bad_value(self):
        self.assertRaises(
            frappe.ValidationError, assert_tax_id, "111.444.777-53", "BR", PERSON
        )


class UnitTestTheCheckEndpoint(UnitTestCase):
    def test_it_never_throws(self):
        for value, country in (
            ("garbage", "BR"),
            (None, "BR"),
            ("9" * 500, "BR"),
            (VALID_CPF, "ZW"),
            (VALID_CPF, None),
        ):
            verdict = tax_ids.check_tax_id(value, country, PERSON)
            self.assertIn("ok", verdict)

    def test_it_reports_which_form_matched(self):
        verdict = tax_ids.check_tax_id(VALID_CPF, "BR", PERSON)
        self.assertTrue(verdict["ok"])
        self.assertEqual(verdict["form"], "CPF")
        self.assertEqual(verdict["formatted"], VALID_CPF)

    def test_it_reveals_nothing_about_stored_data(self):
        """Two different valid CPFs must answer identically.

        Anything that consulted the database here would be an enumeration
        oracle over every tax ID the school holds, on an endpoint open to the
        internet.
        """
        first = tax_ids.check_tax_id("111.444.777-35", "BR", PERSON)
        second = tax_ids.check_tax_id("529.982.247-25", "BR", PERSON)
        self.assertEqual(first["ok"], second["ok"])
        self.assertEqual(first["form"], second["form"])
        self.assertEqual(first["message"], second["message"])


class IntegrationTestTaxIdOnPerson(IntegrationTestCase):
    def test_nationality_decides_the_rule(self):
        person = make_person()
        person.nationality = "Brazil"
        person.mailing_country = "United States"
        person.tax_id = VALID_CPF
        person.save(ignore_permissions=True)
        self.assertEqual(person.tax_id, "11144477735")

        person.tax_id = "111.444.777-53"
        self.assertRaises(frappe.ValidationError, person.save)

    def test_the_mailing_country_is_the_fallback(self):
        person = make_person()
        person.mailing_country = "Brazil"
        person.tax_id = "111.444.777-53"
        self.assertRaises(frappe.ValidationError, person.save)

    def test_a_person_may_not_give_an_organizations_number(self):
        person = make_person()
        person.nationality = "Brazil"
        person.tax_id = VALID_CNPJ
        self.assertRaises(frappe.ValidationError, person.save)

    def test_a_country_with_no_rule_keeps_what_was_typed(self):
        person = make_person()
        person.nationality = "Zimbabwe"
        person.tax_id = "63-1234567-A-42"
        person.save(ignore_permissions=True)
        self.assertEqual(person.tax_id, "63-1234567-A-42")

    def test_no_country_at_all_keeps_what_was_typed(self):
        person = make_person()
        person.tax_id = "whatever-42"
        person.save(ignore_permissions=True)
        self.assertEqual(person.tax_id, "whatever-42")

    def test_a_legacy_value_only_warns_until_it_is_touched(self):
        """A rule shipped this week must not make a record from three years ago
        unsaveable while a registrar corrects an unrelated field."""
        person = make_person()
        person.nationality = "Brazil"
        person.save(ignore_permissions=True)
        # Straight to the column, the way the data actually got there.
        frappe.db.set_value("Person", person.name, "tax_id", "1111111")

        person.reload()
        person.city = "Recife"
        person.save(ignore_permissions=True)  # must not throw
        self.assertEqual(person.tax_id, "1111111")

        person.tax_id = "1111112"
        self.assertRaises(frappe.ValidationError, person.save)

    def test_the_tax_id_reaches_the_spine(self):
        person = make_person()
        spine.update_person(
            person.name, nationality="Brazil", tax_id=VALID_CPF, overwrite=True
        )
        self.assertEqual(
            frappe.db.get_value("Person", person.name, "tax_id"), "11144477735"
        )

    def test_the_country_field_registry_names_real_fields(self):
        for doctype, fieldnames in tax_ids.COUNTRY_FIELDS.items():
            meta = frappe.get_meta(doctype)
            self.assertTrue(meta.get_field("tax_id"), msg=doctype)
            for fieldname in fieldnames:
                self.assertTrue(meta.get_field(fieldname), msg=f"{doctype}.{fieldname}")

    def test_every_doctype_with_a_country_rule_declares_a_subject(self):
        self.assertEqual(set(tax_ids.COUNTRY_FIELDS), set(tax_ids.SUBJECTS))


class IntegrationTestTaxIdOnPartnerOrganization(IntegrationTestCase):
    """The organization's country decides its registration number.

    These live here rather than beside the doctype because loading Partner
    Organization's test-record dependencies reaches erpnext (the `customer`
    link is an oikonomos custom field), whose bootstrap re-inserts the standard
    price lists and dies on any site that already has them.
    """

    PREFIX = "ZZ Partner Tax"

    def tearDown(self):
        for name in frappe.get_all(
            "Partner Organization",
            filters={"organization_name": ("like", self.PREFIX + "%")},
            pluck="name",
        ):
            frappe.delete_doc(
                "Partner Organization", name, force=True, ignore_permissions=True
            )

    def _org(self, country=None, tax_id=None):
        return frappe.get_doc(
            {
                "doctype": "Partner Organization",
                "organization_name": "%s %s"
                % (self.PREFIX, frappe.generate_hash(length=6)),
                "status": "Prospect",
                "listing_status": "Pending Approval",
                "country": country,
                "tax_id": tax_id,
            }
        )

    def test_a_valid_cnpj_is_stored_cleaned(self):
        org = self._org(country="Brazil", tax_id=VALID_CNPJ)
        org.insert(ignore_permissions=True)
        self.assertEqual(org.tax_id, "11222333000181")

    def test_an_invalid_cnpj_is_refused(self):
        org = self._org(country="Brazil", tax_id="11.222.333/0001-18")
        self.assertRaises(frappe.ValidationError, org.insert)

    def test_an_organization_may_not_give_a_persons_number(self):
        # A CPF is a well-formed Brazilian document, but not one issued to an
        # organization — a church is billed against its CNPJ.
        org = self._org(country="Brazil", tax_id=VALID_CPF)
        self.assertRaises(frappe.ValidationError, org.insert)

    def test_a_country_with_no_rule_keeps_what_was_typed(self):
        org = self._org(country="Zimbabwe", tax_id="63-1234567-A-42")
        org.insert(ignore_permissions=True)
        self.assertEqual(org.tax_id, "63-1234567-A-42")


class UnitTestTheLabelFollowsTheSubject(UnitTestCase):
    def test_a_person_form_asks_for_the_persons_document_only(self):
        self.assertEqual(client_rule("BR", PERSON)["label"], "CPF")
        self.assertEqual(client_rule("BR", ORGANIZATION)["label"], "CNPJ")

    def test_an_unnarrowed_field_keeps_the_countrys_own_label(self):
        self.assertEqual(client_rule("BR", BOTH)["label"], "CPF / CNPJ")

    def test_a_narrowed_contract_ships_only_the_forms_it_names(self):
        self.assertEqual(
            [f["name"] for f in client_rule("BR", PERSON)["forms"]], ["CPF"]
        )
