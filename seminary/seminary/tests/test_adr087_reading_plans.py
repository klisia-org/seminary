# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/087: reading plans for cohorts."""

import datetime

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from seminary.seminary.discipleship import reading_plan_pack as pack
from seminary.seminary.discipleship import reading_plans as rp
from seminary.seminary.tests import cohort_fixtures as fx


def _portal_person(label, roles=("Alumni",)):
    user = fx.make_user(roles=roles)
    return fx.make_person(label, user=user.name)


def _ensure_member(cohort, person, is_leader=0):
    name = frappe.db.get_value(
        "Cohort Membership", {"cohort": cohort, "person": person}
    )
    if name:
        frappe.db.set_value(
            "Cohort Membership", name, {"active": 1, "is_leader": is_leader}
        )
        return
    fx.add_member(cohort, person, is_leader=is_leader)


class TestReadingPlans(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.leader = _portal_person("Leader")
        cls.member = _portal_person("Member")
        cls.outsider = _portal_person("Outsider")
        ctype = fx.make_cohort_type()
        cls.cohort = fx.make_cohort(ctype.name, cls.leader.name).name
        _ensure_member(cls.cohort, cls.leader.name, is_leader=1)
        _ensure_member(cls.cohort, cls.member.name)
        other = fx.make_cohort(ctype.name, cls.outsider.name).name
        _ensure_member(other, cls.outsider.name, is_leader=1)
        cls.other_cohort = other

    def tearDown(self):
        frappe.set_user("Administrator")

    def _plan(self, steps=None, plan_type="Bible"):
        frappe.set_user(self.leader.user)
        return rp.save_plan(
            fx.uid("Plan"),
            plan_type,
            None,
            steps
            or [
                {"from_book": "ROM", "from_chapter": 1, "to_chapter": 2},
                {
                    "from_book": "ROM",
                    "from_chapter": 3,
                    "from_verse": 21,
                    "to_verse": 26,
                },
                {"from_book": "ROM", "from_chapter": 5},
            ],
        )

    # ------------------------------------------------------------- steps
    def test_bible_steps_derive_reference_and_ordinals(self):
        plan = frappe.get_doc("Reading Plan", self._plan())
        self.assertEqual([r.step for r in plan.steps], [1, 2, 3])
        self.assertEqual(plan.steps[0].resolved_ref, "ROM.1-ROM.2")
        self.assertEqual(plan.steps[1].resolved_ref, "ROM.3.21-ROM.3.26")
        self.assertEqual(plan.steps[1].reference, "Romans 3:21–26")
        self.assertEqual(plan.steps[2].resolved_ref, "ROM.5")
        self.assertLess(plan.steps[0].verse_start_ord, plan.steps[0].verse_end_ord)
        self.assertEqual(plan.author, self.leader.name)

    def test_cross_book_step(self):
        plan = frappe.get_doc(
            "Reading Plan",
            self._plan(
                [
                    {
                        "from_book": "JUD",
                        "from_chapter": 1,
                        "to_book": "REV",
                        "to_chapter": 2,
                    }
                ]
            ),
        )
        self.assertEqual(plan.steps[0].resolved_ref, "JUD.1-REV.2")

    def test_step_ending_before_it_starts_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            self._plan([{"from_book": "ROM", "from_chapter": 3, "to_chapter": 2}])

    def test_other_step_needs_something_to_read(self):
        with self.assertRaises(frappe.ValidationError):
            self._plan([{"message": "<p>only a note</p>"}], plan_type="Other")
        plan = frappe.get_doc(
            "Reading Plan",
            self._plan(
                [
                    {"reading_text": "Chapter 1 of Life Together"},
                    {"link_url": "https://example.org/paper"},
                ],
                plan_type="Other",
            ),
        )
        self.assertEqual(plan.steps[0].reference, "Chapter 1 of Life Together")
        self.assertEqual(plan.steps[1].reference, "example.org")

    def test_other_step_refuses_unsafe_link(self):
        with self.assertRaises(frappe.ValidationError):
            self._plan([{"link_url": "javascript:alert(1)"}], plan_type="Other")

    def test_step_message_is_sanitised(self):
        plan = frappe.get_doc(
            "Reading Plan",
            self._plan(
                [
                    {
                        "from_book": "JHN",
                        "from_chapter": 1,
                        "message": "<p>Q</p><img src=x onerror=alert(1)>",
                    }
                ]
            ),
        )
        self.assertNotIn("onerror", plan.steps[0].message)

    # -------------------------------------------------------------- lock
    def test_steps_lock_once_started_but_messages_stay_editable(self):
        plan = self._plan()
        rp.start_plan(self.cohort, plan, today())
        steps = rp.get_plan(plan)["steps"]
        reordered = [steps[1], steps[0], steps[2]]
        with self.assertRaises(frappe.ValidationError):
            rp.save_plan("x", "Bible", None, reordered, plan=plan)
        with self.assertRaises(frappe.ValidationError):
            rp.save_plan("x", "Bible", None, steps[:2], plan=plan)
        rp.save_plan(
            "x",
            "Bible",
            None,
            [dict(s, message="<p>new question</p>") for s in steps],
            plan=plan,
        )
        self.assertEqual(
            frappe.get_doc("Reading Plan", plan).steps[2].message, "<p>new question</p>"
        )
        with self.assertRaises(frappe.ValidationError):
            rp.delete_plan(plan)

    def test_standard_plan_is_read_only(self):
        from seminary.install import seed_standard_reading_plans

        seed_standard_reading_plans()
        seed_standard_reading_plans()  # idempotent
        self.assertEqual(
            frappe.db.count("Reading Plan", {"standard_key": "romans-10"}), 1
        )
        name = frappe.db.get_value("Reading Plan", {"standard_key": "romans-10"})
        frappe.set_user(self.leader.user)
        with self.assertRaises(frappe.PermissionError):
            rp.save_plan("x", "Bible", None, [], plan=name)
        copy = rp.duplicate_plan(name)
        doc = frappe.get_doc("Reading Plan", copy)
        self.assertFalse(doc.is_standard)
        self.assertEqual(doc.author, self.leader.name)
        self.assertEqual(len(doc.steps), 10)

    # ------------------------------------------------------------ access
    def test_only_leaders_and_staff_author_and_list(self):
        frappe.set_user(self.member.user)
        with self.assertRaises(frappe.PermissionError):
            rp.list_plans()
        with self.assertRaises(frappe.PermissionError):
            rp.save_plan("x", "Bible", None, [])

    def test_member_sees_only_plans_their_cohort_runs(self):
        plan = self._plan()
        unused = self._plan()
        rp.start_plan(self.cohort, plan, today())
        frappe.set_user(self.member.user)
        self.assertEqual(rp.get_plan(plan)["name"], plan)
        with self.assertRaises(frappe.PermissionError):
            rp.get_plan(unused)
        names = set(frappe.get_list("Reading Plan", pluck="name"))
        self.assertIn(plan, names)
        self.assertNotIn(unused, names)

    def test_only_this_cohorts_leader_starts_a_run(self):
        plan = self._plan()
        frappe.set_user(self.outsider.user)
        with self.assertRaises(frappe.PermissionError):
            rp.start_plan(self.cohort, plan, today())
        frappe.set_user(self.member.user)
        with self.assertRaises(frappe.PermissionError):
            rp.start_plan(self.cohort, plan, today())

    def test_author_edits_other_leader_cannot(self):
        plan = self._plan()
        frappe.set_user(self.outsider.user)
        with self.assertRaises(frappe.PermissionError):
            rp.save_plan("x", "Bible", None, [], plan=plan)

    # ---------------------------------------------------------- schedule
    def test_schedule_follows_reading_days(self):
        run = frappe._dict(
            start_date=datetime.date(2026, 10, 12),  # a Monday
            monday=1,
            wednesday=1,
            friday=1,
        )
        self.assertEqual(
            rp.step_dates(run, 4),
            [
                datetime.date(2026, 10, 12),
                datetime.date(2026, 10, 14),
                datetime.date(2026, 10, 16),
                datetime.date(2026, 10, 19),
            ],
        )

    def test_schedule_can_skip_public_holidays(self):
        frappe.db.set_default("country", "United States")
        run = frappe._dict(
            start_date=datetime.date(2026, 12, 24),
            skip_public_holidays=1,
            **{d: 1 for d in rp.WEEKDAYS},
        )
        dates = rp.step_dates(run, 3)
        self.assertNotIn(datetime.date(2026, 12, 25), dates)
        run.skip_public_holidays = 0
        self.assertIn(datetime.date(2026, 12, 25), rp.step_dates(run, 3))

    def test_run_needs_a_reading_day(self):
        plan = self._plan()
        with self.assertRaises(frappe.ValidationError):
            rp.start_plan(self.cohort, plan, today(), days=[])

    # ---------------------------------------------------------- progress
    def test_marks_and_behind(self):
        plan = self._plan()
        run = rp.start_plan(self.cohort, plan, add_days(today(), -2))
        frappe.set_user(self.member.user)
        rp.mark_step(run, 1)
        rp.mark_step(run, 1)  # idempotent
        view = rp.get_run(run)
        self.assertEqual(view["behind"], 1)  # step 2 was yesterday
        self.assertEqual(view["current_step"], 3)
        rp.mark_step(run, 1, read=0)
        self.assertEqual(rp.get_run(run)["behind"], 2)
        with self.assertRaises(frappe.PermissionError):
            rp.run_progress(run)
        frappe.set_user(self.outsider.user)
        with self.assertRaises(frappe.PermissionError):
            rp.mark_step(run, 1)
        frappe.set_user(self.leader.user)
        grid = {m["person"]: m for m in rp.run_progress(run)["members"]}
        self.assertEqual(grid[self.member.name]["behind"], 2)

    def test_reminder_only_on_falling_behind(self):
        plan = self._plan()
        run = rp.start_plan(self.cohort, plan, add_days(today(), -2))
        frappe.set_user(self.member.user)
        rp.mark_step(run, 1)
        frappe.set_user("Administrator")
        # Step 2 was yesterday: the member read step 1 and not step 2, so they
        # have just fallen behind; the leader read nothing and was already behind.
        rp.send_behind_reminders()
        logs = frappe.get_all(
            "Communication Log",
            filters={"reference_doctype": "Cohort Reading Plan", "reference_name": run},
            pluck="person",
        )
        self.assertIn(self.member.name, logs)
        self.assertNotIn(self.leader.name, logs)
        # Running again sends nothing new (deduped).
        before = len(logs)
        rp.send_behind_reminders()
        self.assertEqual(
            frappe.db.count("Communication Log", {"reference_name": run}), before
        )

    def test_completed_after_last_step(self):
        plan = self._plan()
        run = rp.start_plan(self.cohort, plan, add_days(today(), -5))
        frappe.set_user("Administrator")
        rp.complete_finished_runs()
        self.assertEqual(
            frappe.db.get_value("Cohort Reading Plan", run, "status"), "Completed"
        )

    # -------------------------------------------------------- discussion
    def test_discussion_draft_prefills_but_posts_nothing(self):
        plan = self._plan()
        run = rp.start_plan(self.cohort, plan, today())
        frappe.set_user(self.member.user)
        posts = frappe.db.count("Cohort Post")
        draft = rp.discussion_draft(run, 2)
        self.assertEqual(draft["cohort"], self.cohort)
        self.assertEqual(draft["reference_doctype"], "Cohort Reading Plan")
        self.assertEqual(draft["scripture"], ["Romans 3:21-26"])
        self.assertEqual(frappe.db.count("Cohort Post"), posts)
        draft = rp.discussion_draft(run, 1)
        self.assertEqual(draft["scripture"], ["Romans 1", "Romans 2"])

    # ------------------------------------------------------------- packs
    def test_pack_round_trip(self):
        plan = self._plan()
        rp.save_plan(
            "Round trip",
            "Bible",
            "desc",
            [dict(s, message="<p>Why?</p>") for s in rp.get_plan(plan)["steps"]],
            plan=plan,
        )
        _name, data = pack.build_pack(plan)
        new = pack.import_pack_from_bytes(data)
        a, b = frappe.get_doc("Reading Plan", plan), frappe.get_doc("Reading Plan", new)
        self.assertNotEqual(a.title, b.title)
        self.assertEqual(b.author, self.leader.name)
        self.assertEqual(
            [(r.resolved_ref, r.message) for r in a.steps],
            [(r.resolved_ref, r.message) for r in b.steps],
        )

    def test_pack_import_drops_unknown_fields_and_refuses_junk(self):
        import io
        import json
        import zipfile

        manifest = {
            "kind": "reading_plan",
            "pack_format_version": 1,
            "plan": {"title": "Imported", "plan_type": "Bible", "is_standard": 1},
            "steps": [
                {"from_book": "MRK", "from_chapter": 1, "owner": "Administrator"}
            ],
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
        frappe.set_user(self.leader.user)
        doc = frappe.get_doc(
            "Reading Plan", pack.import_pack_from_bytes(buf.getvalue())
        )
        self.assertFalse(doc.is_standard)
        self.assertEqual(doc.steps[0].resolved_ref, "MRK.1")
        with self.assertRaises(frappe.ValidationError):
            pack.import_pack_from_bytes(b"not a zip")
        frappe.set_user(self.member.user)
        with self.assertRaises(frappe.PermissionError):
            pack.import_pack_from_bytes(buf.getvalue())

    def test_pack_carries_no_cohort_data(self):
        plan = self._plan()
        run = rp.start_plan(self.cohort, plan, today())
        import io
        import zipfile

        _name, data = pack.build_pack(plan)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            manifest = zf.read("manifest.json").decode()
        self.assertNotIn(run, manifest)
        self.assertNotIn(self.cohort, manifest)
        self.assertNotIn(self.leader.name, manifest)
