# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""ADR 066 — mentoring and program cohorts.

Covers the policy layer end to end: `Cohort Type` as the policy record and the
validations that keep two rules from contradicting each other (§2, §7.9, §7.15);
`Cohort Membership` as where policy meets a person (§2, §7.4); academic
privilege composed from mentorship *and* the framework naming the cohort type
(§5); the enrollment's mentors derived from the cohort rather than the reverse
(§4); persistence as a statement about a kind of cohort (§2); and the edge cases
in §7.

These are integration tests because the thing under test is a composition of
records -- a person, a membership, a cohort, a type, a framework, an enrollment.
Mocking the joins would test the mocks.
"""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import cbe, instructor_load
from seminary.seminary.discipleship import api as dapi
from seminary.seminary.discipleship import permissions as dperm
from seminary.seminary.discipleship import enrollment as enrollment_mod
from seminary.seminary.discipleship.enrollment import (
    SEPARATION_STATUSES,
    cohorts_persist,
    release_from_program_cohorts,
)
from seminary.seminary.tests import cohort_fixtures as fx

ALUMNUS = "Alumnus of the bound program or level"
ANY_ALUMNUS = "Any alumnus"


class TestCohortTypePolicy(IntegrationTestCase):
    """§2 — the three axes, and the validations that keep them coherent."""

    def test_paced_program_requires_a_program(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort_type(category="Paced Program")
        self.assertIn("advance through", str(ctx.exception))

    def test_paced_program_refuses_a_credits_based_program(self):
        program = fx.make_program(program_type="Credits-based")
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort_type(category="Paced Program", program=program.name)
        self.assertIn("term boundary", str(ctx.exception))

    def test_throughout_program_requires_a_binding(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort_type(category="Throughout Program")
        self.assertIn("enrollment to graduation", str(ctx.exception))

    def test_program_and_level_together_are_refused(self):
        level = fx.make_program_level()
        if not level:
            self.skipTest("site has no Program Level")
        program = fx.make_program()
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort_type(
                category="Throughout Program",
                program=program.name,
                program_level=level,
            )
        self.assertIn("not to both", str(ctx.exception))

    def test_one_active_paced_type_per_program(self):
        program = fx.make_program()
        fx.make_cohort_type(category="Paced Program", program=program.name)

        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort_type(category="Paced Program", program=program.name)
        self.assertIn("two directions", str(ctx.exception))

        # Retiring one and defining its replacement is an ordinary two-step edit.
        second = fx.make_cohort_type(
            category="Paced Program", program=program.name, is_active=0
        )
        self.assertTrue(second.name)

        # A different category over the same program may coexist (§7.9).
        other = fx.make_cohort_type(category="Throughout Program", program=program.name)
        self.assertTrue(other.name)

    def test_acting_fields_clear_when_the_category_cannot_use_them(self):
        program = fx.make_program()
        unit = fx.make_mentoring_unit()
        t = fx.make_cohort_type(
            category="Throughout Program",
            program=program.name,
            plannable=1,
            mentor_unit=unit.name,
            automation_max_size=8,
            remove_on_withdrawal=1,
        )
        self.assertTrue(t.plannable)

        t.category = "Unrestricted"
        t.save(ignore_permissions=True)
        self.assertFalse(t.plannable)
        self.assertFalse(t.mentor_unit)
        self.assertFalse(t.automation_max_size)
        self.assertFalse(t.remove_on_withdrawal)
        self.assertFalse(t.program)

    def test_sizes_and_pool_clear_when_the_type_is_not_plannable(self):
        program = fx.make_program()
        unit = fx.make_mentoring_unit()
        t = fx.make_cohort_type(
            category="Throughout Program",
            program=program.name,
            mentor_unit=unit.name,
            automation_min_size=4,
            automation_max_size=9,
        )
        self.assertFalse(t.mentor_unit)
        self.assertFalse(t.automation_min_size)
        self.assertFalse(t.automation_max_size)

    def test_a_parked_type_keeps_its_destination_through_a_plain_save(self):
        """The promise the ADR 066 category-reset patch makes.

        A type left at `Unrestricted` must survive being opened and saved with
        its `graduates_to` intact, or reclassifying it later silently loses the
        school's configuration.
        """
        program = fx.make_program()
        dest = fx.make_cohort_type()
        t = fx.make_cohort_type(
            category="Throughout Program",
            program=program.name,
            graduates_to=dest.name,
        )
        t.category = "Unrestricted"
        t.save(ignore_permissions=True)
        self.assertFalse(t.graduates_to)  # moving away clears it

        frappe.db.set_value("Cohort Type", t.name, "graduates_to", dest.name)
        t.reload()
        t.description = "touched"
        t.save(ignore_permissions=True)
        self.assertEqual(t.graduates_to, dest.name)  # a plain save does not

        t.category = "Throughout Program"
        t.program = program.name
        t.save(ignore_permissions=True)
        self.assertEqual(t.graduates_to, dest.name)  # and it survives the return


class TestPlanningSettings(IntegrationTestCase):
    """ADR 067 §4 — a plannable type must name a pool the planner can use.

    `mentor_unit` carries a `link_filters` hint on the form, and a picker filter
    is a convenience rather than a rule: it never runs for a REST insert, an
    import or a fixture. Every assertion here is about the server check behind
    it.
    """

    def _type(self, **kw):
        program = fx.make_program()
        values = {"category": "Throughout Program", "program": program.name}
        values.update(kw)
        return fx.make_cohort_type(**values)

    def test_a_plannable_type_without_a_unit_is_refused(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._type(plannable=1)
        self.assertIn("Mentor Unit", str(ctx.exception))

    def test_a_unit_of_the_wrong_type_is_refused(self):
        wrong = frappe.get_doc(
            {
                "doctype": "Academic Unit",
                "unit_name": fx.uid("Committee"),
                "unit_type": "Program Committee",
                "is_active": 1,
            }
        ).insert(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._type(plannable=1, mentor_unit=wrong.name)
        self.assertIn("Mentoring Department", str(ctx.exception))

    def test_an_inactive_unit_is_refused(self):
        unit = fx.make_mentoring_unit(is_active=0)
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._type(plannable=1, mentor_unit=unit.name)
        self.assertIn("not active", str(ctx.exception))

    def test_a_minimum_above_the_maximum_is_refused(self):
        unit = fx.make_mentoring_unit()
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._type(
                plannable=1,
                mentor_unit=unit.name,
                automation_min_size=9,
                automation_max_size=4,
            )
        self.assertIn("larger than the maximum", str(ctx.exception))

    def test_zero_means_unbounded_on_either_size(self):
        """0 is "no bound", so it can never contradict the other number."""
        unit = fx.make_mentoring_unit()
        t = self._type(
            plannable=1,
            mentor_unit=unit.name,
            automation_min_size=9,
            automation_max_size=0,
        )
        self.assertEqual(t.automation_min_size, 9)

    def test_the_mentorship_route_is_seeded_and_tracks_capacity(self):
        """The route is deliberately not the generic `Mentor` capability: that
        one is uncapped, and a ceiling is the whole reason this one exists."""
        capability = fx.mentorship_capability()
        self.assertTrue(capability, "the cohort mentorship capability is not seeded")
        row = frappe.db.get_value(
            "Faculty Capability",
            capability,
            ["tracks_capacity", "requires_instructor"],
            as_dict=True,
        )
        self.assertTrue(row.tracks_capacity)
        self.assertTrue(row.requires_instructor)


class TestGraduationTarget(IntegrationTestCase):
    """§7.15 — graduating into a type is itself how that type gets filled."""

    def test_a_type_cannot_graduate_into_itself(self):
        program = fx.make_program()
        t = fx.make_cohort_type(category="Throughout Program", program=program.name)
        t.graduates_to = t.name
        with self.assertRaises(frappe.ValidationError) as ctx:
            t.save(ignore_permissions=True)
        self.assertIn("graduate into itself", str(ctx.exception))

    def test_a_receiving_type_may_not_be_planned_in_bulk(self):
        program = fx.make_program()
        dest = fx.make_cohort_type()
        fx.make_cohort_type(
            category="Throughout Program",
            program=program.name,
            graduates_to=dest.name,
        )
        dest.reload()
        dest.category = "Throughout Program"
        dest.program = program.name
        dest.plannable = 1
        dest.mentor_unit = fx.make_mentoring_unit().name
        with self.assertRaises(frappe.ValidationError) as ctx:
            dest.save(ignore_permissions=True)
        self.assertIn("already graduates into this type", str(ctx.exception))

    def test_graduating_into_a_plannable_type_is_refused(self):
        program = fx.make_program()
        auto = fx.make_cohort_type(
            category="Throughout Program",
            program=program.name,
            plannable=1,
            mentor_unit=fx.make_mentoring_unit().name,
        )
        src = fx.make_cohort_type(category="Throughout Program", program=program.name)
        src.graduates_to = auto.name
        with self.assertRaises(frappe.ValidationError) as ctx:
            src.save(ignore_permissions=True)
        self.assertIn("forms its own cohorts", str(ctx.exception))


class TestLeaderEligibility(IntegrationTestCase):
    """§2 axis 2 — checked on the membership, against the person in front of it."""

    def test_anyone_lets_a_peer_lead(self):
        person = fx.make_person("Peer")
        t = fx.make_cohort_type(leader_eligibility="Anyone")
        cohort = fx.make_cohort(t.name, person.name)
        self.assertTrue(
            frappe.db.exists(
                "Cohort Membership",
                {"cohort": cohort.name, "person": person.name, "is_leader": 1},
            )
        )

    def test_instructor_rule_refuses_a_non_instructor_at_cohort_creation(self):
        """`Cohort.after_insert` creates the leader's membership, so the rule
        reaches creation -- the registrar is told at the point of the mistake."""
        instructor = fx.make_instructor()
        plain = fx.make_person("Plain")
        t = fx.make_cohort_type(leader_eligibility="Instructor")

        self.assertTrue(fx.make_cohort(t.name, instructor.person).name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort(t.name, plain.name)
        self.assertIn("active Instructor record", str(ctx.exception))

    def test_a_non_instructor_may_still_be_an_ordinary_member(self):
        instructor = fx.make_instructor()
        plain = fx.make_person("Plain")
        t = fx.make_cohort_type(leader_eligibility="Instructor")
        cohort = fx.make_cohort(t.name, instructor.person)

        member = fx.add_member(cohort.name, plain.name)
        self.assertTrue(member.name)

        member.is_leader = 1
        with self.assertRaises(frappe.ValidationError) as ctx:
            member.save(ignore_permissions=True)
        self.assertIn("active Instructor record", str(ctx.exception))

    def test_history_stays_saveable_when_an_instructor_lapses(self):
        """The 7.1 handover depends on this: closing a lapsed leader's row must
        not be refused by the rule that would now reject reopening it."""
        instructor = fx.make_instructor()
        t = fx.make_cohort_type(leader_eligibility="Instructor")
        cohort = fx.make_cohort(t.name, instructor.person)
        frappe.db.set_value("Instructor", instructor.name, "status", "Inactive")

        row = frappe.get_doc(
            "Cohort Membership",
            frappe.db.get_value(
                "Cohort Membership",
                {"cohort": cohort.name, "person": instructor.person},
                "name",
            ),
        )
        row.invite_status = "Left"
        row.save(ignore_permissions=True)  # must not raise

        with self.assertRaises(frappe.ValidationError):
            fx.make_cohort(t.name, instructor.person)

    def test_alumnus_rule_checks_the_bound_program(self):
        program = fx.make_program()
        other = fx.make_program()
        person = fx.make_person("Alum")
        fx.make_alumni_profile(person, program_completed=program.name)

        bound = fx.make_cohort_type(
            leader_eligibility=ALUMNUS,
            category="Throughout Program",
            program=program.name,
        )
        self.assertTrue(fx.make_cohort(bound.name, person.name).name)

        wrong = fx.make_cohort_type(
            leader_eligibility=ALUMNUS,
            category="Throughout Program",
            program=other.name,
        )
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort(wrong.name, person.name)
        self.assertIn("Alumni Profile", str(ctx.exception))

    def test_the_bound_rule_refuses_a_type_with_nothing_bound(self):
        """The rule reads the binding, so a type without one has no question.

        It used to accept an alumnus of anywhere, which is leadership granted on
        a scope the school never named. That meaning now has its own option.
        """
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort_type(leader_eligibility=ALUMNUS)
        self.assertIn(ANY_ALUMNUS, str(ctx.exception))

    def test_any_alumnus_asks_only_for_a_profile(self):
        program = fx.make_program()
        alum = fx.make_person("Alum")
        fx.make_alumni_profile(alum, program_completed=program.name)
        plain = fx.make_person("Plain")

        t = fx.make_cohort_type(leader_eligibility=ANY_ALUMNUS)
        self.assertTrue(fx.make_cohort(t.name, alum.name).name)

        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort(t.name, plain.name)
        self.assertIn("Alumni Profile", str(ctx.exception))

    def test_any_alumnus_ignores_a_binding_it_happens_to_have(self):
        """The two options differ in what they read, not in who they let in."""
        program = fx.make_program()
        other = fx.make_program()
        person = fx.make_person("Alum")
        fx.make_alumni_profile(person, program_completed=other.name)

        t = fx.make_cohort_type(
            leader_eligibility=ANY_ALUMNUS,
            category="Throughout Program",
            program=program.name,
        )
        self.assertTrue(fx.make_cohort(t.name, person.name).name)

    def test_a_disabled_profile_does_not_lead(self):
        program = fx.make_program()
        person = fx.make_person("Alum")
        profile = fx.make_alumni_profile(person, program_completed=program.name)
        frappe.db.set_value("Alumni Profile", profile.name, "enabled", 0)

        t = fx.make_cohort_type(leader_eligibility=ANY_ALUMNUS)
        with self.assertRaises(frappe.ValidationError):
            fx.make_cohort(t.name, person.name)

    def test_the_binding_survives_a_category_the_lifecycle_does_not_use(self):
        """Two reasons to hold a binding; losing the category keeps the other.

        Clearing it on the category change would take away the program and then
        refuse the save for not naming one -- an error about the field the chair
        had just filled in.
        """
        program = fx.make_program()
        t = fx.make_cohort_type(
            leader_eligibility=ALUMNUS,
            category="Throughout Program",
            program=program.name,
        )
        t.category = "Unrestricted"
        t.save(ignore_permissions=True)
        self.assertEqual(t.program, program.name)

    def test_the_binding_still_goes_when_no_rule_reads_it(self):
        program = fx.make_program()
        t = fx.make_cohort_type(category="Throughout Program", program=program.name)
        t.category = "Unrestricted"
        t.save(ignore_permissions=True)
        self.assertIsNone(t.program)

    def test_staff_rule_reads_the_shared_role_set(self):
        user = fx.make_user(roles=("Registrar",))
        staff = fx.make_person("Staff", user=user.name)
        plain = fx.make_person("Plain")
        t = fx.make_cohort_type(leader_eligibility="Staff")

        self.assertTrue(fx.make_cohort(t.name, staff.name).name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort(t.name, plain.name)
        self.assertIn("staff role", str(ctx.exception))


class TestAlumniRunTheirOwnCohorts(IntegrationTestCase):
    """The alumnus-led type a school does not set up cohort by cohort.

    Convincing alumni to come back to a platform they have no other reason to
    open is most of the cost of this kind of programme, and requiring a staff
    member in the desk for every group is most of the friction. These tests
    cover what the school still gets to decide once it stops doing that.
    """

    def setUp(self):
        super().setUp()
        self.program = fx.make_program()
        self.user = fx.make_user()
        self.alum = fx.make_person("Alum", user=self.user.name)
        fx.make_alumni_profile(self.alum, program_completed=self.program.name)
        self.addCleanup(frappe.set_user, "Administrator")

    def _type(self, **kw):
        values = {
            "leader_eligibility": ANY_ALUMNUS,
            "alumni_may_create": 1,
            "portal_size_limit": 2,
        }
        values.update(kw)
        return fx.make_cohort_type(**values)

    # ------------------------------------------------------ the two settings

    def test_the_settings_do_not_survive_a_rule_that_ignores_them(self):
        """A setting that cannot fire is a rule nobody can see."""
        t = self._type()
        t.leader_eligibility = "Instructor"
        t.save(ignore_permissions=True)
        self.assertEqual(t.alumni_may_create, 0)
        self.assertEqual(t.portal_size_limit, 0)

    def test_advising_a_size_the_portal_refuses_is_refused(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._type(portal_size_limit=4, default_max_size=10)
        self.assertIn("Portal Size Limit", str(ctx.exception))

    def test_the_limit_stands_in_when_no_size_was_suggested(self):
        t = self._type(portal_size_limit=6)
        cohort = fx.make_cohort(t.name, self.alum.name)
        self.assertEqual(cohort.max_size, 6)

    # ---------------------------------------------------------- starting one

    def test_an_alumnus_starts_their_own(self):
        t = self._type()
        frappe.set_user(self.user.name)
        name = dapi.create_my_cohort("ZZT My Group", t.name)
        self.assertEqual(frappe.db.get_value("Cohort", name, "leader"), self.alum.name)
        self.assertTrue(
            frappe.db.exists(
                "Cohort Membership",
                {"cohort": name, "person": self.alum.name, "is_leader": 1, "active": 1},
            )
        )

    def test_a_type_that_did_not_invite_it_refuses(self):
        t = self._type(alumni_may_create=0)
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.PermissionError):
            dapi.create_my_cohort("ZZT My Group", t.name)

    def test_the_leadership_rule_still_decides_who(self):
        """`alumni_may_create` says the setting up is self-service; it does not
        say who may lead.

        And it is refused before the Cohort is written. Letting the membership
        rule catch it leaves a leaderless cohort behind for anything that
        handles the exception short of the request.
        """
        other = fx.make_program()
        t = self._type(
            leader_eligibility=ALUMNUS,
            category="Throughout Program",
            program=other.name,
        )
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.PermissionError) as ctx:
            dapi.create_my_cohort("ZZT Not Mine", t.name)
        self.assertIn(other.name, str(ctx.exception))
        self.assertFalse(frappe.db.exists("Cohort", {"cohort_name": "ZZT Not Mine"}))

    def test_the_picker_offers_only_what_this_person_may_lead(self):
        mine = self._type()
        theirs = self._type(
            leader_eligibility=ALUMNUS,
            category="Throughout Program",
            program=fx.make_program().name,
        )
        staff_only = self._type(alumni_may_create=0)

        frappe.set_user(self.user.name)
        offered = {t["cohort_type"] for t in dapi.my_communities() if t["may_start"]}
        self.assertIn(mine.name, offered)
        self.assertNotIn(theirs.name, offered)
        self.assertNotIn(staff_only.name, offered)

    def test_someone_with_no_profile_here_is_offered_nothing(self):
        self._type()
        stranger = fx.make_user()
        frappe.set_user(stranger.name)
        self.assertEqual(dapi.my_communities(), [])


class TestMyCommunities(IntegrationTestCase):
    """The three things the portal can tell someone about a cohort type.

    They are in one, they have been asked to join one, or they are in none and
    may begin -- read off two facts, their open memberships and whether the type
    would let them start another.
    """

    def setUp(self):
        super().setUp()
        self.program = fx.make_program()
        self.user = fx.make_user()
        self.alum = fx.make_person("Alum", user=self.user.name)
        fx.make_alumni_profile(self.alum, program_completed=self.program.name)
        self.addCleanup(frappe.set_user, "Administrator")

    def _type(self, **kw):
        values = {"leader_eligibility": ANY_ALUMNUS, "alumni_may_create": 1}
        values.update(kw)
        return fx.make_cohort_type(**values)

    def _shepherd(self, program=None):
        """Somebody else's leader -- who, on these types, is an alumnus too."""
        person = fx.make_person("Shepherd")
        fx.make_alumni_profile(person, program_completed=program or self.program.name)
        return person

    def _row(self, cohort_type):
        return next(
            (r for r in dapi.my_communities() if r["cohort_type"] == cohort_type), None
        )

    def test_belonging_to_none_is_an_offer_to_start(self):
        t = self._type()
        frappe.set_user(self.user.name)
        row = self._row(t.name)
        self.assertEqual(row["memberships"], [])
        self.assertTrue(row["may_start"])

    def test_a_membership_is_reported_with_who_leads_it(self):
        t = self._type()
        leader = self._shepherd()
        cohort = fx.make_cohort(t.name, leader.name)
        fx.add_member(cohort.name, self.alum.name)

        frappe.set_user(self.user.name)
        (m,) = self._row(t.name)["memberships"]
        self.assertEqual(m["cohort"], cohort.name)
        self.assertEqual(m["invite_status"], "Active")
        self.assertFalse(m["is_leader"])
        self.assertEqual(m["leader_name"], leader.full_name)
        self.assertEqual(m["member_count"], 2)

    def test_an_invitation_is_its_own_state(self):
        """Not filtered out: an invitation is one of the three things to say,
        and dropping it would show an offer to start instead."""
        t = self._type()
        cohort = fx.make_cohort(t.name, self._shepherd().name)
        fx.add_member(cohort.name, self.alum.name, status="Invited")

        frappe.set_user(self.user.name)
        (m,) = self._row(t.name)["memberships"]
        self.assertEqual(m["invite_status"], "Invited")

    def test_being_in_one_withdraws_the_offer_where_only_one_is_allowed(self):
        t = self._type()  # default: one cohort per member
        cohort = fx.make_cohort(t.name, self._shepherd().name)
        fx.add_member(cohort.name, self.alum.name)

        frappe.set_user(self.user.name)
        row = self._row(t.name)
        self.assertEqual(len(row["memberships"]), 1)
        self.assertFalse(row["may_start"])

    def test_both_are_offered_where_more_than_one_is_allowed(self):
        t = self._type(max_lineages_per_member=0)
        cohort = fx.make_cohort(t.name, self._shepherd().name)
        fx.add_member(cohort.name, self.alum.name)

        frappe.set_user(self.user.name)
        row = self._row(t.name)
        self.assertEqual(len(row["memberships"]), 1)
        self.assertTrue(row["may_start"])

    def test_a_type_they_can_neither_join_nor_start_is_left_out(self):
        t = self._type(
            leader_eligibility=ALUMNUS,
            category="Throughout Program",
            program=fx.make_program().name,
        )
        frappe.set_user(self.user.name)
        self.assertIsNone(self._row(t.name))

    def test_a_membership_shows_even_where_they_could_never_start_one(self):
        """Someone placed in a cohort of a type they are not eligible to lead
        still belongs to it, and the page is about where they stand."""
        theirs = fx.make_program()
        t = self._type(
            leader_eligibility=ALUMNUS,
            category="Throughout Program",
            program=theirs.name,
        )
        cohort = fx.make_cohort(t.name, self._shepherd(theirs.name).name)
        fx.add_member(cohort.name, self.alum.name)

        frappe.set_user(self.user.name)
        row = self._row(t.name)
        self.assertEqual(len(row["memberships"]), 1)
        self.assertFalse(row["may_start"])

    def test_a_family_is_named_only_when_it_is_larger_than_one(self):
        t = self._type(max_lineages_per_member=0, allow_self_split=1)
        leader = self._shepherd()
        parent = fx.make_cohort(t.name, leader.name)
        row = fx.add_member(parent.name, self.alum.name)

        frappe.set_user(self.user.name)
        (before,) = self._row(t.name)["memberships"]
        self.assertIsNone(before["lineage_name"])
        self.assertEqual(before["lineage_size"], 1)

        frappe.set_user("Administrator")
        child = dapi.split_cohort(
            parent.name,
            "ZZT Offshoot",
            frappe.as_json([row.name]),
            new_leader=leader.name,
        )

        frappe.set_user(self.user.name)
        moved = next(
            m for m in self._row(t.name)["memberships"] if m["cohort"] == child
        )
        self.assertEqual(moved["lineage_name"], parent.cohort_name)
        self.assertEqual(moved["lineage_size"], 2)

    # ------------------------------------------------------------- the limit

    def test_the_portal_refuses_past_the_limit(self):
        t = self._type(portal_size_limit=2)
        cohort = fx.make_cohort(t.name, self.alum.name)  # leader is seat 1
        fx.add_member(cohort.name, fx.make_person("M1").name)  # seat 2

        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            dapi.invite_member(cohort.name, person=fx.make_person("M2").name)
        self.assertIn("2", str(ctx.exception))

    def test_unanswered_invitations_count_toward_it(self):
        """Otherwise twenty invitations to a group of twelve walk straight past."""
        t = self._type(portal_size_limit=2)
        cohort = fx.make_cohort(t.name, self.alum.name)
        fx.add_member(cohort.name, fx.make_person("Pending").name, status="Invited")

        # Only the leader has actually joined, so the advisory ceiling would not
        # have fired here. The hard one still does.
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.ValidationError):
            dapi.invite_member(cohort.name, person=fx.make_person("M2").name)

    def test_staff_are_warned_where_the_portal_is_refused(self):
        """§7.4 is untouched for the people it was written about."""
        t = self._type(portal_size_limit=2)
        cohort = fx.make_cohort(t.name, self.alum.name)
        fx.add_member(cohort.name, fx.make_person("M1").name)

        membership = dapi.invite_member(cohort.name, person=fx.make_person("M2").name)
        self.assertTrue(membership)

    def test_no_limit_leaves_the_portal_as_it_was(self):
        t = self._type(portal_size_limit=0)
        cohort = fx.make_cohort(t.name, self.alum.name)
        frappe.set_user(self.user.name)
        self.assertTrue(
            dapi.invite_member(cohort.name, person=fx.make_person("M1").name)
        )


class TestCohortsPerMember(IntegrationTestCase):
    """How many cohorts of one type a person may be in at once.

    Counted by lineage: a cohort and everything split off from it are one
    commitment, made once.
    """

    def setUp(self):
        super().setUp()
        self.person = fx.make_person("Member")
        self.leader = fx.make_person("Leader")
        self.type = fx.make_cohort_type()
        self.addCleanup(frappe.set_user, "Administrator")

    def test_one_is_the_answer_a_new_type_starts_with(self):
        self.assertEqual(self.type.max_lineages_per_member, 1)

    def test_a_second_cohort_of_the_same_type_is_refused(self):
        first = fx.make_cohort(self.type.name, self.leader.name)
        fx.add_member(first.name, self.person.name)

        second = fx.make_cohort(self.type.name, fx.make_person("Other").name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.add_member(second.name, self.person.name)
        self.assertIn(self.type.name, str(ctx.exception))

    def test_another_type_is_a_different_question(self):
        first = fx.make_cohort(self.type.name, self.leader.name)
        fx.add_member(first.name, self.person.name)

        elsewhere = fx.make_cohort(
            fx.make_cohort_type().name, fx.make_person("Other").name
        )
        self.assertTrue(fx.add_member(elsewhere.name, self.person.name).name)

    def test_a_closed_membership_frees_the_seat(self):
        first = fx.make_cohort(self.type.name, self.leader.name)
        row = fx.add_member(first.name, self.person.name)
        row.invite_status = "Left"
        row.save(ignore_permissions=True)

        second = fx.make_cohort(self.type.name, fx.make_person("Other").name)
        self.assertTrue(fx.add_member(second.name, self.person.name).name)

    def test_a_pending_invitation_holds_the_seat(self):
        first = fx.make_cohort(self.type.name, self.leader.name)
        fx.add_member(first.name, self.person.name, status="Invited")

        second = fx.make_cohort(self.type.name, fx.make_person("Other").name)
        with self.assertRaises(frappe.ValidationError):
            fx.add_member(second.name, self.person.name)

    def test_a_split_stays_one_lineage(self):
        """The whole reason it counts roots and not cohorts.

        A leader multiplying their group must not use up their members'
        allowance doing it -- they made one commitment, and it grew.
        """
        frappe.db.set_value("Cohort Type", self.type.name, "allow_self_split", 1)
        parent = fx.make_cohort(self.type.name, self.leader.name)
        row = fx.add_member(parent.name, self.person.name)

        # The split seats `person` over the offshoot and keeps `leader`
        # connected to it as a Mentor -- a brand new membership, in a second
        # cohort, for someone already open in the first. Counting cohorts rather
        # than roots would refuse the split its own author.
        child = dapi.split_cohort(
            parent.name,
            "ZZT Offshoot",
            frappe.as_json([row.name]),
            new_leader=self.person.name,
        )
        self.assertEqual(
            frappe.db.get_value("Cohort", child, "lineage_root"),
            frappe.db.get_value("Cohort", parent.name, "lineage_root"),
        )
        self.assertTrue(
            frappe.db.exists(
                "Cohort Membership",
                {"cohort": child, "person": self.leader.name, "active": 1},
            )
        )
        self.assertTrue(
            frappe.db.exists(
                "Cohort Membership",
                {"cohort": parent.name, "person": self.leader.name, "active": 1},
            )
        )

    def test_zero_means_as_many_as_they_like(self):
        frappe.db.set_value("Cohort Type", self.type.name, "max_lineages_per_member", 0)
        first = fx.make_cohort(self.type.name, self.leader.name)
        fx.add_member(first.name, self.person.name)
        second = fx.make_cohort(self.type.name, fx.make_person("Other").name)
        self.assertTrue(fx.add_member(second.name, self.person.name).name)

    def test_lowering_it_never_breaks_what_already_stands(self):
        """A rule tightened this week must not make a record unsaveable while
        somebody edits it for an unrelated reason."""
        frappe.db.set_value("Cohort Type", self.type.name, "max_lineages_per_member", 0)
        first = fx.make_cohort(self.type.name, self.leader.name)
        fx.add_member(first.name, self.person.name)
        second = fx.make_cohort(self.type.name, fx.make_person("Other").name)
        row = fx.add_member(second.name, self.person.name)

        frappe.db.set_value("Cohort Type", self.type.name, "max_lineages_per_member", 1)
        row.reload()
        row.role = "Mentor"
        row.save(ignore_permissions=True)  # must not raise

    def test_a_course_scoped_type_cannot_hold_the_limit(self):
        """One cohort per course, and a student takes several at once."""
        t = fx.make_cohort_type(category="Course scoped", max_lineages_per_member=1)
        self.assertEqual(t.max_lineages_per_member, 0)

    def test_it_caps_how_many_an_alumnus_can_gather(self):
        """The size limit is per cohort; ten cohorts of twelve would be within
        it. This is what stops that."""
        program = fx.make_program()
        user = fx.make_user()
        alum = fx.make_person("Alum", user=user.name)
        fx.make_alumni_profile(alum, program_completed=program.name)
        t = fx.make_cohort_type(
            leader_eligibility=ANY_ALUMNUS, alumni_may_create=1, portal_size_limit=5
        )

        frappe.set_user(user.name)
        self.assertTrue(dapi.create_my_cohort("ZZT Mine", t.name))
        with self.assertRaises(frappe.ValidationError) as ctx:
            dapi.create_my_cohort("ZZT Mine Too", t.name)
        self.assertIn("as many as", str(ctx.exception))


class TestArchivingAndTheSeat(IntegrationTestCase):
    """§7.6, revisited — what archiving does to the people in the cohort.

    Ending a group and ending its members' place in it are the same act for
    most types and different acts for one: a cohort bound to a single Program
    belonged to that degree, and so does the record of having been in it.
    Everywhere else the seat has to come free, or a group that ended years ago
    keeps someone out of one they now need.
    """

    def setUp(self):
        super().setUp()
        self.leader = fx.make_person("Leader")
        self.member = fx.make_person("Member")

    def _archive(self, cohort):
        doc = frappe.get_doc("Cohort", cohort.name)
        doc.status = "Archived"
        doc.save(ignore_permissions=True)

    def _reactivate(self, cohort):
        doc = frappe.get_doc("Cohort", cohort.name)
        doc.status = "Active"
        doc.save(ignore_permissions=True)

    def _standing(self, cohort, person):
        return frappe.db.get_value(
            "Cohort Membership",
            {"cohort": cohort.name, "person": person.name},
            ["invite_status", "active", "closed_by_archive"],
            as_dict=True,
        )

    # --------------------------------------------------- what the rule says

    def test_a_program_bound_type_keeps_them(self):
        program = fx.make_program()
        t = fx.make_cohort_type(category="Throughout Program", program=program.name)
        cohort = fx.make_cohort(t.name, self.leader.name)
        fx.add_member(cohort.name, self.member.name)

        self._archive(cohort)
        standing = self._standing(cohort, self.member)
        self.assertEqual(standing.invite_status, "Active")
        self.assertFalse(standing.closed_by_archive)

    def test_a_level_bound_type_releases_them(self):
        """The MACL-then-MACE case: the type spans the level, and a cohort that
        ended with the first degree must not block a cohort for the second."""
        level = fx.make_program_level()
        if not level:
            self.skipTest("site has no Program Level")
        t = fx.make_cohort_type(category="Throughout Program", program_level=level)
        cohort = fx.make_cohort(t.name, self.leader.name)
        fx.add_member(cohort.name, self.member.name)

        self._archive(cohort)
        standing = self._standing(cohort, self.member)
        self.assertEqual(standing.invite_status, "Left")
        self.assertFalse(standing.active)
        self.assertTrue(standing.closed_by_archive)

        # And the seat is genuinely free.
        later = fx.make_cohort(t.name, fx.make_person("Later").name)
        self.assertTrue(fx.add_member(later.name, self.member.name).name)

    def test_a_course_scoped_type_keeps_them(self):
        """Not only because the offering runs once. The seeding a registrar does
        for the next course in a sequence reads active memberships to know who
        is already placed -- releasing would make archiving last term's groups
        offer to place everybody again."""
        t = fx.make_cohort_type(category="Course scoped")
        cohort = fx.make_cohort(t.name, self.leader.name)
        fx.add_member(cohort.name, self.member.name)

        self._archive(cohort)
        self.assertEqual(self._standing(cohort, self.member).invite_status, "Active")
        self.assertEqual(
            enrollment_mod.active_cohort_of_type(self.member.name, t.name), cohort.name
        )

    def test_an_unrestricted_type_releases_them(self):
        t = fx.make_cohort_type()  # Unrestricted, the alumni-cohort shape
        cohort = fx.make_cohort(t.name, self.leader.name)
        fx.add_member(cohort.name, self.member.name)

        self._archive(cohort)
        self.assertEqual(self._standing(cohort, self.member).invite_status, "Left")

    def test_the_leader_is_released_too(self):
        """Unlike a withdrawal, which leaves them in place because the cohort
        still needs one. An archived cohort needs nobody, and the leader is the
        person who most needs to be free to begin again."""
        t = fx.make_cohort_type()
        cohort = fx.make_cohort(t.name, self.leader.name)

        self._archive(cohort)
        self.assertEqual(self._standing(cohort, self.leader).invite_status, "Left")
        self.assertTrue(fx.make_cohort(t.name, self.leader.name).name)

    def test_the_school_may_overrule_the_category(self):
        program = fx.make_program()
        t = fx.make_cohort_type(
            category="Throughout Program",
            program=program.name,
            on_archive="Release members",
        )
        cohort = fx.make_cohort(t.name, self.leader.name)
        fx.add_member(cohort.name, self.member.name)

        self._archive(cohort)
        self.assertEqual(self._standing(cohort, self.member).invite_status, "Left")

    def test_keeping_them_is_also_a_choice(self):
        t = fx.make_cohort_type(on_archive="Keep members in it")
        cohort = fx.make_cohort(t.name, self.leader.name)
        fx.add_member(cohort.name, self.member.name)

        self._archive(cohort)
        self.assertEqual(self._standing(cohort, self.member).invite_status, "Active")

    # ------------------------------------------------- what must not be lost

    def test_the_record_of_having_been_there_survives(self):
        """§7.6's promise: the seat goes, the account of it does not."""
        user = fx.make_user()
        member = fx.make_person("Seen", user=user.name)
        t = fx.make_cohort_type()
        cohort = fx.make_cohort(t.name, self.leader.name)
        fx.add_member(cohort.name, member.name)

        self._archive(cohort)
        self.assertIn(cohort.name, dperm.visible_cohorts(user.name))
        self.assertNotIn(cohort.name, dperm.led_cohorts(user.name))

    def test_someone_who_had_already_left_is_not_given_it_back(self):
        """Leaving early was their own decision; archiving does not revisit it."""
        user = fx.make_user()
        gone = fx.make_person("Gone", user=user.name)
        t = fx.make_cohort_type()
        cohort = fx.make_cohort(t.name, self.leader.name)
        row = fx.add_member(cohort.name, gone.name)
        row.invite_status = "Left"
        row.save(ignore_permissions=True)

        self._archive(cohort)
        self.assertFalse(self._standing(cohort, gone).closed_by_archive)
        self.assertNotIn(cohort.name, dperm.visible_cohorts(user.name))

    # ------------------------------------------------------- the way back

    def test_reactivating_puts_them_back(self):
        t = fx.make_cohort_type()
        cohort = fx.make_cohort(t.name, self.leader.name)
        fx.add_member(cohort.name, self.member.name)

        self._archive(cohort)
        self._reactivate(cohort)
        standing = self._standing(cohort, self.member)
        self.assertEqual(standing.invite_status, "Active")
        self.assertFalse(standing.closed_by_archive)

    def test_reactivating_leaves_behind_whoever_moved_on(self):
        """They made a newer commitment, and the type allows only the one."""
        t = fx.make_cohort_type()
        cohort = fx.make_cohort(t.name, self.leader.name)
        fx.add_member(cohort.name, self.member.name)
        self._archive(cohort)

        elsewhere = fx.make_cohort(t.name, fx.make_person("Other").name)
        fx.add_member(elsewhere.name, self.member.name)

        self._reactivate(cohort)
        self.assertEqual(self._standing(cohort, self.member).invite_status, "Left")
        self.assertEqual(
            frappe.db.get_value(
                "Cohort Membership",
                {"cohort": elsewhere.name, "person": self.member.name},
                "invite_status",
            ),
            "Active",
        )

    def test_the_portal_route_goes_through_the_document(self):
        """`db.set_value` would skip the release and leave the status saying one
        thing while the roster said another."""
        t = fx.make_cohort_type()
        cohort = fx.make_cohort(t.name, self.leader.name)
        fx.add_member(cohort.name, self.member.name)

        dapi.set_cohort_status(cohort.name, "Archived")
        self.assertEqual(self._standing(cohort, self.member).invite_status, "Left")


class TestMaxSizeIsAdvice(IntegrationTestCase):
    """§7.4 — the ceiling warns; it does not refuse."""

    def test_a_full_cohort_warns_instead_of_throwing(self):
        person = fx.make_person("Leader")
        t = fx.make_cohort_type()
        cohort = fx.make_cohort(t.name, person.name)
        frappe.db.set_value("Cohort", cohort.name, "max_size", 1)

        before = len(frappe.local.message_log or [])
        dapi._warn_if_full(cohort.name)
        self.assertGreater(len(frappe.local.message_log or []), before)

    def test_a_cohort_with_room_says_nothing(self):
        person = fx.make_person("Leader")
        t = fx.make_cohort_type()
        cohort = fx.make_cohort(t.name, person.name)
        frappe.db.set_value("Cohort", cohort.name, "max_size", 5)

        before = len(frappe.local.message_log or [])
        dapi._warn_if_full(cohort.name)
        self.assertEqual(len(frappe.local.message_log or []), before)

    def test_the_old_refusal_is_gone(self):
        self.assertFalse(hasattr(dapi, "_assert_room"))


class CompetencyCohortCase(IntegrationTestCase):
    """Shared spine for the tests that need a framework and an enrollment."""

    def setUp(self):
        super().setUp()
        if not fx.cbe_grading_scale():
            self.skipTest("site has no competency-based grading scale")
        self.cohort_type = fx.make_cohort_type()
        self.framework = fx.make_framework(cohort_type=self.cohort_type.name)
        self.category = self.framework.evaluators[0].instructor_category
        self.program = fx.make_program(framework=self.framework.name)
        self.student = fx.make_student()
        self.enrollment = fx.make_enrollment(self.student, self.program)
        self.instructor = fx.make_instructor()
        self.cohort = fx.make_cohort(self.cohort_type.name, self.instructor.person)
        fx.add_member(self.cohort.name, self.student.person)
        fx.bust_cbe_cache()

    def unname_the_type(self):
        """Point the framework's evaluator at nothing, leaving the cohort intact."""
        fw = frappe.get_doc("Competency Framework", self.framework.name)
        fw.evaluators[0].cohort_type = None
        fw.save(ignore_permissions=True)
        fx.bust_cbe_cache()


class TestAcademicPrivilege(CompetencyCohortCase):
    """§5 — both halves must hold: they mentor, and the framework names the type."""

    def test_naming_the_type_grants_access(self):
        self.assertIn(self.instructor.name, cbe.mentors_of_student(self.student.name))
        self.assertTrue(cbe.is_mentor_of(self.instructor.name, self.student.name))
        self.assertIn(self.student.name, cbe.mentees_of(self.instructor.name))

    def test_an_unnamed_cohort_type_grants_nothing(self):
        self.unname_the_type()
        self.assertNotIn(
            self.instructor.name, cbe.mentors_of_student(self.student.name)
        )
        self.assertNotIn(self.student.name, cbe.mentees_of(self.instructor.name))
        # The relationship itself is untouched — only the privilege is gone.
        self.assertIn(
            self.instructor.name,
            cbe.cohort_mentors(self.student.name, self.cohort_type.name),
        )

    def test_a_peer_mentor_without_an_instructor_record_confers_nothing(self):
        """Pattern b is safe by construction: the Person→Instructor hop simply
        does not resolve, so there is no rule anyone has to remember."""
        peer = fx.make_person("PeerMentor")
        fx.add_member(self.cohort.name, peer.name, role="Mentor")
        fx.bust_cbe_cache()

        mentors = cbe.mentors_of_student(self.student.name)
        self.assertNotIn(peer.name, mentors)
        self.assertIn(self.instructor.name, mentors)

    def test_closing_the_membership_ends_access(self):
        row = frappe.get_doc(
            "Cohort Membership",
            frappe.db.get_value(
                "Cohort Membership",
                {"cohort": self.cohort.name, "person": self.instructor.person},
                "name",
            ),
        )
        row.invite_status = "Left"
        row.save(ignore_permissions=True)
        fx.bust_cbe_cache()
        self.assertNotIn(
            self.instructor.name, cbe.mentors_of_student(self.student.name)
        )

    def test_an_archived_cohort_resolves_nobody(self):
        frappe.db.set_value("Cohort", self.cohort.name, "status", "Archived")
        fx.bust_cbe_cache()
        self.assertNotIn(
            self.instructor.name, cbe.mentors_of_student(self.student.name)
        )

    def test_a_framework_may_not_draw_on_two_cohort_types(self):
        """§7.9 — two types would answer grading and access twice."""
        second = fx.make_cohort_type()
        other_category = frappe.get_all(
            "Instructor Category",
            filters={"name": ("!=", self.category)},
            limit=1,
            pluck="name",
        )
        if not other_category:
            self.skipTest("site has only one Instructor Category")
        fw = frappe.get_doc("Competency Framework", self.framework.name)
        fw.append(
            "evaluators",
            {
                "instructor_category": other_category[0],
                "assignment_source": "Program Cohort",
                "cohort_type": second.name,
                "gives_competency_verdict": 1,
            },
        )
        with self.assertRaises(frappe.ValidationError) as ctx:
            fw.save(ignore_permissions=True)
        self.assertIn("two kinds of cohort", str(ctx.exception))

    def test_two_capacities_over_one_cohort_type_are_fine(self):
        other_category = frappe.get_all(
            "Instructor Category",
            filters={"name": ("!=", self.category)},
            limit=1,
            pluck="name",
        )
        if not other_category:
            self.skipTest("site has only one Instructor Category")
        fw = frappe.get_doc("Competency Framework", self.framework.name)
        fw.append(
            "evaluators",
            {
                "instructor_category": other_category[0],
                "assignment_source": "Program Cohort",
                "cohort_type": self.cohort_type.name,
                "gives_competency_verdict": 1,
            },
        )
        fw.save(ignore_permissions=True)
        self.assertEqual(len(fw.evaluators), 2)

    def test_the_retired_assignment_source_is_gone(self):
        options = (
            frappe.get_meta("Competency Framework Evaluator")
            .get_field("assignment_source")
            .options
        )
        self.assertNotIn("Program Enrollment Mentor", options)
        self.assertIn("Program Cohort", options)


class TestDerivedMentors(CompetencyCohortCase):
    """§4 — the cohort is the source; the enrollment displays what follows."""

    def _mine(self, rows, instructor):
        return [m for m in rows if m["instructor"] == instructor]

    def test_a_cohort_mentor_is_reported_as_derived(self):
        rows = self._mine(
            cbe.mentors_for_enrollment(self.enrollment.name), self.instructor.name
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], cbe.DERIVED)
        self.assertEqual(rows[0]["cohort"], self.cohort.name)

    def test_derivation_writes_no_rows(self):
        """Storing them would be the duplicate roster this ADR removes."""
        cbe.mentors_for_enrollment(self.enrollment.name)
        self.assertEqual(
            frappe.db.count(
                "Program Enrollment Mentor", {"parent": self.enrollment.name}
            ),
            0,
        )

    def test_an_authored_mentor_no_cohort_supplies_is_kept(self):
        other = fx.make_instructor()
        pe = frappe.get_doc("Program Enrollment", self.enrollment.name)
        pe.append(
            "mentors",
            {
                "instructor": other.name,
                "instructor_name": other.instructor_name,
                "instructor_category": self.category,
                "from_date": frappe.utils.today(),
                "active": 1,
            },
        )
        pe.save(ignore_permissions=True)
        fx.bust_cbe_cache()

        rows = cbe.mentors_for_enrollment(pe.name)
        self.assertEqual({m["source"] for m in rows}, {cbe.DERIVED, cbe.AUTHORED})

    def test_an_authored_duplicate_of_a_derived_mentor_is_suppressed(self):
        """Two rows would read as two mentorships where there is one."""
        pe = frappe.get_doc("Program Enrollment", self.enrollment.name)
        pe.append(
            "mentors",
            {
                "instructor": self.instructor.name,
                "instructor_name": self.instructor.instructor_name,
                "instructor_category": self.category,
                "from_date": frappe.utils.today(),
                "active": 1,
            },
        )
        pe.save(ignore_permissions=True)
        fx.bust_cbe_cache()

        rows = self._mine(cbe.mentors_for_enrollment(pe.name), self.instructor.name)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], cbe.DERIVED)

    def test_rotating_a_mentor_moves_no_student(self):
        """The inversion's whole point: pattern d costs one membership change."""
        successor = fx.make_instructor()
        old = frappe.get_doc(
            "Cohort Membership",
            frappe.db.get_value(
                "Cohort Membership",
                {"cohort": self.cohort.name, "person": self.instructor.person},
                "name",
            ),
        )
        old.invite_status = "Left"
        old.save(ignore_permissions=True)
        fx.add_member(self.cohort.name, successor.person, role="Mentor")
        fx.bust_cbe_cache()

        derived = [
            m
            for m in cbe.mentors_for_enrollment(self.enrollment.name)
            if m["source"] == cbe.DERIVED
        ]
        self.assertEqual([m["instructor"] for m in derived], [successor.name])
        self.assertTrue(
            frappe.db.exists(
                "Cohort Membership",
                {
                    "cohort": self.cohort.name,
                    "person": self.student.person,
                    "active": 1,
                },
            )
        )

    def test_the_enrollment_panel_shows_only_derived_rows(self):
        panel = cbe.enrollment_mentor_panel(self.enrollment.name)
        self.assertIn(self.cohort.name, panel["html"])
        self.assertIn("change the cohort's membership", panel["html"])
        self.assertTrue(all(m["source"] == cbe.DERIVED for m in panel["rows"]))

    def test_the_mentor_report_carries_the_source(self):
        report = frappe.get_doc("Report", "Program Enrollments by Mentor")
        columns, rows = report.execute_script_report(filters={})
        self.assertTrue(any(c.get("fieldname") == "source" for c in columns))
        ours = [r for r in rows if r.get("program_enrollment") == self.enrollment.name]
        self.assertTrue(ours)
        self.assertEqual(ours[0]["source"], cbe.DERIVED)

    def test_the_coverage_check_counts_a_cohort_mentor(self):
        report = frappe.get_doc("Report", "Program Enrollments by Mentor")
        _columns, rows = report.execute_script_report(filters={"unmentored": 1})
        gap = [
            r
            for r in rows
            if r.get("program_enrollment") == self.enrollment.name
            and r.get("instructor_category") == self.category
        ]
        self.assertFalse(gap)

    def test_the_coverage_check_reports_a_student_with_no_cohort(self):
        frappe.db.set_value(
            "Cohort Membership",
            frappe.db.get_value(
                "Cohort Membership",
                {"cohort": self.cohort.name, "person": self.student.person},
                "name",
            ),
            {"invite_status": "Left", "active": 0},
        )
        fx.bust_cbe_cache()
        report = frappe.get_doc("Report", "Program Enrollments by Mentor")
        _columns, rows = report.execute_script_report(filters={"unmentored": 1})
        gap = [r for r in rows if r.get("program_enrollment") == self.enrollment.name]
        self.assertTrue(gap)


class TestPersistenceIsPerType(IntegrationTestCase):
    """§2 — what the site-wide switch could not say."""

    def test_two_types_may_answer_differently(self):
        persists = fx.make_cohort_type(
            category="Course scoped", persists_across_courses=1
        )
        does_not = fx.make_cohort_type(
            category="Course scoped", persists_across_courses=0
        )
        self.assertTrue(cohorts_persist(persists.name))
        self.assertFalse(cohorts_persist(does_not.name))

    def test_the_default_carries_the_old_site_wide_behaviour(self):
        fresh = fx.make_cohort_type(category="Course scoped")
        self.assertTrue(cohorts_persist(fresh.name))

    def test_no_type_is_not_an_error(self):
        self.assertFalse(cohorts_persist(None))

    def test_the_site_wide_switch_is_gone(self):
        self.assertIsNone(
            frappe.get_meta("Seminary Settings").get_field(
                "cohorts_persist_across_courses"
            )
        )


class TestArchivingAndRetirement(IntegrationTestCase):
    """§7.6 and §7.7 — two fields that used to be inert."""

    def setUp(self):
        super().setUp()
        self.person = fx.make_person("Leader")
        self.type = fx.make_cohort_type()
        self.cohort = fx.make_cohort(self.type.name, self.person.name)

    def test_an_archived_cohort_refuses_changes(self):
        member = fx.make_person("Member")
        frappe.db.set_value("Cohort", self.cohort.name, "status", "Archived")

        for label, call in (
            (
                "invite",
                lambda: dapi.invite_member(self.cohort.name, person=member.name),
            ),
            ("split", lambda: dapi.split_cohort(self.cohort.name, "ZZT child", "[]")),
            (
                "reassign",
                lambda: dapi.reassign_leader(self.cohort.name, member.name),
            ),
        ):
            with self.subTest(action=label):
                with self.assertRaises(frappe.ValidationError) as ctx:
                    call()
                self.assertIn("archived", str(ctx.exception).lower())

    def test_reactivating_is_the_way_back_and_is_not_blocked(self):
        frappe.db.set_value("Cohort", self.cohort.name, "status", "Archived")
        dapi.set_cohort_status(self.cohort.name, "Active")
        self.assertEqual(
            frappe.db.get_value("Cohort", self.cohort.name, "status"), "Active"
        )

    def test_archiving_ends_moderation_but_not_visibility(self):
        user = fx.make_user()
        leader = fx.make_person("ArchLeader", user=user.name)
        cohort = fx.make_cohort(self.type.name, leader.name)
        frappe.db.set_value("Cohort", cohort.name, "status", "Archived")

        self.assertNotIn(cohort.name, dperm.led_cohorts(user.name))
        self.assertIn(cohort.name, dperm.visible_cohorts(user.name))

    def test_a_retired_type_stops_producing_cohorts(self):
        frappe.db.set_value("Cohort Type", self.type.name, "is_active", 0)
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort(self.type.name, self.person.name)
        self.assertIn("not active", str(ctx.exception))

    def test_an_existing_cohort_survives_its_type_being_retired(self):
        frappe.db.set_value("Cohort Type", self.type.name, "is_active", 0)
        doc = frappe.get_doc("Cohort", self.cohort.name)
        doc.cohort_name = doc.cohort_name + " renamed"
        doc.save(ignore_permissions=True)  # must not raise
        self.assertTrue(doc.name)


class TestReleaseOnSeparation(IntegrationTestCase):
    """§7.3 — leaving a program short of finishing it."""

    def setUp(self):
        super().setUp()
        self.program = fx.make_program()
        self.student = fx.make_student()
        self.enrollment = fx.make_enrollment(self.student, self.program)
        self.leader = fx.make_person("Leader")

        self.asks = fx.make_cohort_type(
            category="Throughout Program",
            program=self.program.name,
            remove_on_withdrawal=1,
        )
        self.keeps = fx.make_cohort_type(
            category="Throughout Program", program=self.program.name
        )
        self.c_asks = fx.make_cohort(self.asks.name, self.leader.name)
        self.c_keeps = fx.make_cohort(self.keeps.name, self.leader.name)
        for cohort in (self.c_asks, self.c_keeps):
            fx.add_member(cohort.name, self.student.person)

    def _still_in(self, cohort):
        return bool(
            frappe.db.exists(
                "Cohort Membership",
                {"cohort": cohort, "person": self.student.person, "active": 1},
            )
        )

    def test_all_three_separations_release(self):
        self.assertEqual(
            set(SEPARATION_STATUSES), {"Withdrawn", "Transferred", "Dismissed"}
        )

    def test_graduation_releases_nobody(self):
        """Graduation is `graduates_to` — a move, not a removal."""
        self.assertEqual(release_from_program_cohorts(self.enrollment, "Graduated"), [])
        self.assertTrue(self._still_in(self.c_asks.name))

    def test_dismissal_releases_where_the_type_asks(self):
        closed = release_from_program_cohorts(self.enrollment, "Dismissed")
        self.assertEqual(len(closed), 1)
        self.assertFalse(self._still_in(self.c_asks.name))
        self.assertTrue(self._still_in(self.c_keeps.name))

    def test_withdrawal_releases_where_the_type_asks(self):
        closed = release_from_program_cohorts(self.enrollment, "Withdrawn")
        self.assertEqual(len(closed), 1)
        self.assertFalse(self._still_in(self.c_asks.name))
        self.assertTrue(self._still_in(self.c_keeps.name))

    def test_a_leader_is_not_pulled_out_of_their_own_cohort(self):
        # Deliberately two cohorts of one type -- a member of one, the leader of
        # another -- which is the arrangement `max_lineages_per_member` exists
        # to forbid. The release rule has to be right for a school that allows
        # it, so this type says so.
        frappe.db.set_value("Cohort Type", self.asks.name, "max_lineages_per_member", 0)
        led = fx.make_cohort(self.asks.name, self.student.person)
        release_from_program_cohorts(self.enrollment, "Withdrawn")
        self.assertTrue(
            frappe.db.exists(
                "Cohort Membership",
                {
                    "cohort": led.name,
                    "person": self.student.person,
                    "active": 1,
                    "is_leader": 1,
                },
            )
        )

    def test_the_status_spine_calls_the_release(self):
        import inspect

        from seminary.seminary import program_status

        self.assertIn(
            "release_from_program_cohorts",
            inspect.getsource(program_status._on_terminal),
        )


class TestInstructorCommitments(IntegrationTestCase):
    """§7.1 — visibility instead of automation."""

    def setUp(self):
        super().setUp()
        self.instructor = fx.make_instructor()
        self.type = fx.make_cohort_type()
        self.cohort = fx.make_cohort(self.type.name, self.instructor.person)

    def test_a_led_cohort_is_an_open_commitment(self):
        data = instructor_load.open_commitments(self.instructor.name)
        led = [c for c in data["cohorts"] if c["name"] == self.cohort.name]
        self.assertEqual(len(led), 1)
        self.assertFalse(led[0]["co_led"])
        self.assertGreaterEqual(led[0]["members"], 1)

    def test_co_leadership_is_reported(self):
        """The difference between a warning worth reading and noise."""
        other = fx.make_person("CoLeader")
        fx.add_member(self.cohort.name, other.name, role="Mentor", is_leader=1)
        data = instructor_load.open_commitments(self.instructor.name)
        led = [c for c in data["cohorts"] if c["name"] == self.cohort.name][0]
        self.assertTrue(led["co_led"])

    def test_an_archived_cohort_is_not_a_commitment(self):
        frappe.db.set_value("Cohort", self.cohort.name, "status", "Archived")
        data = instructor_load.open_commitments(self.instructor.name)
        self.assertFalse(any(c["name"] == self.cohort.name for c in data["cohorts"]))

    def test_the_panel_links_to_the_cohort(self):
        html = instructor_load.commitments_html(self.instructor.name)
        self.assertIn(self.cohort.name, html)

    def test_deactivation_warns_and_does_not_refuse(self):
        doc = frappe.get_doc("Instructor", self.instructor.name)
        before = len(frappe.local.message_log or [])
        doc.status = "Inactive"
        doc.save(ignore_permissions=True)
        self.assertGreater(len(frappe.local.message_log or []), before)
        self.assertEqual(
            frappe.db.get_value("Instructor", self.instructor.name, "status"),
            "Inactive",
        )


class TestCohortsNeedingAttention(IntegrationTestCase):
    """§7.1 and §7.2 — the gaps a person has to resolve."""

    def setUp(self):
        super().setUp()
        self.report = frappe.get_doc("Report", "Cohorts Needing Attention")
        self.type = fx.make_cohort_type()

    def _run(self, **filters):
        filters.setdefault("cohort_type", self.type.name)
        _columns, rows = self.report.execute_script_report(filters=filters)
        return rows

    def test_a_cohort_with_no_active_leader_is_surfaced(self):
        person = fx.make_person("Leaver")
        cohort = fx.make_cohort(self.type.name, person.name)
        frappe.db.set_value(
            "Cohort Membership",
            frappe.db.get_value(
                "Cohort Membership",
                {"cohort": cohort.name, "person": person.name},
                "name",
            ),
            {"is_leader": 0, "invite_status": "Left", "active": 0},
        )
        rows = self._run(issue="no_leader")
        self.assertTrue(any(r["cohort"] == cohort.name for r in rows))

    def test_a_lapsed_instructor_leader_is_surfaced(self):
        instructor = fx.make_instructor()
        cohort = fx.make_cohort(self.type.name, instructor.person)
        frappe.db.set_value("Instructor", instructor.name, "status", "Inactive")

        rows = self._run()
        ours = [r for r in rows if r["cohort"] == cohort.name]
        self.assertTrue(
            any("no longer an active instructor" in (r["issue"] or "") for r in ours)
        )

    def test_a_peer_led_cohort_is_flagged_by_nothing(self):
        """Pattern b is ordinary, not a defect."""
        peer = fx.make_person("Peer")
        cohort = fx.make_cohort(self.type.name, peer.name)
        rows = self._run()
        self.assertFalse(any(r["cohort"] == cohort.name for r in rows))

    def test_a_member_on_leave_is_surfaced_with_their_membership_open(self):
        leader = fx.make_person("Leader")
        cohort = fx.make_cohort(self.type.name, leader.name)
        student = fx.make_student()
        program = fx.make_program()
        enrollment = fx.make_enrollment(student, program)
        fx.add_member(cohort.name, student.person)

        self.assertFalse(
            any(r["cohort"] == cohort.name for r in self._run(issue="member_on_leave"))
        )

        frappe.db.set_value(
            "Program Enrollment", enrollment.name, "status", "Leave of Absence"
        )
        rows = [
            r for r in self._run(issue="member_on_leave") if r["cohort"] == cohort.name
        ]
        self.assertTrue(rows)
        self.assertIn("On leave from", rows[0]["detail"] or "")
        # Nothing closed it: the cohort they return to must still be theirs.
        self.assertTrue(
            frappe.db.exists(
                "Cohort Membership",
                {"cohort": cohort.name, "person": student.person, "active": 1},
            )
        )
