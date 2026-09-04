# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""The applicant boundary (ADR 068 §7).

Student Applicant is the one doctype that captures personal data before a
Person exists — a guest has no User, and ADR 042 §4 chose that over a signup
wall in front of admissions. Being the exception is exactly why it needs tests:
the promotion to the spine was a hand-written argument list that named seven
attributes while the registry declared fourteen, so the address and gender an
applicant typed simply never arrived. Nothing threw and nothing was logged,
because nothing was attempted.

So the load-bearing test here is not "the address promotes" — it is that no
attribute the registry declares can be left out of the promotion again.
"""

import frappe
from frappe.model import NO_VALUE_FIELDS
from frappe.tests import IntegrationTestCase
from frappe.utils import cstr

from seminary.seminary import person_fields as registry
from seminary.seminary.tests.cohort_fixtures import current_term, make_program, uid

EXTRA_TEST_RECORD_DEPENDENCIES = []

#: Web Form rows that render structure rather than a value. `Page Break` is a
#: web-form-only fieldtype (it starts a new page of the form) and so is absent
#: from Frappe's own `NO_VALUE_FIELDS`.
LAYOUT_FIELDTYPES = NO_VALUE_FIELDS | {"Page Break"}

# Same reason as test_person: somewhere below these links sits erpnext's
# `BootStrapTestData`, which inserts the standard price lists at import time
# and raises DuplicateEntryError on a site that already has them — before a
# single test runs. Every one of Student Applicant's own link targets is listed
# because `get_missing_records_doctypes` applies this list to *direct* links
# only, so naming the transitively-reached doctype does nothing. The fixtures
# below create everything these tests need anyway.
IGNORE_TEST_RECORD_DEPENDENCIES = [
    "User",
    "Person",
    "Program",
    "Academic Year",
    "Academic Term",
    "Term Admission",
    "Country",
    "Salutation",
    "Doctrinal Statement",
]

#: A full capture: every attribute the applicant binds in the registry.
CAPTURED = {
    "first_name": "Aurelia",
    "middle_name": "Reyes",
    "last_name": "Vasquez",
    "student_mobile_number": "5125550117",
    "gender": "Female",
    "date_of_birth": "1991-04-17",
    "address_line_1": "1100 Congress Avenue",
    "address_line_2": "Apt 4",
    "city": "Austin",
    "state": "TX",
    "pincode": "78701",
    "blood_group": "O+",
    "marital": "Single",
    "ethnic": "Hispanic",
}


def make_applicant(ignore_mandatory=False, **overrides):
    term = current_term()
    values = {
        "doctype": "Student Applicant",
        "program": make_program().name,
        "academic_term": term,
        "academic_year": frappe.db.get_value("Academic Term", term, "academic_year"),
        "student_email_id": "applicant-%s@example.test" % uid().replace(" ", "-"),
        "application_status": "Applied",
    }
    values.update(CAPTURED)
    values.update(overrides)
    doc = frappe.get_doc(values)
    doc.flags.ignore_mandatory = ignore_mandatory
    doc.insert(ignore_permissions=True)
    return doc


class TestTheCaptureReachesTheSpine(IntegrationTestCase):
    def test_every_captured_attribute_lands_on_the_person(self):
        """The bug this phase exists to close.

        Written as a loop over the registry rather than a list of assertions:
        a hand-written list here would rot the same way the hand-written
        argument list in `_promote_to_person` did.
        """
        applicant = make_applicant()
        person = frappe.get_doc("Person", applicant.person)
        for spec, binding in registry.bindings_for("Student Applicant"):
            if not spec.settable:
                continue
            captured = applicant.get(binding.fieldname)
            if not captured:
                continue
            with self.subTest(attribute=spec.person_field):
                # `cstr` because a Date comes back from the spine as a
                # `datetime.date` and is still a string on the form document.
                self.assertEqual(
                    cstr(person.get(spec.person_field)),
                    cstr(captured),
                    "%s never reached Person.%s"
                    % (binding.fieldname, spec.person_field),
                )

    def test_the_promotion_is_derived_from_the_registry_not_written_out(self):
        """`spine_kwargs` must offer every settable attribute the applicant
        binds — this is the guard, the assertion above is the symptom."""
        kwargs = registry.spine_kwargs(make_applicant())
        expected = {
            spec.arg
            for spec, _binding in registry.bindings_for("Student Applicant")
            if spec.settable
        }
        self.assertEqual(set(kwargs), expected)

    def test_the_postal_country_seeds_the_routing_country_but_stays_distinct(self):
        """One column on the form feeds two fields on the spine, declared.

        `Person.country` selects the messaging provider (ADR 043); the postal
        country is `mailing_country`. The applicant asks for one country, so it
        seeds both — but only as a seed, or a later address edit would move the
        SMS routing of anyone who moved house.
        """
        applicant = make_applicant(country="United States")
        person = frappe.get_doc("Person", applicant.person)
        self.assertEqual(person.mailing_country, "United States")
        self.assertEqual(person.country, "United States")

    def test_a_pre_admission_edit_re_promotes(self):
        applicant = make_applicant()
        applicant.city = "Round Rock"
        applicant.save(ignore_permissions=True)
        self.assertEqual(
            frappe.db.get_value("Person", applicant.person, "city"), "Round Rock"
        )


class TestTheFieldNamesAgree(IntegrationTestCase):
    def test_the_postal_code_is_spelled_the_same_everywhere(self):
        """`zipcode` was a second spelling of `pincode`, and a second spelling
        is not cosmetic: `enroll_student` maps applicant to student by matching
        field names, so the postal code was dropped at admission."""
        meta = frappe.get_meta("Student Applicant")
        self.assertTrue(meta.get_field("pincode"))
        self.assertFalse(meta.get_field("zipcode"))

    def test_the_column_was_renamed_not_duplicated(self):
        """A dropped docfield keeps its column until `bench trim-tables`, so a
        copy-and-abandon migration would leave `zipcode` still answering raw
        SQL with data that no longer updates."""
        columns = {
            row.get("Field")
            for row in frappe.db.sql("describe `tabStudent Applicant`", as_dict=True)
        }
        self.assertIn("pincode", columns)
        self.assertNotIn("zipcode", columns)


class TestTheWebFormsStillMatchTheDoctype(IntegrationTestCase):
    """A Web Form field naming a column the doctype no longer has.

    This is not hypothetical and it is not loud. Renaming `zipcode` to
    `pincode` updated the doctype (imported by content hash) but *not* the Web
    Form: for records other than DocType, `import_file_by_path` skips the file
    whenever the database's `modified` is not older than the JSON's, and the
    two were byte-identical timestamps. So the live form kept rendering a
    `zipcode` input — the autocomplete could not find the field to fill, and
    anything typed into it by hand was dropped on submit, because the applicant
    has no such column any more. Nothing threw at any point.
    """

    def test_every_web_form_field_exists_on_the_doctype(self):
        meta = frappe.get_meta("Student Applicant")
        forms = frappe.get_all(
            "Web Form", filters={"doc_type": "Student Applicant"}, pluck="name"
        )
        self.assertTrue(forms, "no Student Applicant web form to check")
        for form in forms:
            rows = frappe.get_all(
                "Web Form Field",
                filters={"parent": form, "parenttype": "Web Form"},
                fields=["fieldname", "fieldtype"],
            )
            for row in rows:
                # Layout rows carry no data and often no fieldname at all.
                if not row.fieldname or row.fieldtype in LAYOUT_FIELDTYPES:
                    continue
                with self.subTest(form=form, field=row.fieldname):
                    self.assertTrue(
                        meta.get_field(row.fieldname),
                        "web form %r renders %r, which Student Applicant does "
                        "not have — anything entered there is discarded on "
                        "submit" % (form, row.fieldname),
                    )

    def test_a_link_field_is_a_link_on_the_form_too(self):
        """A Link rendered as `Data` is a free-text box that accepts anything
        and fails at submit. `nationality` was exactly that: an applicant typed
        "Brasileira", got no picker, no inline warning, and a link error only
        when they pressed Submit at the end of a long multi-page form.
        """
        meta = frappe.get_meta("Student Applicant")
        forms = frappe.get_all(
            "Web Form", filters={"doc_type": "Student Applicant"}, pluck="name"
        )
        for form in forms:
            rows = frappe.get_all(
                "Web Form Field",
                filters={"parent": form, "parenttype": "Web Form", "fieldtype": "Data"},
                fields=["fieldname"],
            )
            for row in rows:
                df = meta.get_field(row.fieldname)
                with self.subTest(form=form, field=row.fieldname):
                    self.assertNotEqual(
                        df and df.fieldtype,
                        "Link",
                        "%s.%s is a Link on the doctype but a free-text Data "
                        "box on web form %r" % (meta.name, row.fieldname, form),
                    )


class TestTheGenderPickerIsCurated(IntegrationTestCase):
    """A seminary cannot be shipped Frappe's whole gender vocabulary.

    Frappe's setup wizard seeds seven Gender rows. The app carried a custom
    `enabled` Check to narrow them, but nothing anywhere filtered on it, so
    every picker — the public application form included — offered all seven.

    The fix is the field's *name*, not a filter: `frappe/desk/search.py` drops
    rows from every Link search when the target doctype has a Check called
    `disabled`. Frappe's own convention, so it survives upgrades, needs no
    per-field wiring, and reaches Web Forms — which matters because `Web Form
    Field` has no `link_filters` column for a per-field filter to live in.
    """

    def test_gender_carries_the_field_frappe_filters_on(self):
        df = frappe.get_meta("Gender").get_field("disabled")
        self.assertTrue(df, "Gender has no `disabled` field to filter on")
        self.assertEqual(df.fieldtype, "Check")

    def test_the_retired_enabled_flag_is_gone(self):
        """Two flags answering "is this gender offered" can disagree, and the
        one nothing reads is the one that drifts."""
        self.assertFalse(
            frappe.db.exists("Custom Field", {"dt": "Gender", "fieldname": "enabled"}),
            "Gender.enabled is back — check seminary/fixtures/custom_field.json, "
            "which re-imports on every migrate",
        )

    def test_a_disabled_gender_is_not_offered_by_the_picker(self):
        frappe.db.set_value("Gender", "Other", "disabled", 1, update_modified=False)
        offered = self._search_genders()
        self.assertNotIn("Other", offered)

    def test_an_enabled_gender_is_offered(self):
        frappe.db.set_value("Gender", "Other", "disabled", 0, update_modified=False)
        self.assertIn("Other", self._search_genders())

    def _search_genders(self):
        from frappe.desk.search import search_widget

        frappe.response = frappe._dict()
        return [row[0] for row in search_widget(doctype="Gender", txt="") or []]

    def test_the_public_form_offers_only_the_curated_genders(self):
        """The picker filter and the *web form* are two different code paths.

        Desk pickers go through `search_widget`, which applies the `disabled`
        convention for free. A web form never touches it: `process_link_field`
        turns the Link into an Autocomplete and preloads every row from
        `get_link_options`, an unfiltered `frappe.get_all`. So the surface
        where a curated list matters most was the one ignoring the curation —
        `SeminaryWebForm.get_context` is what closes that, and this is the test
        that would have caught the gap in the first place.
        """
        offered = self._form_options("gender")
        self.assertIn("Male", offered)
        self.assertIn("Female", offered)
        for name in frappe.get_all("Gender", filters={"disabled": 1}, pluck="name"):
            with self.subTest(gender=name):
                self.assertNotIn(name, offered)

    def test_enabling_a_gender_puts_it_back_on_the_public_form(self):
        frappe.db.set_value("Gender", "Other", "disabled", 0, update_modified=False)
        self.assertIn("Other", self._form_options("gender"))

    def _form_options(self, fieldname):
        """Render the guest context of the public form and read one field."""
        form = frappe.get_doc("Web Form", "student-applicant")
        # `frappe.local` raises rather than returning None for an unset key,
        # and the test runner has no request, so `path` is simply absent.
        path = getattr(frappe.local, "path", None)
        form_dict = getattr(frappe.local, "form_dict", None)
        user = frappe.session.user
        try:
            frappe.set_user("Guest")
            # `get_context` redirects unless it believes it is on the "new"
            # route; without both of these it never reaches the field loop.
            frappe.local.path = "%s/new" % form.route
            frappe.local.form_dict = frappe._dict(is_new=1)
            context = frappe._dict()
            form.get_context(context)
        finally:
            frappe.set_user(user)
            frappe.local.path = path
            frappe.local.form_dict = form_dict or frappe._dict()

        for field in context.web_form_doc.web_form_fields:
            if field.fieldname == fieldname:
                return [row["value"] for row in field.options]
        self.fail("web form has no %r field" % fieldname)

    def test_the_applicant_and_the_spine_agree_on_the_type(self):
        """`Student Applicant.gender` was a Select of the literals Male/Female
        while `Person.gender` is a Link to Gender — and the web form rendered a
        Link, which is how the two drifted apart unnoticed. A curated Gender
        table is only customisable if the field is a Link to it."""
        for doctype in ("Student Applicant", "Person"):
            df = frappe.get_meta(doctype).get_field("gender")
            with self.subTest(doctype=doctype):
                self.assertEqual(df.fieldtype, "Link")
                self.assertEqual(df.options, "Gender")


class TestAdmissionFreezesTheCapture(IntegrationTestCase):
    def test_every_captured_field_is_frozen_in_the_ui_after_admission(self):
        """The freeze shipped on exactly five fields — the five names — which
        are also the only five that were ever propagated. Everything else was
        writable, unpropagated and unhydrated: an unmanaged second home."""
        meta = frappe.get_meta("Student Applicant")
        for fieldname in registry.capture_fields("Student Applicant"):
            df = meta.get_field(fieldname)
            with self.subTest(field=fieldname):
                self.assertEqual(
                    df.read_only_depends_on,
                    'eval:doc.application_status=="Admitted"',
                    "%s stays editable after admission" % fieldname,
                )

    def test_a_late_edit_is_refused_on_the_server(self):
        """`read_only` is a UI hint — Frappe enforces `permlevel` only — so the
        JSON flag above would give a test something to assert and an API client
        nothing to trip over."""
        applicant = make_applicant()
        applicant.application_status = "Admitted"
        applicant.save(ignore_permissions=True)

        applicant.city = "El Paso"
        with self.assertRaises(frappe.ValidationError):
            applicant.save(ignore_permissions=True)

    def test_the_admitting_save_may_still_carry_a_correction(self):
        """The transition itself is not late; the saves after it are."""
        applicant = make_applicant()
        applicant.application_status = "Admitted"
        applicant.city = "San Marcos"
        applicant.save(ignore_permissions=True)
        self.assertEqual(applicant.city, "San Marcos")

    def test_an_unrelated_field_still_saves_after_admission(self):
        """The freeze is about shared identity, not about sealing the record —
        admissions staff still annotate employment, church and references."""
        applicant = make_applicant()
        applicant.application_status = "Admitted"
        applicant.save(ignore_permissions=True)
        applicant.employer = "Hill Country Bible Church"
        applicant.save(ignore_permissions=True)
        self.assertEqual(applicant.employer, "Hill Country Bible Church")


class TestTheCaptureBackstop(IntegrationTestCase):
    def test_a_form_that_skips_a_required_attribute_is_refused(self):
        """Admins can point intake at any Web Form built against this doctype.
        A form that omits a field cannot be caught on the client, and the
        omission is invisible afterwards: the applicant looks complete and only
        the Person is empty.

        `ignore_mandatory` here stands in for that missing field — it is also
        the flag importers set, which is the other way the check gets reached.
        """
        with self.assertRaises(frappe.ValidationError) as caught:
            make_applicant(gender=None, ignore_mandatory=True)
        self.assertIn("Gender", str(caught.exception))

    def test_the_backstop_names_what_the_registry_declares(self):
        for person_field in registry.CAPTURE_REQUIRED:
            with self.subTest(attribute=person_field):
                self.assertIn(person_field, registry.SPEC_BY_PERSON_FIELD)
