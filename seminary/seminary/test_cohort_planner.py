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

from seminary.seminary import faculty
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
        self.assertIn("next nearest cohort", note)

    def test_with_one_group_the_note_says_there_is_nowhere_else(self):
        t = self.make_type(criteria=[{"criterion": "nearest_mentor"}])
        self.enrolled_student(point=(-23.55, -46.63))
        self.mentor(point=(-23.56, -46.64))

        plan = planner.propose(t.name)
        note = " ".join(plan["groups"][0]["members"][0]["notes"])
        self.assertIn("no other cohort here", note)

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


class TestApply(PlannerCase):
    """Create Cohorts: all of it, or none of it (ADR 067 §7)."""

    def _plan(self, **kw):
        t = self.make_type(**kw)
        return t, planner.propose(t.name)

    def _payload(self, plan):
        return [
            {
                "name": g["suggested_name"],
                "mentor": g["mentor"],
                "members": [
                    {"person": m["person"], "placed_by_rule": m["placed_by_rule"]}
                    for m in g["members"]
                ],
            }
            for g in plan["groups"]
        ]

    def test_a_plan_becomes_cohorts_and_memberships(self):
        student = self.enrolled_student()
        mentor = self.mentor()
        t, plan = self._plan()

        result = planner.create_cohorts(t.name, self._payload(plan))
        self.assertEqual(len(result["created"]), 1)
        cohort = result["created"][0]["cohort"]
        self.assertEqual(frappe.db.get_value("Cohort", cohort, "cohort_type"), t.name)
        self.assertTrue(
            frappe.db.exists(
                "Cohort Membership",
                {"cohort": cohort, "person": student.person, "active": 1},
            )
        )
        self.assertEqual(frappe.db.get_value("Cohort", cohort, "leader"), mentor.person)

    def test_the_mentor_is_seated_once_as_the_leader(self):
        """`Cohort.after_insert` already seats them, so the apply path must not
        insert a second membership for the same human."""
        self.enrolled_student()
        mentor = self.mentor()
        t, plan = self._plan()
        result = planner.create_cohorts(t.name, self._payload(plan))
        cohort = result["created"][0]["cohort"]

        rows = frappe.get_all(
            "Cohort Membership",
            filters={"cohort": cohort, "person": mentor.person},
            fields=["is_leader", "role"],
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].is_leader)
        self.assertEqual(rows[0].role, "Mentor")

    def test_members_are_active_not_invited(self):
        """An invite leaves the placement in limbo while the mentor's slot is
        already spent. A reviewed batch is a decision taken."""
        student = self.enrolled_student()
        self.mentor()
        t, plan = self._plan()
        result = planner.create_cohorts(t.name, self._payload(plan))

        status = frappe.db.get_value(
            "Cohort Membership",
            {"cohort": result["created"][0]["cohort"], "person": student.person},
            "invite_status",
        )
        self.assertEqual(status, "Active")

    def test_what_placed_each_member_is_recorded(self):
        student = self.enrolled_student(gender="Female")
        self.mentor(gender="Female")
        t, plan = self._plan(criteria=[{"criterion": "match_gender"}])
        result = planner.create_cohorts(t.name, self._payload(plan))

        stamp = frappe.db.get_value(
            "Cohort Membership",
            {"cohort": result["created"][0]["cohort"], "person": student.person},
            "placed_by_rule",
        )
        self.assertIn("Match student and mentor gender", stamp)

    def test_a_hand_moved_member_is_stamped_as_one(self):
        """The difference between a rule the school can change and a judgement
        one person made."""
        student = self.enrolled_student()
        self.mentor()
        t, plan = self._plan()
        payload = self._payload(plan)
        payload[0]["members"][0].pop("placed_by_rule")

        result = planner.create_cohorts(t.name, payload)
        stamp = frappe.db.get_value(
            "Cohort Membership",
            {"cohort": result["created"][0]["cohort"], "person": student.person},
            "placed_by_rule",
        )
        self.assertEqual(stamp, planner.MANUAL_STAMP)

    # ------------------------------------------------------------ re-validation

    def test_a_student_placed_elsewhere_meanwhile_refuses_the_whole_plan(self):
        a = self.enrolled_student()
        self.enrolled_student()
        self.mentor()
        t, plan = self._plan()

        # Somebody else placed one of them while the plan sat in the browser.
        leader = fx.make_person("Other", user=fx.make_user().name)
        other = fx.make_cohort(t.name, leader.name)
        fx.add_member(other.name, a.person)

        before = frappe.db.count("Cohort")
        with self.assertRaises(frappe.ValidationError) as ctx:
            planner.create_cohorts(t.name, self._payload(plan))
        self.assertIn("has joined a cohort", str(ctx.exception))
        self.assertEqual(frappe.db.count("Cohort"), before)

    def test_a_mentor_who_left_the_unit_refuses_the_whole_plan(self):
        self.enrolled_student()
        mentor = self.mentor()
        t, plan = self._plan()
        frappe.db.set_value(
            "Academic Unit Membership",
            {"instructor": mentor.name, "unit": self.unit.name},
            "is_active",
            0,
        )
        with self.assertRaises(frappe.ValidationError) as ctx:
            planner.create_cohorts(t.name, self._payload(plan))
        self.assertIn("no longer a mentor", str(ctx.exception))

    def test_a_person_the_client_invented_is_refused(self):
        """The browser can name any Person it likes; the pool query is the
        permission check."""
        self.enrolled_student()
        self.mentor()
        t, plan = self._plan()
        payload = self._payload(plan)
        payload[0]["members"].append({"person": fx.make_person("Outsider").name})

        with self.assertRaises(frappe.ValidationError) as ctx:
            planner.create_cohorts(t.name, payload)
        self.assertIn("no longer in the group of students", str(ctx.exception))

    def test_the_same_student_in_two_groups_is_refused(self):
        student = self.enrolled_student()
        self.enrolled_student()
        self.mentor()
        self.mentor()
        t, plan = self._plan(automation_max_size=1)
        payload = self._payload(plan)
        payload[1]["members"].append({"person": student.person})

        with self.assertRaises(frappe.ValidationError) as ctx:
            planner.create_cohorts(t.name, payload)
        self.assertIn("two of these cohorts", str(ctx.exception))

    def test_nothing_is_created_when_any_group_fails(self):
        """All or nothing: some students notified and some not is the one
        outcome nobody can review."""
        self.enrolled_student()
        self.enrolled_student()
        self.mentor()
        self.mentor()
        t, plan = self._plan(automation_max_size=1)
        payload = self._payload(plan)
        payload[1]["members"].append({"person": fx.make_person("Ghost").name})

        before = frappe.db.count("Cohort"), frappe.db.count("Cohort Membership")
        with self.assertRaises(frappe.ValidationError):
            planner.create_cohorts(t.name, payload)
        self.assertEqual(
            (frappe.db.count("Cohort"), frappe.db.count("Cohort Membership")), before
        )

    # ---------------------------------------------------------------- capacity

    def test_going_over_a_ceiling_is_applied_and_reported(self):
        """A ceiling may be a workload agreement, so passing it is the chair's
        call -- and theirs to confirm with that mentor."""
        for _i in range(3):
            self.enrolled_student()
        mentor = self.mentor(max_students=2)
        t, plan = self._plan()
        payload = self._payload(plan)
        # The chair dragged all three onto one mentor whose ceiling is two.
        payload[0]["members"] = [
            {"person": s["person"]} for s in planner.students_needing_placement(t.name)
        ]

        result = planner.create_cohorts(t.name, payload)
        self.assertEqual(len(result["created"]), 1)
        self.assertEqual(result["created"][0]["members"], 3)

        over = result["over_capacity"]
        self.assertEqual(len(over), 1)
        self.assertEqual(over[0]["mentor"], mentor.name)
        self.assertEqual(over[0]["current_students"], 3)
        self.assertEqual(over[0]["max_students"], 2)

    def test_a_plan_within_the_ceiling_reports_nothing(self):
        self.enrolled_student()
        self.mentor(max_students=5)
        t, plan = self._plan()
        result = planner.create_cohorts(t.name, self._payload(plan))
        self.assertEqual(result["over_capacity"], [])

    def test_the_counter_moves_by_one_per_member(self):
        for _i in range(2):
            self.enrolled_student()
        mentor = self.mentor(max_students=10)
        t, plan = self._plan()
        planner.create_cohorts(t.name, self._payload(plan))

        capacity = faculty.capacity_for(
            self.unit.name, planner.COHORT_MENTORSHIP_ROUTE, mentor.name
        )
        self.assertEqual(capacity["current_students"], 2)


class TestCapacityClaims(PlannerCase):
    """`faculty.claim_slot` and its two callers (ADR 067 §7).

    The defect being fixed is the missing lock, which every caller had. What is
    *not* uniform is the ceiling: it binds where the system chooses an assignee
    and not where a human already has.
    """

    def _cap_row(self, instructor):
        return frappe.db.sql(
            """
            SELECT c.name FROM `tabAcademic Unit Capability` c
            JOIN `tabAcademic Unit Membership` m ON m.name = c.parent
            WHERE m.instructor = %s
            """,
            instructor.name,
        )[0][0]

    def test_the_system_choosing_will_not_pass_a_ceiling(self):
        mentor = self.mentor(max_students=1)
        self.assertEqual(
            faculty.claim_capability(self.unit.name, planner.COHORT_MENTORSHIP_ROUTE),
            mentor.name,
        )
        self.assertIsNone(
            faculty.claim_capability(self.unit.name, planner.COHORT_MENTORSHIP_ROUTE)
        )

    def test_the_system_falls_through_to_the_next_candidate(self):
        """Losing the race should cost the next-best assignee, not the whole
        assignment."""
        full = self.mentor(max_students=1)
        free = self.mentor(max_students=5)
        faculty.claim_slot(self._cap_row(full))

        chosen = faculty.claim_capability(
            self.unit.name, planner.COHORT_MENTORSHIP_ROUTE
        )
        self.assertEqual(chosen, free.name)

    def test_a_human_s_choice_is_always_counted(self):
        """Refusing the increment would not undo the assignment -- it would only
        stop counting it, and an undercounted advisor looks free to the next
        round-robin."""
        mentor = self.mentor(max_students=1)
        self.assertTrue(
            faculty.claim_for(
                self.unit.name, planner.COHORT_MENTORSHIP_ROUTE, mentor.name
            )
        )
        self.assertTrue(
            faculty.claim_for(
                self.unit.name, planner.COHORT_MENTORSHIP_ROUTE, mentor.name
            )
        )
        capacity = faculty.capacity_for(
            self.unit.name, planner.COHORT_MENTORSHIP_ROUTE, mentor.name
        )
        self.assertEqual(capacity["current_students"], 2)

    def test_an_unwired_instructor_claims_nothing(self):
        stranger = fx.make_instructor()
        self.assertFalse(
            faculty.claim_for(
                self.unit.name, planner.COHORT_MENTORSHIP_ROUTE, stranger.name
            )
        )
        self.assertIsNone(
            faculty.capacity_for(
                self.unit.name, planner.COHORT_MENTORSHIP_ROUTE, stranger.name
            )
        )

    def test_an_uncapped_capability_never_refuses(self):
        mentor = self.mentor(max_students=0)
        for _i in range(3):
            self.assertTrue(
                faculty.claim_for(
                    self.unit.name, planner.COHORT_MENTORSHIP_ROUTE, mentor.name
                )
            )


class TestReadinessDetail(PlannerCase):
    """The readiness check counts; this names.

    Finding the same people by hand means filtering a list view on "is not set",
    which is neither obvious nor reachable from where the question was asked.
    """

    def test_it_names_the_mentors_missing_the_datum(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        gap = self.mentor()
        self.mentor(gender="Female")

        detail = planner.readiness_detail(t.name, "match_gender", "mentors")
        self.assertEqual(detail["total"], 1)
        self.assertEqual(detail["people"][0]["person"], gap.person)
        self.assertEqual(detail["people"][0]["role"], gap.name)
        self.assertEqual(detail["people"][0]["role_doctype"], "Instructor")

    def test_it_names_the_students_too(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        gap = self.enrolled_student()
        self.enrolled_student(gender="Female")

        detail = planner.readiness_detail(t.name, "match_gender", "students")
        self.assertEqual([p["person"] for p in detail["people"]], [gap.person])
        self.assertEqual(detail["people"][0]["role_doctype"], "Student")

    def test_the_distance_gap_names_people_and_not_points(self):
        """It answers "whose address did we fail to locate" -- a list of names.
        A coordinate never reaches a client."""
        t = self.make_type(criteria=[{"criterion": "nearest_mentor"}])
        gap = self.mentor()
        self.mentor(point=(-23.55, -46.63))

        detail = planner.readiness_detail(t.name, "nearest_mentor", "mentors")
        self.assertEqual([p["person"] for p in detail["people"]], [gap.person])
        blob = frappe.as_json(detail)
        self.assertNotIn("latitude", blob)
        self.assertNotIn("longitude", blob)

    def test_the_label_names_the_datum_not_the_column(self):
        """Telling a chair four mentors "have no latitude" names a column, not
        the thing they have to go and fix."""
        t = self.make_type(criteria=[{"criterion": "nearest_mentor"}])
        self.mentor()
        detail = planner.readiness_detail(t.name, "nearest_mentor", "mentors")
        self.assertEqual(detail["reads_label"], "address we could locate")
        self.assertNotEqual(detail["reads_label"], detail["criterion"])

    def test_the_setup_carries_the_same_label(self):
        t = self.make_type(criteria=[{"criterion": "nearest_mentor"}])
        self.mentor()
        self.enrolled_student()
        row = planner.planner_setup(t.name)["readiness"][0]
        self.assertEqual(row["reads_label"], "address we could locate")

    def test_an_unknown_rule_or_side_is_refused(self):
        t = self.make_type()
        with self.assertRaises(frappe.ValidationError):
            planner.readiness_detail(t.name, "subprocess.run", "mentors")
        with self.assertRaises(frappe.ValidationError):
            planner.readiness_detail(t.name, "match_gender", "everybody")

    def test_nobody_missing_is_an_empty_list_not_an_error(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        self.mentor(gender="Female")
        detail = planner.readiness_detail(t.name, "match_gender", "mentors")
        self.assertEqual(detail["total"], 0)
        self.assertEqual(detail["people"], [])


class TestFiltersPartitionTheGroupCount(PlannerCase):
    """A Filter splits the students, so the group count cannot be taken over
    the pool as a whole (found on a real plan, ADR 067 §5).

    Six students at a maximum of six is arithmetically one cohort. Under gender
    matching it is at least two, and the version that counted globally seeded a
    single male mentor, placed the three men and left the three women unplaced
    — with a female mentor sitting unused in the pool and a reason that was
    correct and useless: "X is not the same gender as this student."
    """

    def _macl(self):
        t = self.make_type(
            criteria=[{"criterion": "match_gender"}],
            automation_min_size=3,
            automation_max_size=6,
        )
        for _i in range(3):
            self.enrolled_student(gender="Male")
        for _i in range(3):
            self.enrolled_student(gender="Female")
        return t

    def test_both_genders_are_placed(self):
        t = self._macl()
        male = self.mentor(gender="Male")
        female = self.mentor(gender="Female")

        plan = planner.propose(t.name)
        self.assertEqual(plan["unplaced"], [])
        self.assertEqual(len(plan["groups"]), 2)
        leaders = {g["mentor"] for g in plan["groups"]}
        self.assertEqual(leaders, {male.name, female.name})
        for group in plan["groups"]:
            self.assertEqual(group["size"], 3)

    def test_the_global_count_would_still_have_said_one(self):
        """The arithmetic is not wrong; applying it to the whole pool was."""
        self.assertEqual(planner.group_count(6, 3, 6), 1)

    def test_each_class_gets_the_groups_its_own_size_warrants(self):
        """Three of each at a maximum of two is two groups per gender, not two
        overall."""
        t = self.make_type(
            criteria=[{"criterion": "match_gender"}], automation_max_size=2
        )
        for _i in range(3):
            self.enrolled_student(gender="Male")
        for _i in range(3):
            self.enrolled_student(gender="Female")
        for _i in range(2):
            self.mentor(gender="Male")
        for _i in range(2):
            self.mentor(gender="Female")

        plan = planner.propose(t.name)
        self.assertEqual(plan["unplaced"], [])
        self.assertEqual(len(plan["groups"]), 4)

    def test_no_filters_still_counts_over_the_whole_pool(self):
        """One eligibility class, so the per-class count is the global one."""
        t = self.make_type(automation_min_size=3, automation_max_size=6)
        for _i in range(6):
            self.enrolled_student()
        for _i in range(4):
            self.mentor()

        plan = planner.propose(t.name)
        self.assertEqual(len(plan["groups"]), 1)
        self.assertEqual(plan["groups"][0]["size"], 6)

    def test_a_class_with_no_eligible_mentor_is_unplaced_not_crashed(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        for _i in range(2):
            self.enrolled_student(gender="Male")
        self.enrolled_student(gender="Female")
        self.mentor(gender="Male")

        plan = planner.propose(t.name)
        self.assertEqual(len(plan["groups"]), 1)
        self.assertEqual(len(plan["unplaced"]), 1)

    def test_the_classes_are_the_distinct_eligible_mentor_sets(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        self.enrolled_student(gender="Male")
        self.enrolled_student(gender="Female")
        self.mentor(gender="Male")
        self.mentor(gender="Female")

        students = planner.students_needing_placement(t.name)
        mentors = planner.mentor_pool(self.unit.name)
        rows = planner._person_rows(
            [s["person"] for s in students] + [m["person"] for m in mentors]
        )
        classes = planner.eligibility_classes(
            students, mentors, rows, [rules.get("match_gender")]
        )
        self.assertEqual(len(classes), 2)
        for eligible in classes:
            self.assertEqual(len(eligible), 1)


class TestShortlistCoversThePool(PlannerCase):
    """The page lets a chair open a cohort under a mentor the matcher did not
    pick -- the timezone case: three students on one side of the world are
    better served by a nearby mentor with a small group than by the arrangement
    the rules produce.

    That only works if the payload says whether the rules allow each pairing
    for *any* mentor, not only for the ones already leading a cohort.
    """

    def test_it_ranks_every_eligible_mentor_not_only_the_leaders(self):
        t = self.make_type(automation_min_size=3, automation_max_size=6)
        student = self.enrolled_student()
        for _i in range(4):
            self.mentor()

        plan = planner.propose(t.name)
        # One student, so one group -- but all four mentors could take them.
        self.assertEqual(len(plan["groups"]), 1)
        self.assertEqual(len(plan["shortlists"][student.person]), 4)

    def test_it_still_excludes_mentors_a_filter_refuses(self):
        """The *shortlist* is what the rules allow — distinct from the distance
        matrix, which covers everyone. An added cohort has to know the rules say
        no, so the page can warn, and still show how far away they are."""
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        student = self.enrolled_student(gender="Female")
        match = self.mentor(gender="Female")
        self.mentor(gender="Male")

        plan = planner.propose(t.name)
        self.assertEqual(plan["shortlists"][student.person], [match.person])

    def test_an_unplaced_student_has_an_empty_shortlist(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        student = self.enrolled_student(gender="Female")
        self.mentor(gender="Male")

        plan = planner.propose(t.name)
        self.assertEqual(plan["shortlists"][student.person], [])

    def test_a_cohort_under_an_unseeded_mentor_is_accepted_on_apply(self):
        """What the Add a Cohort button posts: a mentor the matcher never
        chose. The apply path checks they are wired to the unit, not that the
        matcher liked them."""
        t = self.make_type(automation_max_size=6)
        students = [self.enrolled_student() for _i in range(3)]
        self.mentor()
        spare = self.mentor()

        plan = planner.propose(t.name)
        self.assertNotIn(spare.name, [g["mentor"] for g in plan["groups"]])

        result = planner.create_cohorts(
            t.name,
            [
                {
                    "name": "Hand made",
                    "mentor": spare.name,
                    "members": [{"person": s.person} for s in students],
                }
            ],
        )
        self.assertEqual(len(result["created"]), 1)
        self.assertEqual(result["created"][0]["members"], 3)

    def test_an_empty_added_cohort_is_simply_not_created(self):
        t = self.make_type()
        self.enrolled_student()
        mentor = self.mentor()
        spare = self.mentor()
        plan = planner.propose(t.name)

        payload = [
            {
                "name": g["suggested_name"],
                "mentor": g["mentor"],
                "members": [{"person": m["person"]} for m in g["members"]],
            }
            for g in plan["groups"]
        ]
        payload.append({"name": "Empty", "mentor": spare.name, "members": []})

        result = planner.create_cohorts(t.name, payload)
        self.assertEqual(len(result["created"]), 1)
        self.assertEqual(result["created"][0]["mentor"], mentor.name)


class TestPairValues(PlannerCase):
    """Distances survive a drag (ADR 067 §6, §10).

    A moved student's note stops being true the moment they move: "next nearest
    cohort 34 km" was measured against a cohort they are no longer in. The page
    cannot recompute it — coordinates never leave the server — so the derived
    numbers travel instead.
    """

    def test_the_matrix_covers_every_mentor_in_the_pool(self):
        t = self.make_type(criteria=[{"criterion": "nearest_mentor"}])
        student = self.enrolled_student(point=(-23.55, -46.63))
        a = self.mentor(point=(-23.56, -46.64))
        b = self.mentor(point=(-30.03, -51.23))

        plan = planner.propose(t.name)
        row = plan["pair_values"][student.person]
        self.assertEqual(set(row), {a.person, b.person})
        self.assertLess(row[a.person], row[b.person])

    def test_no_coordinate_is_ever_sent(self):
        t = self.make_type(criteria=[{"criterion": "nearest_mentor"}])
        self.enrolled_student(point=(-23.55, -46.63))
        self.mentor(point=(-23.56, -46.64))

        blob = frappe.as_json(planner.propose(t.name))
        for leak in ("latitude", "longitude", "geo_status", "-46.63"):
            with self.subTest(leak=leak):
                self.assertNotIn(leak, blob)

    def test_a_mentor_without_a_point_has_no_value(self):
        """Absent, not zero: a 0 would render as "0 km away", which is a place."""
        t = self.make_type(criteria=[{"criterion": "nearest_mentor"}])
        student = self.enrolled_student(point=(-23.55, -46.63))
        located = self.mentor(point=(-23.56, -46.64))
        unlocated = self.mentor()

        row = planner.propose(t.name)["pair_values"][student.person]
        self.assertIn(located.person, row)
        self.assertNotIn(unlocated.person, row)

    def test_the_numbers_are_in_the_school_s_unit(self):
        t = self.make_type(criteria=[{"criterion": "nearest_mentor"}])
        student = self.enrolled_student(point=(-23.55, -46.63))
        mentor = self.mentor(point=(-30.03, -51.23))

        frappe.db.set_single_value("Seminary Settings", "distance_unit", "Kilometres")
        plan = planner.propose(t.name)
        km = plan["pair_values"][student.person][mentor.person]
        self.assertEqual(plan["pair_suffix"], "km")

        frappe.db.set_single_value("Seminary Settings", "distance_unit", "Miles")
        plan = planner.propose(t.name)
        miles = plan["pair_values"][student.person][mentor.person]
        self.assertEqual(plan["pair_suffix"], "mi")
        self.assertAlmostEqual(miles, km / 1.609344, places=0)

    def test_no_quantity_rule_means_no_matrix(self):
        """A Filter publishes no number, so nothing is sent and the page falls
        back to naming the preference order."""
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        self.enrolled_student(gender="Female")
        self.mentor(gender="Female")

        plan = planner.propose(t.name)
        self.assertEqual(plan["pair_values"], {})
        self.assertIsNone(plan["pair_suffix"])

    def test_a_pairing_the_filters_refuse_still_has_a_distance(self):
        """Whether the rules permit a pairing and how far apart two people live
        are different questions. A chair who overrides a filter — the entire
        point of being able to drag — must not lose the number that made them
        want to."""
        t = self.make_type(
            criteria=[
                {"criterion": "match_gender"},
                {"criterion": "nearest_mentor"},
            ]
        )
        student = self.enrolled_student(gender="Female", point=(-23.55, -46.63))
        mismatched = self.mentor(gender="Male", point=(-23.56, -46.64))
        self.mentor(gender="Female", point=(-30.03, -51.23))

        plan = planner.propose(t.name)
        self.assertNotIn(mismatched.person, plan["shortlists"][student.person])
        self.assertIn(mismatched.person, plan["pair_values"][student.person])


class TestMandatoryPersonalFields(IntegrationTestCase):
    """The curation layer over `person_fields.py` (ADR 067 §9).

    A thin one: the school owns exactly one bit — whether a detail is required.
    Everything else is read from the code on every save, because `read_only` is
    a form hint that a REST insert never sees.
    """

    def test_everything_but_required_comes_from_the_code(self):
        doc = frappe.get_doc("Mandatory Personal Field", "gender")
        doc.automation_valid = 0
        doc.derived = 1
        doc.field_label = "Whatever"
        doc.save(ignore_permissions=True)

        self.assertTrue(doc.automation_valid)  # a rule does read gender
        self.assertFalse(doc.derived)  # and it is typed, not worked out
        self.assertEqual(doc.field_label, "Gender")

    def test_a_coordinate_is_marked_as_worked_out(self):
        doc = frappe.get_doc("Mandatory Personal Field", "latitude")
        self.assertTrue(doc.derived)

    def test_a_field_the_app_does_not_record_is_refused(self):
        doc = frappe.get_doc(
            {"doctype": "Mandatory Personal Field", "person_field": "favourite_psalm"}
        )
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("not a personal detail", str(ctx.exception))

    def test_the_sources_name_where_a_human_types_it(self):
        """Since ADR 068 the role records mirror the Person, so a mirror is not
        a source — nobody can type into one."""
        doc = frappe.get_doc("Mandatory Personal Field", "gender")
        doc.save(ignore_permissions=True)
        self.assertIn("Application form", doc.sources)
        self.assertIn("Person record", doc.sources)
        self.assertNotIn("Student", doc.sources)


class TestUnMandatingIsGuarded(PlannerCase):
    def test_a_detail_a_live_rule_reads_cannot_be_un_required(self):
        """Silently dropping a criterion changes who mentors whom, and that is
        not a side effect anyone should get from clearing a checkbox."""
        t = self.make_type(criteria=[{"criterion": "match_gender"}])

        doc = frappe.get_doc("Mandatory Personal Field", "gender")
        doc.mandatory = 0
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.save(ignore_permissions=True)
        self.assertIn(t.name, str(ctx.exception))

    def test_a_detail_nothing_reads_can_be_un_required(self):
        fx.require_personal_field("date_of_birth")
        doc = frappe.get_doc("Mandatory Personal Field", "date_of_birth")
        doc.mandatory = 0
        doc.save(ignore_permissions=True)
        self.assertFalse(doc.mandatory)

    def test_an_inactive_type_does_not_hold_a_detail_hostage(self):
        from seminary.seminary.doctype.mandatory_personal_field import (
            mandatory_personal_field as mpf,
        )

        self.make_type(criteria=[{"criterion": "match_gender"}])
        # Every type that reads gender, not only the one just made:
        # `IntegrationTestCase` rolls back per *class*, so a sibling test's
        # active type is still there and would hold the detail hostage on its
        # behalf.
        for name in mpf.cohort_types_depending_on("gender"):
            frappe.db.set_value("Cohort Type", name, "is_active", 0)

        doc = frappe.get_doc("Mandatory Personal Field", "gender")
        doc.mandatory = 0
        doc.save(ignore_permissions=True)
        self.assertFalse(doc.mandatory)


class TestARuleNeedsItsDataGuaranteed(PlannerCase):
    def test_a_criterion_whose_detail_is_not_required_is_refused(self):
        """Checked in `validate`, not only in the picker: a picker filter is a
        convenience and a REST insert never sees one."""
        # Built directly rather than through the fixture, which marks a rule's
        # detail required precisely so every other test stops depending on how
        # the site happens to be configured.
        frappe.db.set_value("Mandatory Personal Field", "gender", "mandatory", 0)
        doc = frappe.get_doc(
            {
                "doctype": "Cohort Type",
                "type_name": fx.uid("Type"),
                "category": "Throughout Program",
                "leader_eligibility": "Anyone",
                "program": self.program.name,
                "plannable": 1,
                "mentor_unit": self.unit.name,
                "criteria": [{"criterion": "match_gender"}],
            }
        )
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("has to be a detail your school requires", str(ctx.exception))

    def test_a_type_with_its_detail_required_saves(self):
        t = self.make_type(criteria=[{"criterion": "match_gender"}])
        self.assertEqual([r.criterion for r in t.criteria], ["match_gender"])


class TestCaptureRequiredFollowsTheSchool(PlannerCase):
    def test_a_required_detail_joins_the_application_gate(self):
        """The rules a school chooses and the questions its application asks
        stay in step by construction."""
        from seminary.seminary import person_fields

        fx.require_personal_field("date_of_birth")
        self.assertIn("date_of_birth", person_fields.capture_required())

    def test_a_worked_out_detail_never_joins_it(self):
        """Nobody types a latitude, so required there means resolvable — which
        the planner reports and no save refuses."""
        from seminary.seminary import person_fields

        fx.require_personal_field("latitude")
        self.assertNotIn("latitude", person_fields.capture_required())

    def test_the_built_in_floor_is_always_there(self):
        from seminary.seminary import person_fields

        for field in person_fields.CAPTURE_REQUIRED:
            self.assertIn(field, person_fields.capture_required())


class TestPersonWarnsAndNeverRefuses(PlannerCase):
    def test_a_person_missing_a_required_detail_still_saves(self):
        """A rule enabled this week must not make a record created three years
        ago unsaveable while somebody corrects a phone number."""
        fx.require_personal_field("date_of_birth")
        person = fx.make_person("NoDob")
        person.reload()
        person.middle_name = "Edited"
        person.save(ignore_permissions=True)  # must not throw

        messages = " ".join(str(m) for m in frappe.get_message_log())
        self.assertIn("Still to record", messages)


class TestUnplacedIssueCode(PlannerCase):
    """The planner is pull; this is the push half (ADR 067 §11)."""

    def test_a_type_with_students_waiting_is_reported(self):
        from seminary.seminary.report.cohorts_needing_attention import (
            cohorts_needing_attention as report,
        )

        t = self.make_type()
        for _i in range(3):
            self.enrolled_student()
        self.mentor()

        _cols, rows = report.execute({"cohort_type": t.name, "issue": "unplaced"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cohort_type"], t.name)
        self.assertEqual(rows[0]["member_count"], 3)
        # No cohort, which is the point: these students are not in one.
        self.assertIsNone(rows[0]["cohort"])

    def test_a_type_with_nobody_waiting_is_not_reported(self):
        from seminary.seminary.report.cohorts_needing_attention import (
            cohorts_needing_attention as report,
        )

        t = self.make_type()
        _cols, rows = report.execute({"cohort_type": t.name, "issue": "unplaced"})
        self.assertEqual(rows, [])


class TestADerivedDetailExplainsItself(PlannerCase):
    """ "Required" on a coordinate reaches no form, so the row has to say what
    it *does* mean and what would actually make the datum arrive (ADR 067 §9)."""

    def _latitude(self):
        return frappe.get_doc("Mandatory Personal Field", "latitude")

    def test_it_is_named_the_way_a_school_would_name_it(self):
        """Nobody requires a "Latitude"; they require an address we can find."""
        doc = self._latitude()
        doc.save(ignore_permissions=True)
        self.assertEqual(doc.field_label, "Address we could locate")

    def test_the_sources_name_the_minimum_and_what_it_buys(self):
        doc = self._latitude()
        doc.save(ignore_permissions=True)
        self.assertIn("Never typed", doc.sources)
        self.assertIn("City", doc.sources)
        # The geocoder reads mailing_country, not the comms routing country.
        self.assertIn("Mailing Country", doc.sources)
        self.assertIn("town-to-town", doc.sources)
        self.assertIn("Address Line 1", doc.sources)

    def test_requiring_it_warns_that_no_form_asks_for_it(self):
        for field in ("city", "mailing_country"):
            frappe.db.set_value("Mandatory Personal Field", field, "mandatory", 0)
        frappe.clear_messages()
        doc = self._latitude()
        doc.mandatory = 1
        doc.save(ignore_permissions=True)

        messages = " ".join(str(m) for m in frappe.get_message_log())
        self.assertIn("City", messages)
        self.assertIn("Mailing Country", messages)
        self.assertIn("town", messages)

    def test_the_warning_stops_once_the_minimum_is_required(self):
        fx.require_personal_field("city", "mailing_country")
        frappe.clear_messages()
        doc = self._latitude()
        doc.mandatory = 1
        doc.save(ignore_permissions=True)

        messages = " ".join(str(m) for m in frappe.get_message_log())
        self.assertNotIn("Nothing on a form asks for this", messages)

    def test_it_never_joins_a_form_gate_however_it_is_set(self):
        """The whole point: a derived detail cannot be demanded of anybody."""
        from seminary.seminary import person_fields
        from seminary.seminary.doctype.mandatory_personal_field import (
            mandatory_personal_field as mpf,
        )

        fx.require_personal_field("latitude", "city", "mailing_country")
        self.assertNotIn("latitude", person_fields.capture_required())
        self.assertNotIn("latitude", mpf.required_fields())
        self.assertFalse(frappe.get_meta("Person").get_field("latitude").reqd)

    def test_a_detail_nobody_could_honestly_supply_is_not_offered(self):
        """Address Line 2 is empty for most people and adds nothing to a
        geocode, so requiring it could not be satisfied honestly."""
        self.assertFalse(frappe.db.exists("Mandatory Personal Field", "address_line_2"))
