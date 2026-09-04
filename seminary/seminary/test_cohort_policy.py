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
from seminary.seminary.discipleship.enrollment import (
    SEPARATION_STATUSES,
    cohorts_persist,
    release_from_program_cohorts,
)
from seminary.seminary.tests import cohort_fixtures as fx

ALUMNUS = "Alumnus of the bound program or level"


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
        t = fx.make_cohort_type(
            category="Throughout Program",
            program=program.name,
            automation_rule="On Program Enrollment",
            automation_max_size=8,
            remove_on_withdrawal=1,
        )
        self.assertEqual(t.automation_rule, "On Program Enrollment")

        t.category = "Unrestricted"
        t.save(ignore_permissions=True)
        self.assertFalse(t.automation_rule)
        self.assertFalse(t.automation_max_size)
        self.assertFalse(t.remove_on_withdrawal)
        self.assertFalse(t.program)

    def test_max_size_without_a_rule_is_cleared(self):
        program = fx.make_program()
        t = fx.make_cohort_type(
            category="Throughout Program", program=program.name, automation_max_size=9
        )
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


class TestGraduationTarget(IntegrationTestCase):
    """§7.15 — graduating into a type is itself that type's automation."""

    def test_a_type_cannot_graduate_into_itself(self):
        program = fx.make_program()
        t = fx.make_cohort_type(category="Throughout Program", program=program.name)
        t.graduates_to = t.name
        with self.assertRaises(frappe.ValidationError) as ctx:
            t.save(ignore_permissions=True)
        self.assertIn("graduate into itself", str(ctx.exception))

    def test_a_receiving_type_may_not_take_an_automation_rule(self):
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
        dest.automation_rule = "On Program Enrollment"
        with self.assertRaises(frappe.ValidationError) as ctx:
            dest.save(ignore_permissions=True)
        self.assertIn("already graduates into this type", str(ctx.exception))

    def test_graduating_into_an_automated_type_is_refused(self):
        program = fx.make_program()
        auto = fx.make_cohort_type(
            category="Throughout Program",
            program=program.name,
            automation_rule="On Program Enrollment",
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

        unbound = fx.make_cohort_type(leader_eligibility=ALUMNUS)
        self.assertTrue(fx.make_cohort(unbound.name, person.name).name)

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

    def test_staff_rule_reads_the_shared_role_set(self):
        user = fx.make_user(roles=("Registrar",))
        staff = fx.make_person("Staff", user=user.name)
        plain = fx.make_person("Plain")
        t = fx.make_cohort_type(leader_eligibility="Staff")

        self.assertTrue(fx.make_cohort(t.name, staff.name).name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            fx.make_cohort(t.name, plain.name)
        self.assertIn("staff role", str(ctx.exception))


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
