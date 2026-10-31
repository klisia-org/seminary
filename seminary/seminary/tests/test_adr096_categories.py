# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/096: weighted categories, dropped scores and excused assessments."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import api, gradebook_weights as gw
from seminary.seminary.tests import cohort_fixtures as fx


def _r(name, weight=0, cat=None, score=None, due=None, **extra):
    return {
        "name": name,
        "weight_scac": weight,
        "category_code": cat,
        "due_date": due,
        "score": score or 0,
        "graded": 1 if score is not None else 0,
        **extra,
    }


QUIZ_PAPER = [
    {"category_code": "quizzes", "title": "Quizzes", "weight": 40, "drop_lowest": 1},
    {"category_code": "papers", "title": "Papers", "weight": 60, "drop_lowest": 0},
]


def weights(out):
    return {k: round(v["weight"], 4) for k, v in out.items()}


class TestCompute(IntegrationTestCase):
    def test_no_categories_keeps_each_rows_weight(self):
        rows = [_r("a", 30, score=80), _r("b", 70, score=90)]
        self.assertEqual(weights(gw.compute(rows, [])), {"a": 30, "b": 70})

    def test_no_categories_excused_weight_spreads_in_proportion(self):
        rows = [_r("a", 20), _r("b", 30), _r("c", 50, excused=1)]
        out = gw.compute(rows, [])
        self.assertEqual(weights(out), {"a": 40, "b": 60, "c": 0})
        self.assertEqual(out["c"]["status"], gw.EXCUSED)

    def test_blank_rows_share_their_category(self):
        rows = [_r(f"q{i}", cat="quizzes") for i in range(4)] + [_r("p", cat="papers")]
        cats = [dict(c, drop_lowest=0) for c in QUIZ_PAPER]
        self.assertEqual(
            weights(gw.compute(rows, cats)),
            {"q0": 10, "q1": 10, "q2": 10, "q3": 10, "p": 60},
        )

    def test_typed_weight_is_a_percent_of_the_category(self):
        rows = [_r("q1", 50, "quizzes"), _r("q2", 0, "quizzes"), _r("q3", 0, "quizzes")]
        cats = [{"category_code": "quizzes", "weight": 100, "drop_lowest": 0}]
        self.assertEqual(
            weights(gw.compute(rows, cats)), {"q1": 50, "q2": 25, "q3": 25}
        )

    def test_lowest_drops_and_the_rest_share_again(self):
        rows = [
            _r("q1", cat="quizzes", score=90),
            _r("q2", cat="quizzes", score=40),
            _r("q3", cat="quizzes", score=70),
            _r("p", cat="papers", score=80),
        ]
        out = gw.compute(rows, QUIZ_PAPER)
        self.assertEqual(weights(out), {"q1": 20, "q2": 0, "q3": 20, "p": 60})
        self.assertEqual(out["q2"]["status"], gw.DROPPED)

    def test_never_drop_is_skipped_for_the_next_lowest(self):
        rows = [
            _r("q1", cat="quizzes", score=90),
            _r("q2", cat="quizzes", score=40, never_drop=1),
            _r("q3", cat="quizzes", score=70),
            _r("p", cat="papers", score=80),
        ]
        out = gw.compute(rows, QUIZ_PAPER)
        self.assertEqual(out["q3"]["status"], gw.DROPPED)
        self.assertIsNone(out["q2"]["status"])

    def test_a_tie_drops_the_earlier_due_date(self):
        rows = [
            _r("late", cat="quizzes", score=50, due="2026-03-09 10:00:00"),
            _r("early", cat="quizzes", score=50, due="2026-03-02 10:00:00"),
            _r("p", cat="papers", score=80),
        ]
        self.assertEqual(gw.compute(rows, QUIZ_PAPER)["early"]["status"], gw.DROPPED)

    def test_ungraded_drops_only_at_send(self):
        rows = [
            _r("q1", cat="quizzes", score=60),
            _r("q2", cat="quizzes", score=None),
            _r("p", cat="papers", score=80),
        ]
        live = gw.compute(rows, QUIZ_PAPER)
        self.assertEqual(live["q1"]["status"], gw.DROPPED)
        self.assertIsNone(live["q2"]["status"])
        final = gw.compute(rows, QUIZ_PAPER, final=True)
        self.assertEqual(final["q2"]["status"], gw.DROPPED)

    def test_one_row_always_counts(self):
        rows = [_r("q1", cat="quizzes", score=60), _r("p", cat="papers", score=80)]
        self.assertIsNone(gw.compute(rows, QUIZ_PAPER)["q1"]["status"])

    def test_an_excuse_is_not_a_drop(self):
        rows = [
            _r("q1", cat="quizzes", score=90),
            _r("q2", cat="quizzes", score=40),
            _r("q3", cat="quizzes", excused=1),
            _r("p", cat="papers", score=80),
        ]
        out = gw.compute(rows, QUIZ_PAPER)
        self.assertEqual(out["q3"]["status"], gw.EXCUSED)
        self.assertEqual(out["q2"]["status"], gw.DROPPED)
        self.assertEqual(weights(out)["q1"], 40)

    def test_an_empty_category_gives_its_weight_to_the_others(self):
        rows = [
            _r("q1", cat="quizzes", excused=1),
            _r("p1", cat="papers", score=80),
            _r("p2", cat="papers", score=70),
        ]
        self.assertEqual(
            weights(gw.compute(rows, QUIZ_PAPER)), {"q1": 0, "p1": 50, "p2": 50}
        )

    def test_extra_credit_is_left_out(self):
        rows = [_r("a", 100, score=80), _r("x", 0, extracredit_scac=1)]
        self.assertNotIn("x", gw.compute(rows, []))

    def test_nominal_ignores_scores_and_excuses(self):
        rows = [
            _r("q1", cat="quizzes", score=10, excused=1),
            _r("q2", cat="quizzes", score=90),
            _r("p", cat="papers"),
        ]
        self.assertEqual(
            {k: round(v, 4) for k, v in gw.nominal(rows, QUIZ_PAPER).items()},
            {"q1": 20, "q2": 20, "p": 60},
        )


def _cat(code, weight, drop=0, title=None):
    return frappe._dict(
        category_code=code, title=title or code, weight=weight, drop_lowest=drop
    )


def _row(title, weight=0, cat=None, **extra):
    return frappe._dict(
        title=title,
        weight_scac=weight,
        category_code=cat,
        extracredit_scac=extra.pop("extracredit_scac", 0),
        never_drop=extra.pop("never_drop", 0),
    )


class TestValidate(IntegrationTestCase):
    def test_weights_must_total_100(self):
        with self.assertRaises(frappe.ValidationError):
            gw.validate(
                [_cat("a", 50), _cat("b", 40)], [_row("x", cat="a"), _row("y", cat="b")]
            )

    def test_every_regular_row_needs_a_category(self):
        with self.assertRaises(frappe.ValidationError):
            gw.validate([_cat("a", 100)], [_row("x", cat="a"), _row("y")])
        gw.validate(
            [_cat("a", 100)], [_row("x", cat="a"), _row("bonus", extracredit_scac=1)]
        )

    def test_drop_must_leave_one_that_counts(self):
        rows = [_row("q1", cat="a"), _row("q2", cat="a", never_drop=1)]
        with self.assertRaises(frappe.ValidationError):
            gw.validate([_cat("a", 100, drop=1)], rows)
        gw.validate([_cat("a", 100, drop=1)], rows + [_row("q3", cat="a")])

    def test_typed_weights_must_leave_room_for_blank_ones(self):
        with self.assertRaises(frappe.ValidationError):
            gw.validate([_cat("a", 100)], [_row("q1", 100, "a"), _row("q2", 0, "a")])

    def test_codes_fill_from_titles_and_stay_unique(self):
        cats = [_cat(None, 50, title="Quizzes"), _cat(None, 50, title="Quizzes")]
        gw.fill_codes(cats)
        self.assertEqual([c.category_code for c in cats], ["quizzes", "quizzes-2"])


# --- through the gradebook ------------------------------------------------------


def _scale():
    doc = frappe.get_doc(
        {
            "doctype": "Grading Scale",
            "name": fx.uid("GS"),
            "grading_scale_name": fx.uid("GS"),
            "grscale_type": "Points",
            "maxnumgrade": 100,
        }
    )
    doc.db_insert()
    return doc.name


class ADR096Case(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.student = fx.make_student()
        self.cs = frappe.get_doc(
            {
                "doctype": "Course Schedule",
                "name": fx.uid("CS"),
                "workflow_state": "Grading",
                "open_ended": 1,
                "gradesc_cs": _scale(),
                "maxnumgrade": 100,
            }
        )
        self.cs.db_insert()
        for idx, c in enumerate(QUIZ_PAPER, 1):
            frappe.get_doc(
                {
                    "doctype": "Scheduled Course Assess Category",
                    "parent": self.cs.name,
                    "parenttype": "Course Schedule",
                    "parentfield": "assess_categories",
                    "idx": idx,
                    **c,
                }
            ).db_insert()
        self.rows = {}
        for idx, (key, cat, due) in enumerate(
            [
                ("q1", "quizzes", "2026-03-02"),
                ("q2", "quizzes", "2026-03-09"),
                ("q3", "quizzes", "2026-03-16"),
                ("p1", "papers", "2026-03-20"),
            ],
            1,
        ):
            row = frappe.get_doc(
                {
                    "doctype": "Scheduled Course Assess Criteria",
                    "name": fx.uid("SCAC"),
                    "parent": self.cs.name,
                    "parenttype": "Course Schedule",
                    "parentfield": "courseassescrit_sc",
                    "idx": idx,
                    "title": key,
                    "type": "Offline",
                    "weight_scac": 0,
                    "category_code": cat,
                    "due_date": due,
                }
            )
            row.db_insert()
            self.rows[key] = row.name
        self.roster = frappe.get_doc(
            {
                "doctype": "Scheduled Course Roster",
                "name": f"{self.cs.name}-{self.student.name}",
                "course_sc": self.cs.name,
                "student": self.student.name,
                "stuname_roster": self.student.name,
                "active": 1,
                "audit_bool": 0,
            }
        )
        self.roster.db_insert()
        self.cards = {}
        for key, row in self.rows.items():
            card = frappe.get_doc(
                {
                    "doctype": "Course Assess Results Detail",
                    "name": frappe.generate_hash(length=10),
                    "parent": self.roster.name,
                    "parenttype": "Scheduled Course Roster",
                    "parentfield": "stdroster_grade",
                    "assessment_criteria": row,
                    "student_card": self.student.name,
                    "maximum_score": 0,
                }
            )
            card.db_insert()
            self.cards[key] = card.name

    def grade(self, **scores):
        for key, score in scores.items():
            frappe.db.set_value(
                "Course Assess Results Detail",
                self.cards[key],
                {"rawscore_card": score, "graded_card": 1},
            )

    def card(self, key, *fields):
        return frappe.db.get_value(
            "Course Assess Results Detail", self.cards[key], list(fields), as_dict=True
        )


class TestGrading(ADR096Case):
    def test_final_score_drops_the_lowest_quiz(self):
        self.grade(q1=90, q2=40, q3=70, p1=80)
        api._grade_thisstudent(self.roster.name)
        api._fgrade_this_std(self.roster.name)
        # Quizzes 40% over 90 and 70, papers 60% at 80: 18 + 14 + 48.
        self.assertAlmostEqual(
            frappe.db.get_value("Scheduled Course Roster", self.roster.name, "fscore"),
            80,
        )
        self.assertEqual(self.card("q2", "dropped_card").dropped_card, 1)
        self.assertAlmostEqual(self.card("q1", "maximum_score").maximum_score, 20)

    def test_refresh_writes_the_live_weights(self):
        self.grade(q1=90, q2=40)
        gw.refresh_roster(self.roster.name)
        self.assertEqual(self.card("q2", "dropped_card").dropped_card, 1)
        # q3 is not graded yet, so it counts and cannot be the one dropped.
        self.assertAlmostEqual(self.card("q3", "maximum_score").maximum_score, 20)

    def test_excusing_reweighs_and_needs_a_reason(self):
        with self.assertRaises(frappe.ValidationError):
            gw.set_excused(self.cards["p1"], 1)
        gw.set_excused(self.cards["p1"], 1, "Family emergency")
        p1 = self.card("p1", "excused", "maximum_score")
        self.assertEqual((p1.excused, p1.maximum_score), (1, 0))
        # Papers has nothing left, so its 60% goes to the quizzes.
        self.assertAlmostEqual(
            self.card("q1", "maximum_score").maximum_score, 100 / 3, 3
        )

    def test_an_excused_card_does_not_block_sending(self):
        self.grade(q1=90, q2=40, q3=70)
        self.assertEqual(api._ungraded_roster_count(self.cs.name), 1)
        gw.set_excused(self.cards["p1"], 1, "Accommodation")
        self.assertEqual(api._ungraded_roster_count(self.cs.name), 0)

    def test_sent_grades_are_frozen(self):
        self.grade(q1=90, q2=40, q3=70, p1=80)
        api._grade_thisstudent(self.roster.name)
        frappe.db.set_value("Scheduled Course Roster", self.roster.name, "active", 0)
        frappe.db.set_value(
            "Scheduled Course Assess Category",
            {"parent": self.cs.name, "category_code": "quizzes"},
            "drop_lowest",
            0,
        )
        gw.refresh_section(self.cs.name)
        self.assertEqual(self.card("q2", "dropped_card").dropped_card, 1)
        with self.assertRaises(frappe.ValidationError):
            gw.set_excused(self.cards["q1"], 1, "Too late")

    def test_projection_leaves_out_the_dropped_quiz(self):
        from seminary.seminary.grade_projection import compute, section_assessments

        self.grade(q1=90, q2=40, q3=70, p1=80)
        rows = section_assessments(self.cs.name, [self.roster.name])[self.roster.name]
        # 90 and 70 at 20% each, 80 at 60%: the 40 is not counted.
        self.assertAlmostEqual(compute(rows, [], 100)["current"]["score"], 80)

    def test_template_import_copies_categories(self):
        from seminary.seminary.doctype.course_schedule.course_schedule import (
            _SCAC_COPYABLE_FIELDS,
            _copy_categories,
        )

        target = frappe.get_doc(
            {
                "doctype": "Course Schedule",
                "name": fx.uid("CS"),
                "gradesc_cs": self.cs.gradesc_cs,
            }
        )
        target.db_insert()
        _copy_categories(self.cs.name, target.name)
        self.assertEqual(
            [c.category_code for c in gw.section_categories(target.name)],
            ["quizzes", "papers"],
        )
        self.assertIn("category_code", _SCAC_COPYABLE_FIELDS)
        self.assertIn("never_drop", _SCAC_COPYABLE_FIELDS)
