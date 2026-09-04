# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""The identity spine's own tests (ADR 068).

The spine had no direct coverage at all, which is how four seams ended up
disagreeing about what a shared human attribute is. Two kinds of test here:

**Agreement** — the registry in `person_fields.py` and the doctype JSONs must
say the same thing. These are what make the registry load-bearing rather than
decorative: adding an attribute and forgetting a doctype fails here instead of
becoming the next silent hole.

**Behaviour** — the write semantics the registry declares actually hold.
"""

import inspect

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import person as spine
from seminary.seminary import person_fields as registry
from seminary.seminary.tests.cohort_fixtures import (
    make_instructor,
    make_person,
    make_student,
    make_user,
)

EXTRA_TEST_RECORD_DEPENDENCIES = []

# Person links User, which links Email Account, which links erpnext's Company —
# and `erpnext.setup.doctype.company.test_company` imports `erpnext.tests.utils`,
# whose BootStrapTestData inserts the standard price lists at import time. On a
# site that already has them (potestas does) that raises DuplicateEntryError
# before a single test runs.
#
# It has to be `User` and not `Company`: `get_missing_records_doctypes` applies
# each doctype's ignore list to that doctype's *direct* link fields only, so
# naming a transitively-reached doctype here does nothing. Nothing in this
# module needs User test records — the fixtures create their own.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


class TestRegistryAgreesWithTheDoctypes(IntegrationTestCase):
    """The registry describes the schema, or it describes nothing."""

    def test_every_person_field_in_the_registry_exists(self):
        meta = frappe.get_meta("Person")
        for spec in registry.SPEC:
            with self.subTest(field=spec.person_field):
                self.assertTrue(
                    meta.get_field(spec.person_field),
                    "Person has no field %r" % spec.person_field,
                )

    def test_every_role_binding_points_at_a_real_field(self):
        for doctype in registry.ROLE_DOCTYPES:
            meta = frappe.get_meta(doctype)
            for spec, binding in registry.bindings_for(doctype):
                with self.subTest(doctype=doctype, field=binding.fieldname):
                    self.assertTrue(
                        meta.get_field(binding.fieldname),
                        "%s has no field %r (declared for Person.%s)"
                        % (doctype, binding.fieldname, spec.person_field),
                    )

    def test_a_mirror_declares_fetch_from_and_read_only(self):
        for doctype in registry.ROLE_DOCTYPES:
            meta = frappe.get_meta(doctype)
            for spec, binding in registry.bindings_for(doctype):
                if binding.kind != registry.MIRROR:
                    continue
                df = meta.get_field(binding.fieldname)
                with self.subTest(doctype=doctype, field=binding.fieldname):
                    self.assertEqual(df.fetch_from, "person.%s" % spec.person_field)
                    self.assertTrue(df.read_only)

    def test_a_snapshot_never_declares_fetch_from(self):
        """The one assertion standing between a rename and a reissued diploma.

        `Program Enrollment.student_name` is the name that reaches the diploma.
        A snapshot that quietly grows a `fetch_from` re-fetches on every save —
        including `on_update_after_submit` — and rewrites the legal name on a
        completed enrollment.
        """
        for doctype in registry.ROLE_DOCTYPES:
            meta = frappe.get_meta(doctype)
            for _spec, binding in registry.bindings_for(doctype):
                if binding.kind != registry.SNAPSHOT:
                    continue
                df = meta.get_field(binding.fieldname)
                with self.subTest(doctype=doctype, field=binding.fieldname):
                    self.assertFalse(
                        df.fetch_from,
                        "%s.%s is a snapshot; a fetch_from would re-derive it"
                        % (doctype, binding.fieldname),
                    )

    def test_a_foreign_binding_still_points_where_the_registry_says(self):
        """Pins the mirrors that fetch from somewhere other than the spine.

        `Instructor.gender` fetches from erpnext's `Employee` — a doctype this
        app does not require — and `Alumni Profile.image` fetches from Student,
        a mirror of a mirror. Neither is a decision anyone made; declaring them
        keeps them visible until phase 4 repoints them at Person.
        """
        for doctype in registry.ROLE_DOCTYPES:
            meta = frappe.get_meta(doctype)
            for _spec, binding in registry.bindings_for(doctype):
                if binding.kind != registry.FOREIGN:
                    continue
                df = meta.get_field(binding.fieldname)
                with self.subTest(doctype=doctype, field=binding.fieldname):
                    self.assertEqual(df.fetch_from, binding.source)

    def test_a_local_binding_has_not_quietly_become_a_mirror(self):
        """Locks the pre-068 state so the migration phases show up as diffs.

        A `fetch_from` appearing on a LOCAL field means someone converted it
        without moving the registry — exactly the drift this module exists to
        stop.
        """
        for doctype in registry.ROLE_DOCTYPES:
            meta = frappe.get_meta(doctype)
            for _spec, binding in registry.bindings_for(doctype):
                if binding.kind != registry.LOCAL:
                    continue
                df = meta.get_field(binding.fieldname)
                with self.subTest(doctype=doctype, field=binding.fieldname):
                    self.assertFalse(
                        df.fetch_from,
                        "%s.%s gained a fetch_from but is still declared LOCAL"
                        % (doctype, binding.fieldname),
                    )


class TestRegistryAgreesWithTheSpineApi(IntegrationTestCase):
    def test_the_entry_points_accept_exactly_the_settable_attributes(self):
        """A keyword the registry does not know is silently dropped by
        `_values_from_kwargs`, so the two lists have to match exactly."""
        for func in (spine.ensure_person, spine.update_person):
            accepted = set(inspect.signature(func).parameters)
            with self.subTest(func=func.__name__):
                self.assertEqual(
                    accepted & set(registry.SETTABLE_ARGS),
                    set(registry.SETTABLE_ARGS),
                    "%s does not accept every settable attribute" % func.__name__,
                )

    def test_the_retired_tuples_are_gone(self):
        """`FILL_ONLY_FIELDS` was declared and read nowhere — the fill-only
        behaviour it named was really `_apply`'s fallthrough. Keeping a second,
        partial copy of the field list is what let the four seams diverge."""
        self.assertFalse(hasattr(spine, "IDENTITY_FIELDS"))
        self.assertFalse(hasattr(spine, "FILL_ONLY_FIELDS"))


class TestOpaqueDocnames(IntegrationTestCase):
    """A role record must not be keyed on the person's own data (ADR 068 §5)."""

    OPAQUE = {
        "Instructor": "INST-",
        "Alumni Profile": "ALUM-",
        "Student Applicant": "APP-",
        "Student": "",  # already opaque: format:{YY}-{#####}
    }

    def test_no_role_doctype_autonames_from_personal_data(self):
        personal = {spec.person_field for spec in registry.SPEC} | {
            binding.fieldname
            for doctype in registry.ROLE_DOCTYPES
            for _s, binding in registry.bindings_for(doctype)
        }
        for doctype in self.OPAQUE:
            autoname = frappe.get_meta(doctype).autoname or ""
            with self.subTest(doctype=doctype):
                for field in personal:
                    self.assertNotIn(
                        "{%s}" % field,
                        autoname,
                        "%s is keyed on %s" % (doctype, field),
                    )
                self.assertFalse(
                    autoname.startswith("field:"),
                    "%s autonames from a field value" % doctype,
                )

    def test_renamed_doctypes_allow_rename(self):
        """`rename_doc` refuses without it, so a future correction would need a
        patch author to remember `force=True`."""
        for doctype in ("Instructor", "Alumni Profile", "Student Applicant"):
            with self.subTest(doctype=doctype):
                self.assertTrue(frappe.get_meta(doctype).allow_rename)

    def test_link_controls_still_show_a_name(self):
        """`title_field` alone is not enough — `desk/search.py` only labels a
        link with it when `show_title_field_in_link` is set. Without this every
        faculty picker in the app would read INST-00001."""
        for doctype in ("Instructor", "Alumni Profile", "Student Applicant"):
            meta = frappe.get_meta(doctype)
            with self.subTest(doctype=doctype):
                self.assertTrue(meta.title_field)
                self.assertTrue(meta.show_title_field_in_link)
                self.assertTrue(meta.search_fields)

    def test_a_corrected_name_now_reaches_the_instructor(self):
        """`person.py` used to hold `targets["Instructor"] = {}` precisely
        because the docname was the name, so a correction on the spine stayed
        invisible forever."""
        instructor = make_instructor()
        person = frappe.get_doc("Person", instructor.person)
        person.last_name = "Renamed"
        person.save(ignore_permissions=True)

        row = frappe.db.get_value(
            "Instructor", instructor.name, ["instructor_name", "name"], as_dict=True
        )
        self.assertIn("Renamed", row.instructor_name)
        self.assertTrue(row.name.startswith("INST-"), "the docname must not move")


class TestPersonFirst(IntegrationTestCase):
    """A role record is created against a Person, never the other way round."""

    def test_the_person_link_is_required_and_writable(self):
        """`reqd` + `read_only` would be a doctype nobody can create: the field
        is mandatory and there is no way to fill it."""
        for doctype in ("Student", "Instructor", "Alumni Profile"):
            df = frappe.get_meta(doctype).get_field("person")
            with self.subTest(doctype=doctype):
                self.assertTrue(df.reqd, "%s.person is not required" % doctype)
                self.assertFalse(df.read_only, "%s.person is not writable" % doctype)

    def test_a_role_record_without_a_person_is_refused(self):
        doc = frappe.new_doc("Student")
        doc.first_name = "ZZT Orphan"
        with self.assertRaises(frappe.MandatoryError):
            doc.insert(ignore_permissions=True)

    def test_the_mirrors_are_populated_on_the_very_first_save(self):
        """`_validate_links` runs *before* `validate`, so a controller that
        resolved `person` in `validate` missed the fetch and saved with empty
        mirrors until the record was touched a second time."""
        from seminary.seminary import intake

        person = make_person("FirstSave")
        student = intake.make_student(person)
        row = frappe.db.get_value(
            "Student",
            student.name,
            ["student_name", "student_email_id", "first_name"],
            as_dict=True,
        )
        self.assertEqual(row.student_name, person.full_name)
        self.assertEqual(row.student_email_id, person.primary_email)
        self.assertEqual(row.first_name, person.first_name)

    def test_intake_refuses_an_unknown_person(self):
        from seminary.seminary import intake

        with self.assertRaises(frappe.ValidationError):
            intake.make_student("PERS-does-not-exist")

    def test_the_user_is_provisioned_after_insert_not_during_validate(self):
        """Creating the User mid-validation committed it, and its Student role
        grant, even when the Student itself went on to fail."""
        from seminary.seminary import intake

        person = make_person("Provisioned")
        student = intake.make_student(person)
        self.assertEqual(
            frappe.db.get_value("Student", student.name, "user"),
            person.primary_email,
        )
        self.assertFalse(
            hasattr(frappe.get_doc("Student", student.name), "resolve_person")
        )


class TestSnapshotsDoNotMove(IntegrationTestCase):
    """The assertion standing between a rename and a reissued diploma."""

    def test_no_snapshot_field_declares_a_fetch_from(self):
        for snap in registry.SNAPSHOTS:
            if not frappe.db.exists("DocType", snap.doctype):
                continue
            df = frappe.get_meta(snap.doctype).get_field(snap.fieldname)
            with self.subTest(doctype=snap.doctype, field=snap.fieldname):
                self.assertTrue(df, "%s has no %s" % (snap.doctype, snap.fieldname))
                self.assertFalse(
                    df.fetch_from,
                    "%s.%s is a snapshot; a fetch_from would re-derive it on "
                    "every save, including on_update_after_submit"
                    % (snap.doctype, snap.fieldname),
                )

    def test_the_enrollment_name_is_captured_then_frozen(self):
        person = make_person("Graduand")
        student = make_student(person)

        enrollment = frappe.new_doc("Program Enrollment")
        enrollment.student = student.name
        registry.capture_snapshots(enrollment)
        captured = enrollment.student_name
        self.assertTrue(captured, "the name was not captured at creation")

        person.reload()
        person.last_name = "MarriedName"
        person.save(ignore_permissions=True)

        # Re-running capture on an already-recorded document must not move it.
        registry.capture_snapshots(enrollment)
        self.assertEqual(enrollment.student_name, captured)
        # ...while the student's own record does follow the rename.
        self.assertIn(
            "MarriedName",
            frappe.db.get_value("Student", student.name, "student_name"),
        )


class TestOneRecordPerRolePerPerson(IntegrationTestCase):
    """One record *per role*, many roles per person.

    The rule used to be enforced only by accident and only in two places: a
    second Student or Alumni Profile collided on its unique email mirror, while
    a second Instructor was created happily — `prof_email` is not unique and
    neither is `Instructor.user`.
    """

    def test_the_person_link_is_unique_in_the_database(self):
        """Asserts the index, not the docfield flag.

        `unique: 1` in the JSON did *not* produce a unique index here: the
        column already carried a plain index from being a Link, and Frappe's
        schema updater leaves it rather than converting it. So the meta said
        unique while MariaDB happily accepted duplicates, and a test reading
        `meta.get_field("person").unique` passed against a database that
        enforced nothing. The patch creates the index explicitly; this is what
        proves it took.
        """
        for doctype in ("Student", "Instructor", "Alumni Profile"):
            indexes = frappe.db.sql(
                "show index from `tab{0}` where Column_name = 'person'".format(doctype),
                as_dict=True,
            )
            with self.subTest(doctype=doctype):
                self.assertTrue(
                    any(row["Non_unique"] == 0 for row in indexes),
                    "%s.person has no unique index (found: %s)"
                    % (doctype, [r["Key_name"] for r in indexes]),
                )

    def test_a_second_student_is_refused(self):
        from seminary.seminary import intake

        person = make_person("OnlyOnce")
        intake.make_student(person)
        # Not matched on `unique_person`: the email mirror fills both rows with
        # the same address, so `student_email_id`'s index trips first. The
        # person index is proved directly by the index test above — what
        # matters here is that a second Student cannot be created at all.
        with self.assertRaises(frappe.UniqueValidationError):
            intake.make_student(person)

    def test_a_second_instructor_is_refused(self):
        """The one that was not blocked at all before ADR 068 phase 5 —
        `prof_email` is not unique and neither is `Instructor.user`, so nothing
        stood in the way. This is the case where `unique_person` is the
        constraint actually doing the work, so match on it by name."""
        from seminary.seminary import intake

        person = make_person("OneChair", user=make_user().name)
        intake.make_instructor(person)
        with self.assertRaisesRegex(frappe.UniqueValidationError, "unique_person"):
            intake.make_instructor(person)

    def test_one_person_may_hold_several_different_roles(self):
        """A student who teaches is one human, not three — this is the whole
        point of the spine (ADR 042), and the uniqueness above is per doctype
        precisely so it stays possible."""
        from seminary.seminary import intake

        person = make_person("Polymath", user=make_user().name)
        student = intake.make_student(person)
        instructor = intake.make_instructor(person)
        alumni = intake.make_alumni_profile(person)

        for doctype, doc in (
            ("Student", student),
            ("Instructor", instructor),
            ("Alumni Profile", alumni),
        ):
            with self.subTest(doctype=doctype):
                self.assertEqual(
                    frappe.db.get_value(doctype, doc.name, "person"), person.name
                )

    def test_a_student_still_holds_many_program_enrollments(self):
        """Uniqueness is about identity, not about academic history."""
        self.assertFalse(
            frappe.get_meta("Program Enrollment").get_field("student").unique
        )


class TestSensitiveAttributes(IntegrationTestCase):
    """Permlevel-1 fields with no permlevel-1 permission row are invisible and
    unwritable for every role — while still working for Administrator, which
    is exactly how such a mistake survives a smoke test."""

    def test_a_sensitive_attribute_is_held_at_permlevel_one(self):
        meta = frappe.get_meta("Person")
        for spec in registry.SPEC:
            if not spec.sensitive:
                continue
            with self.subTest(field=spec.person_field):
                self.assertEqual(meta.get_field(spec.person_field).permlevel, 1)

    def test_a_non_sensitive_attribute_is_not(self):
        meta = frappe.get_meta("Person")
        for spec in registry.SPEC:
            if spec.sensitive:
                continue
            with self.subTest(field=spec.person_field):
                self.assertFalse(meta.get_field(spec.person_field).permlevel)

    def test_the_roles_that_may_write_person_can_reach_level_one(self):
        meta = frappe.get_meta("Person")
        writers = {p.role for p in meta.permissions if not p.permlevel and p.write}
        level_one = {p.role for p in meta.permissions if p.permlevel == 1 and p.write}
        self.assertTrue(
            registry.SPEC and any(s.sensitive for s in registry.SPEC),
            "no sensitive attributes declared; this test would pass vacuously",
        )
        self.assertEqual(writers, level_one)


class TestRoutingAndPostalCountryAreSeparate(IntegrationTestCase):
    """`country` routes messaging (ADR 043); `mailing_country` is where letters
    go. One field served both until ADR 068 phase 2, so a student's
    self-service address edit could reach the SMS provider selector."""

    def test_both_fields_exist_and_are_distinct(self):
        meta = frappe.get_meta("Person")
        self.assertTrue(meta.get_field("country"))
        self.assertTrue(meta.get_field("mailing_country"))
        self.assertNotEqual(
            registry.SPEC_BY_PERSON_FIELD["country"].arg,
            registry.SPEC_BY_PERSON_FIELD["mailing_country"].arg,
        )

    def test_the_alumni_address_reads_the_postal_country(self):
        """Repointing this fetch at a field nobody had filled would have blanked
        every alumni address; the phase 2 patch seeds it from `country`."""
        df = frappe.get_meta("Alumni Profile").get_field("mailing_country")
        self.assertEqual(df.fetch_from, "person.mailing_country")

    def test_writing_the_postal_country_does_not_move_the_routing_one(self):
        """`country` is FILL_ONLY *and* Frappe auto-defaults Link-to-Country
        fields, so it is normally already set — which is precisely why writing
        an address must not reach it."""
        person = make_person("Countries")
        before = frappe.db.get_value("Person", person.name, "country")
        spine.update_person(person.name, mailing_country="Portugal")
        row = frappe.db.get_value(
            "Person", person.name, ["country", "mailing_country"], as_dict=True
        )
        self.assertEqual(row.mailing_country, "Portugal")
        self.assertEqual(row.country, before)


class TestTheSpineAcceptsAnAddress(IntegrationTestCase):
    """ADR 046 said the registrar-intake snapshot seeds the Person. It never
    did: `ensure_person` accepted no address arguments at all."""

    def test_every_registry_attribute_actually_lands(self):
        """Guards the `locals()` hand-off — a signature that accepts an
        argument but drops it on the floor is worse than one that rejects it."""
        person = make_person("Lands")
        sample = {
            "address_line_1": "12 Rua Teste",
            "address_line_2": "Apto 3",
            "city": "Recife",
            "state": "PE",
            "pincode": "50000-000",
            "phonetic_name": "REH-see-feh",
            "blood_group": "O+",
            "marital_status": "Single",
            "ethnicity": "Other",
        }
        spine.update_person(person.name, **sample)
        stored = frappe.db.get_value("Person", person.name, list(sample), as_dict=True)
        for field, value in sample.items():
            with self.subTest(field=field):
                self.assertEqual(stored.get(field), value)

    def test_an_unknown_link_value_is_not_written_on_creation_either(self):
        """`ensure_person`'s new-Person branch writes straight onto the doc
        instead of going through `_apply`, so it needs the guard of its own."""
        email = "zzt.badlink.%d@example.test" % frappe.utils.now_datetime().microsecond
        name = spine.ensure_person(
            email, first_name="ZZT Guard", nationality="Not A Country"
        )
        self.assertFalse(frappe.db.get_value("Person", name, "nationality"))

    def test_an_unknown_link_value_is_not_written_blindly(self):
        """`Student Applicant.gender` is a Select of literals against a Link to
        Gender, and `setup_genders()` enables the *translated* names."""
        person = make_person("BadLink")
        spine.update_person(person.name, nationality="Not A Country")
        self.assertFalse(
            frappe.db.get_value("Person", person.name, "nationality"),
            "a nonexistent Country was written to a Link field",
        )


class TestWriteSemantics(IntegrationTestCase):
    def test_an_authored_field_is_last_write_wins_when_authoritative(self):
        person = make_person("Authored")
        spine.update_person(person.name, last_name="Corrected", overwrite=True)
        self.assertEqual(
            frappe.db.get_value("Person", person.name, "last_name"), "Corrected"
        )

    def test_an_authored_field_only_fills_blanks_when_not_authoritative(self):
        person = make_person("FillOnly")
        original = person.last_name
        spine.update_person(person.name, last_name="Ignored")
        self.assertEqual(
            frappe.db.get_value("Person", person.name, "last_name"), original
        )

    def test_a_never_blank_field_is_never_cleared(self):
        """`first_name` is reqd on Person: an authoritative caller may change
        it, but a blank incoming value is an omission, not a correction."""
        person = make_person("Keeper")
        spine.update_person(person.name, first_name="", overwrite=True)
        self.assertTrue(frappe.db.get_value("Person", person.name, "first_name"))

    def test_a_gender_can_now_be_corrected(self):
        """It was FILL_ONLY, so `update_person(overwrite=True)` could not change
        an existing value — the gap ADR 067 stalled on. Phase 4 makes it
        AUTHORED, like the rest of the identity block."""
        self.assertEqual(
            registry.SPEC_BY_PERSON_FIELD["gender"].mode, registry.AUTHORED
        )
        genders = frappe.get_all("Gender", pluck="name", limit=2)
        if len(genders) < 2:
            self.skipTest("site has fewer than two Gender records")
        person = make_person("Gendered")
        spine.update_person(person.name, gender=genders[0], overwrite=True)
        spine.update_person(person.name, gender=genders[1], overwrite=True)
        self.assertEqual(
            frappe.db.get_value("Person", person.name, "gender"), genders[1]
        )


class TestPropagation(IntegrationTestCase):
    def test_a_spine_edit_reaches_the_role_row(self):
        person = make_person("Propagate")
        student = make_student(person)

        person.reload()
        person.last_name = "Renamed"
        person.save(ignore_permissions=True)

        row = frappe.db.get_value(
            "Student", student.name, ["last_name", "student_name"], as_dict=True
        )
        self.assertEqual(row.last_name, "Renamed")
        self.assertIn("Renamed", row.student_name)

    def test_the_spine_email_cannot_be_cleared_while_a_role_holds_it(self):
        """`Student.student_email_id` provisions the portal User and is unique.

        Since phase 4 it is `fetch_from person.primary_email`, and Frappe
        *blanks* a mirror whose source is null — so clearing the spine's email
        would strand the login on the role's next save, far from the edit that
        caused it. Refused at the Person instead.
        """
        person = make_person("NoBlank")
        student = make_student(person)
        before = frappe.db.get_value("Student", student.name, "student_email_id")
        self.assertTrue(before)

        person.reload()
        person.primary_email = None
        with self.assertRaises(frappe.ValidationError):
            person.save(ignore_permissions=True)

        self.assertEqual(
            frappe.db.get_value("Student", student.name, "student_email_id"), before
        )

    def test_a_person_with_no_role_may_still_have_no_email(self):
        """Donors, guardians and partner contacts are Persons without roles or
        logins (ADR 042 §6, ADR 048) — the guard must not reach them."""
        person = make_person("Emailless")
        person.reload()
        person.primary_email = None
        person.save(ignore_permissions=True)
        self.assertFalse(frappe.db.get_value("Person", person.name, "primary_email"))

    def test_a_blank_spine_value_is_omitted_rather_than_pushed_as_empty(self):
        """`push_blank` is the difference between a name (which may legitimately
        be cleared) and an email (where an empty spine must not wipe a unique,
        login-provisioning mirror). Before phase 3 this was observable as
        Instructor being dropped from the plan entirely; it now always carries
        `instructor_name`, so assert the field-level rule directly."""
        person = make_person("Empty")
        person.reload()
        person.primary_email = None
        person.primary_mobile = None
        plan = registry.propagation_plan(person)

        instructor = plan.get(registry.INSTRUCTOR, {})
        self.assertNotIn("prof_email", instructor)
        self.assertNotIn("phone_message", instructor)
        # A name part is pushed even when blank, so a real clear propagates.
        self.assertIn("instructor_name", instructor)
        self.assertEqual(plan[registry.STUDENT]["middle_name"], "")
