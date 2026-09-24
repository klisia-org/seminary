# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p007 §2.1–2.3, §2.8: the Student DocPerm rewrite, the row hooks, the
permlevel-1 grading fields and the instructor tiers, exercised through the
same generic paths the browser uses (``frappe.get_list``, ``doc.save``,
``frappe.has_permission``).

Fixtures are built in-test (the app's Student/Instructor test records predate
Person-first identity), so nothing here depends on test_records.json.
"""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import guards
from seminary.seminary.tests.test_p006_api import _make_user

PREFIX = "ZZT-p007"


def _student_for(user, tag):
    name = frappe.db.get_value("Student", {"user": user}, "name")
    if name:
        return name
    doc = frappe.get_doc(
        {
            "doctype": "Student",
            "first_name": "P007",
            "last_name": tag,
            "student_email_id": user,
            "user": user,
            "enabled": 1,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert(ignore_mandatory=True)
    return doc.name


def _category(name, of_record):
    if not frappe.db.exists("Instructor Category", name):
        frappe.get_doc(
            {
                "doctype": "Instructor Category",
                "category_name": name,
                "is_instructor_of_record": 1 if of_record else 0,
            }
        ).insert(ignore_permissions=True)
    return name


def _instructor_for(user, tag, category=None):
    name = frappe.db.get_value("Instructor", {"user": user}, "name")
    if name:
        return name
    from seminary.seminary import person as person_spine

    person = person_spine.ensure_person(email=user, first_name="P007", last_name=tag)
    doc = frappe.get_doc(
        {
            "doctype": "Instructor",
            "instructor_name": "P007 %s" % tag,
            "user": user,
            "person": person,
            "status": "Active",
            "default_inst_category": category,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert(ignore_mandatory=True)
    # The Instructor DocPerm row is `if_owner`; a record created by staff is
    # not editable by its instructor on Desk (pre-existing, p007 §7.3). Hand
    # the fixture to its user so the permlevel test exercises the field, not
    # the owner rule.
    frappe.db.set_value("Instructor", doc.name, "owner", user, update_modified=False)
    return doc.name


def _any_course_schedule():
    """Two distinct existing sections (any term) to hang fixtures on."""
    rows = frappe.get_all(
        "Course Schedule",
        filters={"workflow_state": ["!=", "Cancelled"]},
        fields=["name", "course"],
        limit=2,
        order_by="creation asc",
    )
    if len(rows) < 2:
        raise frappe.DoesNotExistError("test site needs two Course Schedules")
    return rows[0], rows[1]


def _list_instructor(cs_name, instructor, category=None):
    cs = frappe.get_doc("Course Schedule", cs_name)
    if any(r.instructor == instructor for r in cs.instructor1):
        return
    row = frappe.get_doc(
        {
            "doctype": "Course Schedule Instructors",
            "parent": cs_name,
            "parenttype": "Course Schedule",
            "parentfield": "instructor1",
            "instructor": instructor,
            "instructor_category": category,
            "idx": len(cs.instructor1) + 1,
        }
    )
    row.flags.ignore_permissions = True
    row.insert()
    frappe.local.p007_cache = {}


def _roster(cs_name, student, user):
    name = frappe.db.get_value(
        "Scheduled Course Roster", {"course_sc": cs_name, "student": student}, "name"
    )
    if name:
        return name
    doc = frappe.get_doc(
        {
            "doctype": "Scheduled Course Roster",
            "course_sc": cs_name,
            "student": student,
            "stuemail_rc": user,
            "stuname_roster": "P007 " + student,
            "active": 1,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert(ignore_mandatory=True)
    return doc.name


def _submission(cs_name, student, user, answer="first"):
    name = frappe.db.get_value(
        "Assignment Submission",
        {"course": cs_name, "member": user, "assignment_title": PREFIX},
        "name",
    )
    if name:
        return name
    doc = frappe.get_doc(
        {
            "doctype": "Assignment Submission",
            "course": cs_name,
            "member": user,
            "student": student,
            "answer": answer,
            "status": "Not Graded",
            "grade": 0,
            "assignment_title": PREFIX,
            "type": "Text",
        }
    )
    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory = True
    doc.flags.ignore_links = True
    doc.insert(ignore_mandatory=True)
    # A real submission is inserted by its student; `if_owner` reads `owner`.
    frappe.db.set_value(
        "Assignment Submission", doc.name, "owner", user, update_modified=False
    )
    return doc.name


class TestP007DocPerms(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.cs, cls.cs2 = _any_course_schedule()
        cls.stu_a_user = _make_user("Student", "dp-a")
        cls.stu_b_user = _make_user("Student", "dp-b")
        cls.stu_a = _student_for(cls.stu_a_user, "A")
        cls.stu_b = _student_for(cls.stu_b_user, "B")
        # A student on no roster at all: invisible to a grader.
        cls.stu_c_user = _make_user("Student", "dp-c")
        cls.stu_c = _student_for(cls.stu_c_user, "C")
        cls.record_cat = _category("P007 Of Record", True)
        cls.grader_cat = _category("P007 Grader", False)
        cls.prof_user = _make_user("Instructor", "dp-prof")
        cls.prof = _instructor_for(cls.prof_user, "prof", cls.record_cat)
        cls.other_user = _make_user("Instructor", "dp-other")
        cls.other = _instructor_for(cls.other_user, "other", cls.record_cat)
        cls.gta_user = _make_user("Student", "dp-gta")
        frappe.get_doc("User", cls.gta_user).add_roles("Instructor")
        cls.gta_student = _student_for(cls.gta_user, "GTA")
        cls.gta = _instructor_for(cls.gta_user, "gta", cls.grader_cat)
        _list_instructor(cls.cs.name, cls.prof, cls.record_cat)
        _list_instructor(cls.cs.name, cls.gta, cls.grader_cat)
        _list_instructor(cls.cs2.name, cls.other, cls.record_cat)
        cls.roster_a = _roster(cls.cs.name, cls.stu_a, cls.stu_a_user)
        cls.roster_b = _roster(cls.cs.name, cls.stu_b, cls.stu_b_user)
        cls.sub_a = _submission(cls.cs.name, cls.stu_a, cls.stu_a_user)
        cls.sub_b = _submission(cls.cs.name, cls.stu_b, cls.stu_b_user)
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        frappe.local.p007_cache = {}

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.local.p007_cache = {}

    def _as(self, user):
        frappe.set_user(user)
        frappe.local.p007_cache = {}

    # ------------------------------------------- §8.1 published AND enrolled

    def test_student_reads_a_section_only_when_published_and_enrolled(self):
        was = {
            n: frappe.db.get_value("Course Schedule", n, "published")
            for n in (self.cs.name, self.cs2.name)
        }
        try:
            for n in was:
                frappe.db.set_value("Course Schedule", n, "published", 1)
            self._as(self.stu_a_user)
            # enrolled + published
            self.assertTrue(
                frappe.has_permission("Course Schedule", "read", self.cs.name)
            )
            self.assertTrue(guards.is_enrolled(self.cs.name))
            # published, not enrolled
            self.assertFalse(
                frappe.has_permission("Course Schedule", "read", self.cs2.name)
            )
            listed = frappe.get_list("Course Schedule", pluck="name", limit=0)
            self.assertEqual(listed, [self.cs.name])

            # enrolled, not published: the roster row alone opens nothing
            frappe.set_user("Administrator")
            frappe.db.set_value("Course Schedule", self.cs.name, "published", 0)
            self._as(self.stu_a_user)
            self.assertFalse(
                frappe.has_permission("Course Schedule", "read", self.cs.name)
            )
            self.assertFalse(guards.is_enrolled(self.cs.name))
            self.assertEqual(guards.student_sections(), [])
            self.assertEqual(
                frappe.get_list("Course Schedule", pluck="name", limit=0), []
            )
            # the teaching staff are untouched by publication
            self._as(self.gta_user)
            self.assertTrue(
                frappe.has_permission("Course Schedule", "read", self.cs.name)
            )
        finally:
            frappe.set_user("Administrator")
            for n, v in was.items():
                frappe.db.set_value("Course Schedule", n, "published", v)

    def test_staff_list_their_unpublished_sections(self):
        """An instructor builds the course before publishing it, so the
        course list shows staff their unpublished sections; a student on the
        roster still sees nothing until it is published."""
        from seminary.seminary.utils import get_courses

        was = frappe.db.get_value("Course Schedule", self.cs.name, "published")
        try:
            frappe.db.set_value("Course Schedule", self.cs.name, "published", 0)
            for user in (self.prof_user, self.gta_user):
                self._as(user)
                listed = [c.name for c in get_courses(page_length=1000)]
                self.assertIn(self.cs.name, listed, user)
            self._as(self.stu_a_user)
            listed = [c.name for c in get_courses(page_length=1000)]
            self.assertNotIn(self.cs.name, listed)
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("Course Schedule", self.cs.name, "published", was)

    # ---------------------------------------------------------------- tiers

    def test_instructor_tiers(self):
        self.assertEqual(guards.instructor_tier(self.prof_user), "record")
        self.assertEqual(guards.instructor_tier(self.gta_user), "section")
        self.assertIsNone(guards.instructor_tier(self.stu_a_user))
        self.assertIsNone(guards.readable_course_schedules(self.prof_user))
        self.assertEqual(
            guards.readable_course_schedules(self.gta_user), [self.cs.name]
        )

    # ------------------------------------------------------------ §2.1/§2.2

    def test_student_lists_only_own_rows(self):
        self._as(self.stu_a_user)
        rows = frappe.get_list("Assignment Submission", pluck="name")
        self.assertIn(self.sub_a, rows)
        self.assertNotIn(self.sub_b, rows)
        rows = frappe.get_list("Scheduled Course Roster", pluck="name")
        self.assertIn(self.roster_a, rows)
        self.assertNotIn(self.roster_b, rows)
        students = frappe.get_list("Student", pluck="name")
        self.assertEqual(students, [self.stu_a])

    def test_student_cannot_read_classmate(self):
        self._as(self.stu_a_user)
        self.assertFalse(frappe.has_permission("Student", "read", self.stu_b))
        self.assertFalse(
            frappe.has_permission("Assignment Submission", "read", self.sub_b)
        )
        self.assertTrue(
            frappe.has_permission("Assignment Submission", "read", self.sub_a)
        )

    def test_student_has_no_write_on_roster_or_section(self):
        self._as(self.stu_a_user)
        self.assertFalse(
            frappe.has_permission("Scheduled Course Roster", "write", self.roster_a)
        )
        self.assertFalse(
            frappe.has_permission("Course Schedule", "write", self.cs.name)
        )
        self.assertFalse(
            frappe.has_permission("Assignment Submission", "delete", self.sub_a)
        )

    # ---------------------------------------------------------------- §2.3

    def test_student_cannot_grade_own_submission_through_save(self):
        self._as(self.stu_a_user)
        doc = frappe.get_doc("Assignment Submission", self.sub_a)
        self.assertTrue(doc.has_permission("write"))
        doc.answer = "edited by the student"
        doc.grade = 100
        doc.status = "Graded"
        doc.save()
        frappe.set_user("Administrator")
        stored = frappe.db.get_value(
            "Assignment Submission",
            self.sub_a,
            ["answer", "grade", "status"],
            as_dict=True,
        )
        self.assertEqual(stored.answer, "edited by the student")
        self.assertNotEqual(stored.grade, 100)
        self.assertNotEqual(stored.status, "Graded")

    def test_student_reads_grade_but_not_letter_body(self):
        # A level-1 read row lets the student see their grade and the grader's
        # comments; Recommendation Letter has no such row, so the body, the
        # attachment and the token stay hidden from the student it is about.
        sub_meta = frappe.get_meta("Assignment Submission")
        self.assertEqual(sub_meta.get_field("grade").permlevel, 1)
        self.assertTrue(
            any(
                p.role == "Student" and p.permlevel == 1 and p.read and not p.write
                for p in sub_meta.permissions
            )
        )
        rl_meta = frappe.get_meta("Recommendation Letter")
        for field in ("letter_body", "letter_attachment", "request_token"):
            self.assertEqual(rl_meta.get_field(field).permlevel, 1, field)
        self.assertFalse(
            any(p.role == "Student" and p.permlevel == 1 for p in rl_meta.permissions)
        )
        self._as(self.stu_a_user)
        self.assertIn(
            1,
            frappe.get_doc("Assignment Submission", self.sub_a).get_permlevel_access(
                "read"
            ),
        )
        self.assertNotIn(
            1, frappe.new_doc("Recommendation Letter").get_permlevel_access("read")
        )

    # ---------------------------------------------------------------- §2.8

    def test_record_tier_reads_everywhere_writes_own_sections(self):
        self._as(self.other_user)  # of record, listed on cs2 only
        self.assertTrue(frappe.has_permission("Course Schedule", "read", self.cs.name))
        self.assertTrue(
            frappe.has_permission("Assignment Submission", "read", self.sub_a)
        )
        self.assertFalse(
            frappe.has_permission("Course Schedule", "write", self.cs.name)
        )
        self.assertFalse(
            frappe.has_permission("Assignment Submission", "write", self.sub_a)
        )
        self.assertTrue(
            frappe.has_permission("Course Schedule", "write", self.cs2.name)
        )

    def test_section_tier_is_confined_to_own_sections(self):
        self._as(self.gta_user)
        self.assertTrue(frappe.has_permission("Course Schedule", "read", self.cs.name))
        self.assertTrue(
            frappe.has_permission("Assignment Submission", "write", self.sub_a)
        )
        self.assertFalse(
            frappe.has_permission("Course Schedule", "write", self.cs2.name)
        )
        rows = frappe.get_list("Assignment Submission", pluck="name")
        self.assertIn(self.sub_a, rows)
        self.assertIn(self.sub_b, rows)
        students = set(frappe.get_list("Student", pluck="name"))
        self.assertTrue({self.stu_a, self.stu_b} <= students)
        self.assertNotIn(self.stu_c, students)
        self.assertFalse(frappe.has_permission("Student", "read", self.stu_c))
        # Course gates agree with the hooks.
        self.assertTrue(guards.is_course_staff(self.cs.name, user=self.gta_user))
        self.assertFalse(guards.is_course_staff(self.cs2.name, user=self.gta_user))
        # A grader is not "super access" any more.
        from seminary.seminary.utils import has_super_access

        self.assertFalse(has_super_access(self.gta_user))
        self.assertTrue(has_super_access(self.prof_user))

    def test_grader_cannot_change_own_default_category(self):
        self._as(self.gta_user)
        doc = frappe.get_doc("Instructor", self.gta)
        doc.default_inst_category = self.record_cat
        doc.shortbio = "p007"
        doc.save()
        frappe.set_user("Administrator")
        stored = frappe.db.get_value(
            "Instructor", self.gta, ["default_inst_category", "shortbio"], as_dict=True
        )
        self.assertEqual(stored.default_inst_category, self.grader_cat)
        self.assertEqual(stored.shortbio, "p007")

    def test_registrar_cannot_promote_a_grader_on_a_section(self):
        reg = _make_user("Registrar", "dp-reg")
        self._as(reg)
        cs = frappe.get_doc("Course Schedule", self.cs2.name)
        cs.append(
            "instructor1",
            {"instructor": self.gta, "instructor_category": self.record_cat},
        )
        with self.assertRaises(frappe.ValidationError):
            cs.save()
        frappe.set_user("Administrator")
        cs = frappe.get_doc("Course Schedule", self.cs2.name)
        cs.append(
            "instructor1",
            {"instructor": self.prof, "instructor_category": self.record_cat},
        )
        self._as(reg)
        cs.save()  # a professor by default: the registrar may list them

    def test_unit_scope_narrows_record_tier(self):
        frappe.db.set_single_value(
            "Seminary Settings", "faculty_read_scope", "Academic Unit"
        )
        try:
            unit = "P007 Unit"
            if not frappe.db.exists("Academic Unit", unit):
                frappe.get_doc(
                    {
                        "doctype": "Academic Unit",
                        "unit_name": unit,
                        "unit_type": "Academic Department",
                    }
                ).insert(ignore_permissions=True)
            unit2 = "P007 Unit 2"
            if not frappe.db.exists("Academic Unit", unit2):
                frappe.get_doc(
                    {
                        "doctype": "Academic Unit",
                        "unit_name": unit2,
                        "unit_type": "Academic Department",
                    }
                ).insert(ignore_permissions=True)
            frappe.db.set_value("Course", self.cs.course, "academic_unit", unit)
            frappe.db.set_value("Course", self.cs2.course, "academic_unit", unit2)
            person = frappe.db.get_value("Instructor", self.other, "person")
            self.assertTrue(person)
            if not frappe.db.exists(
                "Academic Unit Membership", {"person": person, "unit": unit2}
            ):
                frappe.get_doc(
                    {
                        "doctype": "Academic Unit Membership",
                        "unit": unit2,
                        "person": person,
                    }
                ).insert(ignore_permissions=True)
            self._as(self.other_user)
            readable = guards.readable_course_schedules(self.other_user)
            self.assertIsNotNone(readable)
            self.assertIn(self.cs2.name, readable)
            self.assertNotIn(self.cs.name, readable)
            self.assertFalse(
                frappe.has_permission("Course Schedule", "read", self.cs.name)
            )
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_single_value(
                "Seminary Settings", "faculty_read_scope", "School"
            )
            frappe.db.set_value("Course", self.cs.course, "academic_unit", None)
            frappe.db.set_value("Course", self.cs2.course, "academic_unit", None)

    # --------------------------------- p010 Block F / p005a A01-20: the two
    # Academic-Unit fallbacks to School are settings, not fixed rules.

    def _scope(self, **kw):
        frappe.db.set_single_value(
            "Seminary Settings", "faculty_read_scope", "Academic Unit"
        )
        for k, v in kw.items():
            frappe.db.set_single_value("Seminary Settings", k, v)
        frappe.local.p007_cache = {}

    def _scope_reset(self):
        frappe.set_user("Administrator")
        for k, v in (
            ("faculty_read_scope", "School"),
            ("unit_scope_no_membership", "School"),
            ("unit_scope_unassigned_course", "School"),
        ):
            frappe.db.set_single_value("Seminary Settings", k, v)
        frappe.db.set_value("Course", self.cs.course, "academic_unit", None)
        frappe.db.set_value("Course", self.cs2.course, "academic_unit", None)
        frappe.local.p007_cache = {}

    def _unit(self, name):
        if not frappe.db.exists("Academic Unit", name):
            frappe.get_doc(
                {
                    "doctype": "Academic Unit",
                    "unit_name": name,
                    "unit_type": "Academic Department",
                }
            ).insert(ignore_permissions=True)
        return name

    def test_no_membership_reads_as_school_by_default(self):
        """The p007 §2.8 behaviour, now explicit: unchanged unless asked."""
        try:
            self._scope()
            self._as(self.prof_user)
            self.assertIsNone(guards.readable_course_schedules(self.prof_user))
        finally:
            self._scope_reset()

    def test_no_membership_can_be_narrowed_to_own_sections(self):
        try:
            self._scope(unit_scope_no_membership="Own sections only")
            self._as(self.prof_user)
            readable = guards.readable_course_schedules(self.prof_user)
            self.assertIsNotNone(readable, "the switch must stop reading as School")
            self.assertIn(self.cs.name, readable)
            self.assertNotIn(self.cs2.name, readable)
        finally:
            self._scope_reset()

    def test_unassigned_course_reads_as_school_by_default(self):
        unit = self._unit("P010 Unit")
        person = frappe.db.get_value("Instructor", self.other, "person")
        if not frappe.db.exists(
            "Academic Unit Membership", {"person": person, "unit": unit}
        ):
            frappe.get_doc(
                {"doctype": "Academic Unit Membership", "unit": unit, "person": person}
            ).insert(ignore_permissions=True)
        try:
            frappe.db.set_value("Course", self.cs2.course, "academic_unit", unit)
            frappe.db.set_value("Course", self.cs.course, "academic_unit", None)
            self._scope()
            self._as(self.other_user)
            readable = guards.readable_course_schedules(self.other_user)
            self.assertIsNotNone(readable)
            # cs has no unit at all, and still reads as School.
            self.assertIn(self.cs.name, readable)
            self.assertIn(self.cs2.name, readable)
        finally:
            self._scope_reset()

    def test_unassigned_course_can_be_excluded(self):
        unit = self._unit("P010 Unit")
        person = frappe.db.get_value("Instructor", self.other, "person")
        if not frappe.db.exists(
            "Academic Unit Membership", {"person": person, "unit": unit}
        ):
            frappe.get_doc(
                {"doctype": "Academic Unit Membership", "unit": unit, "person": person}
            ).insert(ignore_permissions=True)
        try:
            frappe.db.set_value("Course", self.cs2.course, "academic_unit", unit)
            frappe.db.set_value("Course", self.cs.course, "academic_unit", None)
            self._scope(unit_scope_unassigned_course="Exclude")
            self._as(self.other_user)
            readable = guards.readable_course_schedules(self.other_user)
            self.assertIsNotNone(readable)
            self.assertIn(self.cs2.name, readable)
            self.assertNotIn(
                self.cs.name, readable, "an unassigned course must not leak in"
            )
            self.assertFalse(
                frappe.has_permission("Course Schedule", "read", self.cs.name)
            )
        finally:
            self._scope_reset()

    # --------------------------------- p010 Block F / p005a A10-6: the direct
    # upload ceiling already follows the configured policy; only the wholly
    # unconfigured state reaches the built-in constant.

    def test_direct_limit_follows_configured_policy(self):
        """A10-6 as filed said this fell back to 2 GiB. It does not."""
        from seminary.storage import limits

        was = frappe.db.get_single_value("Seminary Settings", "default_max_upload_mb")
        try:
            frappe.db.set_single_value("Seminary Settings", "default_max_upload_mb", 7)
            limits.clear_cache()
            # A student holds no exception row, so the default governs. (An
            # exception row overrides the default outright -- see the
            # storage.limits module docstring -- so an Instructor here would
            # resolve to their row, not to this 7.)
            self.assertEqual(
                limits.direct_limit_for_user(self.stu_a_user), 7 * limits.MB
            )
            self.assertLess(
                limits.direct_limit_for_user(self.stu_a_user),
                limits.DEFAULT_MAX_DIRECT_BYTES,
            )
        finally:
            frappe.db.set_single_value(
                "Seminary Settings", "default_max_upload_mb", was
            )
            limits.clear_cache()

    # --------------------------------- p010 Block F / p005a A01-19: the ICS
    # token and meeting link belong to the SECTION, not the catalogue course.

    def test_sibling_section_token_is_not_handed_out(self):
        """One enrolment must not unlock every section of the same course.

        `stu_a` is on `cs` only. With `cs2` pointed at the same catalogue
        course, the old course-level gate handed over `cs2`'s calendar token
        and join link -- across terms, not just parallel sections.
        """
        from seminary.seminary.utils import get_course_details

        was_course = frappe.db.get_value("Course Schedule", self.cs2.name, "course")
        was_pub = frappe.db.get_value("Course Schedule", self.cs2.name, "published")
        course = frappe.db.get_value("Course Schedule", self.cs.name, "course")
        try:
            frappe.db.set_value("Course Schedule", self.cs2.name, "course", course)
            frappe.db.set_value("Course Schedule", self.cs2.name, "published", 1)
            for n in (self.cs.name, self.cs2.name):
                if not frappe.db.get_value("Course Schedule", n, "calendar_token"):
                    frappe.db.set_value(
                        "Course Schedule", n, "calendar_token", "t" * 64
                    )
            self._as(self.stu_a_user)

            # Their own section still hands over the token -- no loss.
            own = get_course_details(self.cs.name)
            self.assertTrue(
                own.get("calendar_token"),
                "the enrolled student must still get their own section's token",
            )

            # The sibling section must not.
            other = get_course_details(self.cs2.name)
            self.assertFalse(
                other.get("calendar_token"),
                "a sibling section's calendar token must not be handed out",
            )
            self.assertFalse(other.get("web_meeting"))
            self.assertFalse(
                [m for m in (other.get("meeting_dates") or []) if m.get("web_meeting")]
            )
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("Course Schedule", self.cs2.name, "course", was_course)
            frappe.db.set_value("Course Schedule", self.cs2.name, "published", was_pub)
            frappe.local.p007_cache = {}

    def test_inactive_enrolment_does_not_keep_the_join_link(self):
        """The section gate keeps `active = 1`, so a withdrawal revokes."""
        from seminary.seminary.utils import (
            get_course_details,
            user_is_enrolled_in_section,
        )

        try:
            if not frappe.db.get_value(
                "Course Schedule", self.cs.name, "calendar_token"
            ):
                frappe.db.set_value(
                    "Course Schedule", self.cs.name, "calendar_token", "t" * 64
                )
            self._as(self.stu_a_user)
            self.assertTrue(user_is_enrolled_in_section(self.cs.name))

            frappe.set_user("Administrator")
            frappe.db.set_value("Scheduled Course Roster", self.roster_a, "active", 0)
            self._as(self.stu_a_user)
            self.assertFalse(user_is_enrolled_in_section(self.cs.name))
            self.assertFalse(get_course_details(self.cs.name).get("calendar_token"))
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("Scheduled Course Roster", self.roster_a, "active", 1)
            frappe.local.p007_cache = {}

    def test_upload_default_ships_so_a_fresh_install_is_bounded(self):
        """A10-6's real residual: an install with object storage and no policy.

        `after_install` saves Seminary Settings (seed_portal_messaging_rules),
        and a Single persists its field defaults on save -- so shipping a
        default here is what bounds a brand-new site's direct upload path.
        Without it the only ceiling is DEFAULT_MAX_DIRECT_BYTES."""
        from seminary.storage import limits

        field = frappe.get_meta("Seminary Settings").get_field("default_max_upload_mb")
        self.assertTrue(
            field.default and int(field.default) > 0,
            "default_max_upload_mb must ship a default, or a fresh install's "
            "direct uploads answer only to the built-in ceiling",
        )
        self.assertLess(int(field.default) * limits.MB, limits.DEFAULT_MAX_DIRECT_BYTES)

    def test_direct_limit_reaches_the_constant_only_when_unconfigured(self):
        from seminary.storage import limits

        was = frappe.db.get_single_value("Seminary Settings", "default_max_upload_mb")
        rows = frappe.get_all(
            "Upload Limit",
            filters={"parenttype": "Seminary Settings"},
            fields=["name", "role", "max_file_size_mb"],
        )
        try:
            frappe.db.set_single_value("Seminary Settings", "default_max_upload_mb", 0)
            for r in rows:
                frappe.db.set_value("Upload Limit", r.name, "max_file_size_mb", 0)
            limits.clear_cache()
            self.assertEqual(
                limits.direct_limit_for_user(self.prof_user),
                limits.DEFAULT_MAX_DIRECT_BYTES,
            )
        finally:
            frappe.db.set_single_value(
                "Seminary Settings", "default_max_upload_mb", was
            )
            for r in rows:
                frappe.db.set_value(
                    "Upload Limit", r.name, "max_file_size_mb", r.max_file_size_mb
                )
            limits.clear_cache()

    def test_settings_warns_when_unit_scope_restricts_nothing(self):
        """The control must not look enabled while reaching everything."""
        doc = frappe.get_single("Seminary Settings")
        doc.faculty_read_scope = "Academic Unit"
        doc.unit_scope_no_membership = "School"
        doc.unit_scope_unassigned_course = "School"
        frappe.clear_messages()
        doc._warn_if_unit_scope_restricts_nothing()
        messages = " ".join(str(m) for m in frappe.get_message_log())
        self.assertIn("school-wide", messages)

        # Tightened on both axes: nothing to warn about.
        doc.unit_scope_no_membership = "Own sections only"
        doc.unit_scope_unassigned_course = "Exclude"
        frappe.clear_messages()
        doc._warn_if_unit_scope_restricts_nothing()
        self.assertEqual(frappe.get_message_log(), [])
