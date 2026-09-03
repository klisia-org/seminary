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
from seminary.seminary.tests.cohort_fixtures import make_person, make_student

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

    def test_gender_is_fill_only_today(self):
        """Recorded, not endorsed: this is why `update_person(overwrite=True)`
        cannot correct a gender, and it is the gap ADR 067 stalled on. Phase 4
        promotes gender to AUTHORED and this test moves with it."""
        self.assertEqual(
            registry.SPEC_BY_PERSON_FIELD["gender"].mode, registry.FILL_ONLY
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

    def test_an_empty_spine_never_blanks_a_required_mirror(self):
        """`Student.student_email_id` provisions the portal User. Pushing an
        empty spine email over it would strand the student's login."""
        person = make_person("NoBlank")
        student = make_student(person)
        before = frappe.db.get_value("Student", student.name, "student_email_id")
        self.assertTrue(before)

        person.reload()
        person.primary_email = None
        person.save(ignore_permissions=True)

        self.assertEqual(
            frappe.db.get_value("Student", student.name, "student_email_id"), before
        )

    def test_the_plan_skips_a_doctype_with_nothing_to_push(self):
        person = make_person("Empty")
        person.reload()
        person.primary_email = None
        person.primary_mobile = None
        plan = registry.propagation_plan(person)
        # Instructor's only propagated bindings are email and mobile.
        self.assertNotIn(registry.INSTRUCTOR, plan)
