# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""The dimension vocabulary is a set of stable keys, and these tests say so.

`dimension_code` is stored as a string by every competency descriptor, weight
and grade rather than as a link to the Grading Scale row that defines it
(ADR 065 section 1), because a reporting axis has to survive the scale being
amended and has to stay comparable across scales. The cost of that choice is
that Frappe will not cascade a rename, so nothing but a guard stops an author
from detaching live records with one edit. That guard is what is under test
here, together with the shared validator every storer of a code now goes
through.
"""

import frappe
from frappe.tests import IntegrationTestCase

PREFIX = "ZZ DIMVOC"

DIMENSIONS = [
    {"dimension": "Knowledge", "dimension_code": "knowledge", "sequence": 1},
    {"dimension": "Character", "dimension_code": "character", "sequence": 2},
]

# `grade_pass` says whether an interval is a passing grade. B105 matches the
# `pass` in the key name and reads the value as a credential, so every row needs
# the annotation.
INTERVALS = [
    {"grade_code": "4", "threshold": 4.0, "grade_pass": "Pass"},  # nosec B105
    {"grade_code": "3", "threshold": 3.0, "grade_pass": "Pass"},  # nosec B105
    {"grade_code": "2", "threshold": 2.0, "grade_pass": "Fail"},  # nosec B105
    {"grade_code": "1", "threshold": 1.0, "grade_pass": "Fail"},  # nosec B105
]


class TestDimensionVocabulary(IntegrationTestCase):
    def setUp(self):
        self._purge()
        # The scale stays a draft on purpose: `gradingscaledimensions` is not
        # allow_on_submit, so a submitted scale cannot reach the guard at all.
        self.scale = frappe.get_doc(
            {
                "doctype": "Grading Scale",
                "grading_scale_name": f"{PREFIX} CBE",
                "grscale_type": "Competency-based education",
                "maxnumgrade": 4.0,
                "intervals": list(INTERVALS),
                "gradingscaledimensions": [dict(d) for d in DIMENSIONS],
            }
        )
        self.scale.flags.ignore_permissions = True
        self.scale.insert()

        self.course = frappe.get_doc(
            {
                "doctype": "Course",
                "course_name": f"{PREFIX} Formation",
                "coursecode": "ZZDIMVOC1",
                "default_grading_scale": self.scale.name,
            }
        )
        self.course.flags.ignore_permissions = True
        self.course.insert()

    def tearDown(self):
        self._purge()

    def _purge(self):
        for dt, field in (
            ("Course Competency", "course"),
            ("Course", "course_name"),
            ("Grading Scale", "grading_scale_name"),
        ):
            for name in frappe.get_all(
                dt, filters={field: ("like", f"{PREFIX}%")}, pluck="name"
            ):
                frappe.db.set_value(dt, name, "docstatus", 0, update_modified=False)
                frappe.delete_doc(
                    dt,
                    name,
                    force=True,
                    ignore_permissions=True,
                    delete_permanently=True,
                )
        frappe.db.commit()

    def _competency(self, codes=("knowledge", "character")):
        doc = frappe.get_doc(
            {
                "doctype": "Course Competency",
                "course": self.course.name,
                "competency_code": "LIC",
                "competency_name": "Life in Christ",
                "statement": "<p>Lives attentively before God.</p>",
                "sequence": 1,
                "is_active": 1,
                "dimensions": [
                    {
                        "dimension_code": code,
                        "demonstrated_by": f"<p>Shows {code}.</p>",
                    }
                    for code in codes
                ],
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert()
        return doc

    def _rename_dimension(self, old, new):
        scale = frappe.get_doc("Grading Scale", self.scale.name)
        for row in scale.gradingscaledimensions:
            if row.dimension_code == old:
                row.dimension_code = new
        scale.flags.ignore_permissions = True
        scale.save()
        return scale

    # ---------------------------------------------------------------- the guard

    def test_rename_blocked_while_a_descriptor_uses_the_code(self):
        self._competency()
        with self.assertRaises(frappe.ValidationError) as caught:
            self._rename_dimension("character", "formation")
        message = str(caught.exception)
        self.assertIn("character", message)
        self.assertIn("competency descriptors", message)

    def test_removing_a_used_dimension_is_blocked_too(self):
        """A delete orphans exactly what a rename does, so it fails the same way."""
        self._competency()
        scale = frappe.get_doc("Grading Scale", self.scale.name)
        scale.gradingscaledimensions = [
            r for r in scale.gradingscaledimensions if r.dimension_code != "character"
        ]
        scale.flags.ignore_permissions = True
        with self.assertRaises(frappe.ValidationError):
            scale.save()

    def test_rename_allowed_when_nothing_stores_the_code(self):
        self._competency(codes=("knowledge",))
        scale = self._rename_dimension("character", "formation")
        self.assertEqual(
            {r.dimension_code for r in scale.gradingscaledimensions},
            {"knowledge", "formation"},
        )

    def test_label_may_change_while_the_code_is_in_use(self):
        """Only the key is guarded -- renaming the human label is always allowed."""
        competency = self._competency()
        scale = frappe.get_doc("Grading Scale", self.scale.name)
        for row in scale.gradingscaledimensions:
            if row.dimension_code == "character":
                row.dimension = "Character & Formation"
        scale.flags.ignore_permissions = True
        scale.save()

        # And the denormalised label follows on the competency's next save.
        competency.reload()
        competency.flags.ignore_permissions = True
        competency.save()
        labels = {r.dimension_code: r.dimension for r in competency.dimensions}
        self.assertEqual(labels["character"], "Character & Formation")

    def test_guard_is_scoped_to_this_scale(self):
        """Another scale's records must not freeze this scale's vocabulary."""
        other = frappe.get_doc(
            {
                "doctype": "Grading Scale",
                "grading_scale_name": f"{PREFIX} CBE Two",
                "grscale_type": "Competency-based education",
                "maxnumgrade": 4.0,
                "intervals": list(INTERVALS),
                "gradingscaledimensions": [dict(d) for d in DIMENSIONS],
            }
        )
        other.flags.ignore_permissions = True
        other.insert()

        # The competency hangs off `self.course`, which uses `self.scale`.
        self._competency()

        for row in other.gradingscaledimensions:
            if row.dimension_code == "character":
                row.dimension_code = "formation"
        other.save()
        self.assertIn(
            "formation", {r.dimension_code for r in other.gradingscaledimensions}
        )

    # ------------------------------------------------------- the shared validator

    def test_unknown_code_is_refused_and_names_the_scale(self):
        with self.assertRaises(frappe.ValidationError) as caught:
            self._competency(codes=("knowledge", "craft"))
        message = str(caught.exception)
        self.assertIn("craft", message)
        self.assertIn(self.scale.name, message)

    def test_duplicate_dimension_rows_are_refused(self):
        with self.assertRaises(frappe.ValidationError) as caught:
            self._competency(codes=("knowledge", "knowledge"))
        self.assertIn("appears in rows", str(caught.exception))

    def test_label_is_stamped_from_the_scale_not_the_author(self):
        competency = self._competency(codes=("knowledge",))
        self.assertEqual(competency.dimensions[0].dimension, "Knowledge")
