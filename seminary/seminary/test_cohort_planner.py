# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""The cohort planner's pools, rules and matcher (ADR 067 phases H and I).

Everything asserted here is server-side and writes nothing, which is the point
of building it before the page: a proposal is a pure function of the site's data,
so it can be run, inspected and thrown away.

Deliberately outside the doctype folder, for the same reason `test_cohort_policy`
is: `IntegrationTestCase.setUpClass` only calls `make_test_records` for modules
in a doctype directory, and this graph reaches erpnext's `Company` several ways
over.
"""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.discipleship import criteria as rules
from seminary.seminary.discipleship import planner
from seminary.seminary.tests import cohort_fixtures as fx


def _resolve_point(person, lat, lon):
    """A Person with a usable coordinate.

    Set with `db.set_value` rather than a save: the fields are permlevel 1 and
    written by the geocoder, and `geo_status` -- not latitude -- is the presence
    signal, because a Float column is NOT NULL DEFAULT 0 and an unresolved point
    reads as 0.0, 0.0.
    """
    frappe.db.set_value(
        "Person",
        person,
        {"latitude": lat, "longitude": lon, "geo_status": "Resolved"},
        update_modified=False,
    )


def _gender(person, value):
    if not frappe.db.exists("Gender", value):
        frappe.get_doc({"doctype": "Gender", "gender": value}).insert(
            ignore_permissions=True
        )
    frappe.db.set_value("Person", person, "gender", value, update_modified=False)


class PlannerCase(IntegrationTestCase):
    """A program, a mentoring unit, and a plannable type over both."""

    def setUp(self):
        super().setUp()
        self.program = fx.make_program()
        self.unit = fx.make_mentoring_unit()

    def make_type(self, **kw):
        values = {
            "category": "Throughout Program",
            "program": self.program.name,
            "plannable": 1,
            "mentor_unit": self.unit.name,
        }
        values.update(kw)
        return fx.make_cohort_type(**values)

    def enrolled_student(self, gender=None, point=None):
        student = fx.make_student()
        fx.make_enrollment(student, self.program)
        if gender:
            _gender(student.person, gender)
        if point:
            _resolve_point(student.person, *point)
        return student

    def mentor(self, gender=None, point=None, max_students=0):
        instructor = fx.make_instructor()
        fx.seat_mentor(self.unit, instructor, max_students=max_students)
        if gender:
            _gender(instructor.person, gender)
        if point:
            _resolve_point(instructor.person, *point)
        return instructor


class TestGroupCount(IntegrationTestCase):
    """How many cohorts to open, decided before anybody is placed.

    This is the arithmetic that answers the question the on-enrollment trigger
    could not: with one student in hand you cannot know whether a group of two
    becomes a group of eight.
    """

    def test_the_ceiling_sets_the_count(self):
        self.assertEqual(planner.group_count(10, 4, 6), 2)
        self.assertEqual(planner.group_count(100, 4, 6), 17)

    def test_the_floor_wins_when_they_disagree(self):
        """An oversized group is a warning; an undersized one does not work."""
        # Six students would fit in one group of six; the floor agrees.
        self.assertEqual(planner.group_count(6, 4, 6), 1)
        # Seven would need two groups by the ceiling, but the second would hold
        # one person, so one group of seven is proposed instead.
        self.assertEqual(planner.group_count(7, 4, 6), 1)

    def test_too_few_students_still_get_one_group(self):
        """Three students and ten mentors is one flagged group, not three pairs
        -- which is what mentor-first greedy would have produced."""
        self.assertEqual(planner.group_count(3, 4, 6), 1)

    def test_zero_means_unbounded_on_either_side(self):
        self.assertEqual(planner.group_count(10, 0, 0), 1)
        self.assertEqual(planner.group_count(10, 0, 4), 3)
        self.assertEqual(planner.group_count(10, 4, 0), 1)

    def test_no_students_no_groups(self):
        self.assertEqual(planner.group_count(0, 4, 6), 0)


class TestTheCatalogGuardsItsHandlers(IntegrationTestCase):
    """`handler` is code, not configuration.

    A free-text dotted path an admin can type is remote code execution by form
    field, so `read_only` on the form is backed by a check that a REST insert
    also passes through.
    """

    def test_an_unknown_handler_is_refused(self):
        doc = frappe.get_doc(
            {
                "doctype": "Cohort Assignment Criterion",
                "handler": "os.system",
                "criterion_name": fx.uid("Evil"),
                "kind": "Filter",
            }
        )
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("not a rule this system knows", str(ctx.exception))

    def test_the_kind_comes_from_the_code_not_the_form(self):
        """A Ranking recorded as a Filter would be ANDed into the pool, where it
        can only ever answer yes."""
        doc = frappe.get_doc("Cohort Assignment Criterion", "nearest_mentor")
        doc.kind = "Filter"
        doc.save(ignore_permissions=True)
        self.assertEqual(doc.kind, "Ranking")

    def test_both_shipped_rules_are_seeded(self):
        for handler in ("match_gender", "nearest_mentor"):
            with self.subTest(handler=handler):
                self.assertTrue(
                    frappe.db.exists("Cohort Assignment Criterion", handler)
                )


class TestStudentScopes(PlannerCase):
    """All / Never / No longer -- every one a subset of "needs placement"."""

    def setUp(self):
        super().setUp()
        self.type = self.make_type()
        self.fresh = self.enrolled_student()
        self.former = self.enrolled_student()
        self.placed = self.enrolled_student()

        leader = fx.make_person("Leader", user=fx.make_user().name)
        cohort = fx.make_cohort(self.type.name, leader.name)
        fx.add_member(cohort.name, self.placed.person)
        left = fx.add_member(cohort.name, self.former.person)
        left.invite_status = "Left"
        left.save(ignore_permissions=True)

    def _persons(self, scope):
        return {
            row["person"]
            for row in planner.students_needing_placement(self.type.name, scope)
        }

    def test_an_active_member_is_never_offered(self):
        """Placement happens once, so the pool query is the guard -- no marker
        and nothing to protect a hand-moved member from."""
        for scope in planner.SCOPES:
            with self.subTest(scope=scope):
                self.assertNotIn(self.placed.person, self._persons(scope))

    def test_all_offers_everyone_needing_placement(self):
        found = self._persons(planner.SCOPE_ALL)
        self.assertIn(self.fresh.person, found)
        self.assertIn(self.former.person, found)

    def test_never_excludes_anyone_who_has_been_a_member(self):
        found = self._persons(planner.SCOPE_NEVER)
        self.assertIn(self.fresh.person, found)
        self.assertNotIn(self.former.person, found)

    def test_former_offers_only_the_re_placements(self):
        found = self._persons(planner.SCOPE_FORMER)
        self.assertIn(self.former.person, found)
        self.assertNotIn(self.fresh.person, found)

    def test_an_unknown_scope_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            planner.students_needing_placement(self.type.name, "everyone")


class TestMentorPool(PlannerCase):
    def test_a_mentor_at_their_ceiling_is_not_offered(self):
        self.mentor()
        full = self.mentor(max_students=2)
        frappe.db.sql(
            """
            UPDATE `tabAcademic Unit Capability` c
            JOIN `tabAcademic Unit Membership` m ON m.name = c.parent
            SET c.current_students = 2
            WHERE m.instructor = %s
            """,
            full.name,
        )
        offered = {m["instructor"] for m in planner.mentor_pool(self.unit.name)}
        self.assertNotIn(full.name, offered)

    def test_an_excluded_mentor_is_dropped_for_this_run_only(self):
        """A mentor on sabbatical is excluded here, not by editing their
        capability row -- the run is an experiment, the row is policy."""
        keep = self.mentor()
        drop = self.mentor()
        offered = {
            m["instructor"]
            for m in planner.mentor_pool(self.unit.name, exclude=[drop.name])
        }
        self.assertEqual(offered, {keep.name})
        self.assertIn(
            drop.name, {m["instructor"] for m in planner.mentor_pool(self.unit.name)}
        )

    def test_the_pool_carries_the_person_not_only_the_instructor(self):
        """A Cohort's leader is a Person, and every rule reads Person fields."""
        instructor = self.mentor()
        row = planner.mentor_pool(self.unit.name)[0]
        self.assertEqual(row["person"], instructor.person)


class TestFilters(PlannerCase):
    def test_gender_matching_narrows_the_pool(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        student = self.enrolled_student(gender="Female")
        self.mentor(gender="Male")
        match = self.mentor(gender="Female")

        plan = planner.propose(t.name)
        seated = {
            m["person"]: g["mentor"] for g in plan["groups"] for m in g["members"]
        }
        self.assertEqual(seated.get(student.person), match.name)

    def test_a_student_the_filter_cannot_place_is_reported_with_a_reason(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        student = self.enrolled_student(gender="Female")
        self.mentor(gender="Male")

        plan = planner.propose(t.name)
        unplaced = {u["person"]: u["reason"] for u in plan["unplaced"]}
        self.assertIn(student.person, unplaced)
        self.assertIn("not the same gender", unplaced[student.person])

    def test_a_student_with_no_gender_is_unplaced_not_mismatched(self):
        """The reason has to name the datum to fix; "no mentor matched" is not
        one."""
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        student = self.enrolled_student()
        self.mentor(gender="Female")

        plan = planner.propose(t.name)
        unplaced = {u["person"]: u["reason"] for u in plan["unplaced"]}
        self.assertIn("gender is not recorded", unplaced[student.person])

    def test_a_retired_criterion_stops_deciding_placements(self):
        """`is_active` is how a school withdraws a rule. Honouring it only in
        the picker would leave it quietly running."""
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        student = self.enrolled_student(gender="Female")
        self.mentor(gender="Male")

        frappe.db.set_value(
            "Cohort Assignment Criterion", "match_gender", "is_active", 0
        )
        plan = planner.propose(t.name)
        frappe.db.set_value(
            "Cohort Assignment Criterion", "match_gender", "is_active", 1
        )
        self.assertFalse(plan["unplaced"])
        self.assertEqual(plan["groups"][0]["members"][0]["person"], student.person)


class TestRankings(PlannerCase):
    def test_the_nearest_mentor_wins(self):
        t = self.make_type(
            criteria=[{"criterion": "nearest_mentor"}], automation_max_size=1
        )
        student = self.enrolled_student(point=(-23.55, -46.63))
        near = self.mentor(point=(-23.56, -46.64))
        self.mentor(point=(-30.03, -51.23))

        plan = planner.propose(t.name)
        self.assertEqual(plan["groups"][0]["mentor"], near.name)
        self.assertEqual(plan["groups"][0]["members"][0]["person"], student.person)

    def test_a_mentor_without_a_point_sorts_last_rather_than_infinitely_far(self):
        t = self.make_type(
            criteria=[{"criterion": "nearest_mentor"}], automation_max_size=1
        )
        self.enrolled_student(point=(-23.55, -46.63))
        far = self.mentor(point=(-30.03, -51.23))
        self.mentor()  # no resolved address at all

        plan = planner.propose(t.name)
        self.assertEqual(plan["groups"][0]["mentor"], far.name)

    def test_the_note_says_what_moving_the_student_would_cost(self):
        """A bare distance is not a decision aid; the comparison is.

        Two students and a ceiling of one, so two groups open and there is
        somewhere to move to. The comparison is against the other *group*, not
        against the pool -- a mentor leading no cohort is not a destination.
        """
        t = self.make_type(
            criteria=[{"criterion": "nearest_mentor"}], automation_max_size=1
        )
        self.enrolled_student(point=(-23.55, -46.63))
        self.enrolled_student(point=(-30.03, -51.23))
        self.mentor(point=(-23.56, -46.64))
        self.mentor(point=(-30.04, -51.24))

        plan = planner.propose(t.name)
        note = " ".join(plan["groups"][0]["members"][0]["notes"])
        self.assertIn("next nearest mentor", note)

    def test_with_one_group_the_note_says_there_is_nowhere_else(self):
        t = self.make_type(criteria=[{"criterion": "nearest_mentor"}])
        self.enrolled_student(point=(-23.55, -46.63))
        self.mentor(point=(-23.56, -46.64))

        plan = planner.propose(t.name)
        note = " ".join(plan["groups"][0]["members"][0]["notes"])
        self.assertIn("no other mentor", note)

    def test_a_ranking_never_empties_the_pool(self):
        """ANDing a ranking would be meaningless -- it orders, it does not
        refuse. A student with no coordinate is still placed."""
        t = self.make_type(criteria=[{"criterion": "nearest_mentor"}])
        student = self.enrolled_student()
        self.mentor(point=(-23.56, -46.64))

        plan = planner.propose(t.name)
        self.assertFalse(plan["unplaced"])
        self.assertEqual(plan["groups"][0]["members"][0]["person"], student.person)


class TestDistanceRendering(IntegrationTestCase):
    def test_kilometres_and_miles(self):
        rules.using_unit(rules.KM)
        self.assertIn("km", rules.format_distance(10))
        rules.using_unit(rules.MILES)
        rendered = rules.format_distance(rules._KM_PER_MILE)
        self.assertIn("mi", rendered)
        self.assertIn("1.0", rendered)
        rules.using_unit(rules.KM)

    def test_haversine_is_symmetric_and_zero_at_a_point(self):
        self.assertEqual(rules.haversine_km(10, 20, 10, 20), 0)
        self.assertAlmostEqual(
            rules.haversine_km(-23.55, -46.63, -30.03, -51.23),
            rules.haversine_km(-30.03, -51.23, -23.55, -46.63),
        )


class TestProposalShape(PlannerCase):
    def test_a_proposal_writes_nothing(self):
        """The page treats a proposal as disposable, which is only safe if it
        is."""
        t = self.make_type()
        self.enrolled_student()
        self.mentor()
        before = frappe.db.count("Cohort"), frappe.db.count("Cohort Membership")
        planner.propose(t.name)
        self.assertEqual(
            (frappe.db.count("Cohort"), frappe.db.count("Cohort Membership")), before
        )

    def test_an_undersized_group_is_flagged_and_still_proposed(self):
        t = self.make_type(automation_min_size=4, automation_max_size=6)
        for _i in range(3):
            self.enrolled_student()
        for _i in range(10):
            self.mentor()

        plan = planner.propose(t.name)
        self.assertEqual(len(plan["groups"]), 1)
        self.assertTrue(plan["groups"][0]["below_minimum"])
        self.assertEqual(plan["groups"][0]["size"], 3)

    def test_every_member_carries_what_proposed_them(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        self.enrolled_student(gender="Female")
        self.mentor(gender="Female")

        plan = planner.propose(t.name)
        stamp = plan["groups"][0]["members"][0]["placed_by_rule"]
        self.assertIn("Match student and mentor gender", stamp)

    def test_the_payload_carries_each_student_s_shortlist(self):
        """So a drag recomputes the notes without a round trip.

        The shortlist is the *opened groups* in preference order, not the whole
        mentor pool: those are the only places a chair can drag a student to.
        """
        t = self.make_type(
            criteria=[{"criterion": "nearest_mentor"}], automation_max_size=1
        )
        near = self.enrolled_student(point=(-23.55, -46.63))
        self.enrolled_student(point=(-30.03, -51.23))
        a = self.mentor(point=(-23.56, -46.64))
        b = self.mentor(point=(-30.04, -51.24))

        plan = planner.propose(t.name)
        self.assertEqual(len(plan["groups"]), 2)
        self.assertEqual(plan["shortlists"][near.person], [a.person, b.person])

    def test_capacity_reaches_the_client_as_json(self):
        """An uncapped capability is `float("inf")` internally, and Python
        serialises that as the bare token `Infinity` -- which `JSON.parse`
        rejects, so the whole proposal would arrive as a parse error."""
        import json

        t = self.make_type()
        self.enrolled_student()
        self.mentor()
        plan = planner.propose(t.name)
        self.assertIsNone(plan["groups"][0]["remaining"])
        json.loads(json.dumps(plan, allow_nan=False))

    def test_a_run_may_deviate_from_the_type_s_rules_without_changing_them(self):
        """Trying the intake with and without a rule is an experiment, not an
        amendment."""
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        student = self.enrolled_student(gender="Female")
        self.mentor(gender="Male")

        self.assertTrue(planner.propose(t.name)["unplaced"])
        plan = planner.propose(t.name, handlers=[])
        self.assertFalse(plan["unplaced"])
        self.assertEqual(plan["groups"][0]["members"][0]["person"], student.person)

        t.reload()
        self.assertEqual([r.criterion for r in t.criteria], ["match_gender"])

    def test_a_type_that_is_not_plannable_is_refused(self):
        t = fx.make_cohort_type(
            category="Throughout Program", program=self.program.name
        )
        with self.assertRaises(frappe.ValidationError) as ctx:
            planner.propose(t.name)
        self.assertIn("not set up for bulk planning", str(ctx.exception))


class TestMostConstrainedFirst(PlannerCase):
    def test_a_student_with_one_option_does_not_lose_the_last_seat(self):
        """Placing in pool order would seat the flexible student first and leave
        the constrained one unplaced, with capacity still in the room."""
        t = self.make_type(
            criteria=[{"criterion": "match_gender"}], automation_max_size=1
        )
        constrained = self.enrolled_student(gender="Female")
        flexible = self.enrolled_student(gender="Male")
        self.mentor(gender="Female")
        self.mentor(gender="Male")

        plan = planner.propose(t.name)
        seated = {m["person"] for g in plan["groups"] for m in g["members"]}
        self.assertIn(constrained.person, seated)
        self.assertIn(flexible.person, seated)


class TestReadiness(PlannerCase):
    """Mentor gaps and student gaps are different failures and are counted
    separately: one student without gender makes that student unplaced, but a
    mentor pool without gender makes the rule inoperable."""

    def test_the_setup_reports_gaps_on_both_sides(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        self.enrolled_student(gender="Female")
        self.enrolled_student()
        self.mentor(gender="Female")
        self.mentor()

        setup = planner.planner_setup(t.name)
        row = setup["readiness"][0]
        self.assertEqual(row["criterion"], "match_gender")
        self.assertEqual(row["students_missing"], 1)
        self.assertEqual(row["students_total"], 2)
        self.assertEqual(row["mentors_missing"], 1)
        self.assertEqual(row["mentors_total"], 2)

    def test_the_setup_counts_each_student_scope(self):
        t = self.make_type()
        self.enrolled_student()
        setup = planner.planner_setup(t.name)
        self.assertEqual(setup["scopes"]["all"], 1)
        self.assertEqual(setup["scopes"]["never"], 1)
        self.assertEqual(setup["scopes"]["former"], 0)

    def test_a_type_with_no_mentor_unit_is_named_not_guessed(self):
        t = self.make_type()
        frappe.db.set_value("Cohort Type", t.name, "mentor_unit", None)
        with self.assertRaises(frappe.ValidationError) as ctx:
            planner.planner_setup(t.name)
        self.assertIn("no Mentor Unit", str(ctx.exception))


class TestTheApiValidatesWhatItIsSent(PlannerCase):
    def test_an_unknown_rule_from_a_client_is_refused(self):
        """A whitelisted method takes whatever a client sends."""
        t = self.make_type()
        with self.assertRaises(frappe.ValidationError) as ctx:
            planner.build_proposal(t.name, criteria=["subprocess.run"])
        self.assertIn("Unknown matching rule", str(ctx.exception))

    def test_only_plannable_types_are_listed(self):
        listed = self.make_type()
        hidden = fx.make_cohort_type(
            category="Throughout Program", program=fx.make_program().name
        )
        names = {r["name"] for r in planner.plannable_types()}
        self.assertIn(listed.name, names)
        self.assertNotIn(hidden.name, names)
