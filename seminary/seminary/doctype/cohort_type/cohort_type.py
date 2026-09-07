# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Cohort Type: the policy record for a family of cohorts (ADR 066 section 2).

Everything a school wants to say about a *kind* of cohort is said once here and
enforced on each `Cohort Membership` as it is written. Policy on the type rather
than the cohort, because a rule that can be edited per cohort is not a rule.

Three axes, deliberately separate -- lifecycle (`category` and what it binds to),
leadership (`leader_eligibility`) and bulk planning (`plannable`). They vary
independently in the schools we have seen, and one rich `category` cannot express
a program-long cohort led by an alumnus.

`plannable` replaced the `automation_rule` Select (ADR 067 section 2). The Select
carried two axes at once -- a trigger (`On Program Enrollment`, withdrawn: at the
moment one enrollment is created nobody can know whether the cohort will hold)
and a set of deferred cuts that were never triggers at all. What used to be
implied by it now lives where a rule lives: the pool on `mentor_unit`, the
matching in the criteria table, the sizes in the two size fields.
"""

import frappe
from frappe import _
from frappe.model.document import Document

PACED = "Paced Program"
THROUGHOUT = "Throughout Program"
COURSE_SCOPED = "Course scoped"
UNRESTRICTED = "Unrestricted"

PROGRAM_CATEGORIES = (PACED, THROUGHOUT)

MENTORING_DEPARTMENT = "Mentoring Department"
COHORT_MENTORSHIP_ROUTE = "Program Cohort Mentorship"

# The one leadership rule that reads the binding rather than the person alone.
# `Any alumnus` is the same rule with nothing to read, kept as a separate option
# so an unbound type says which of the two it means instead of leaving the
# membership check to decide.
BOUND_ALUMNUS = "Alumnus of the bound program or level"
ANY_ALUMNUS = "Any alumnus"
ALUMNUS_RULES = (BOUND_ALUMNUS, ANY_ALUMNUS)


class CohortType(Document):
    def validate(self):
        self.clear_fields_the_category_does_not_use()
        self.validate_binding()
        self.validate_leaders_have_something_to_be_alumni_of()
        self.validate_alumni_self_service()
        self.validate_graduation_target()
        self.validate_one_paced_type_per_program()
        self.validate_planning_settings()

    def clear_fields_the_category_does_not_use(self):
        """A hidden field that still holds a value is a rule nobody can see.

        `depends_on` only hides; it does not clear. Two kinds of field are
        hidden by a category, and they want different treatment:

        Fields that make the system *act* -- the planning flag and the
        withdrawal sweep -- are cleared on every save. A stale one is a job
        firing on a type whose form does not admit to having it.

        Bindings and destinations are inert without a lifecycle to run them, so
        they are cleared only when the category actually moves away from them.
        That is what lets a type parked at `Unrestricted` (the state the ADR 066
        patch left every existing type in) be reclassified later and find its
        `graduates_to` still there, rather than punishing the chair for having
        opened the record in between.

        The exception is a binding the *leadership* rule reads. The category is
        not the only reason to hold one, so clearing on a category change would
        take away the answer and then refuse the save for not having it -- the
        chair would be told to name a program they had just named.
        """
        if self.category not in PROGRAM_CATEGORIES:
            self.plannable = 0
            self.remove_on_withdrawal = 0
        if self.category == COURSE_SCOPED:
            # A course-scoped type forms one cohort per course and a student
            # takes many courses, often at once. "One cohort per member" is not
            # a policy a school could hold here; it is a contradiction of the
            # category, and holding it would refuse the second course's seeding.
            self.max_lineages_per_member = 0
        if not self.plannable:
            self.mentor_unit = None
            self.automation_min_size = 0
            self.automation_max_size = 0

        before = self.get_doc_before_save()
        if before and before.category == self.category:
            return
        if self.category not in PROGRAM_CATEGORIES:
            self.graduates_to = None
        if self.category != THROUGHOUT and not self.leaders_read_the_binding():
            # Only a program-long cohort can span a whole level; everything else
            # is bound to one program or to none.
            self.program_level = None
        if self.category == UNRESTRICTED and not self.leaders_read_the_binding():
            self.program = None

    def leaders_read_the_binding(self):
        """Does the leadership rule need a program or a level to check against?"""
        return self.leader_eligibility == BOUND_ALUMNUS

    def validate_binding(self):
        """What the cohort is bound to, per category."""
        if self.program and self.program_level:
            frappe.throw(
                _(
                    "A cohort type binds to a Program or to a Program Level, not "
                    "to both -- two bindings is two answers to the question of "
                    "who belongs here. Clear one."
                )
            )

        if self.category == PACED:
            # A paced cohort moves its members together, which is only definable
            # over one program: two programs at the same level advance on their
            # own schedules, so "the whole cohort moves up" has no meaning there.
            if not self.program:
                frappe.throw(
                    _(
                        "A {0} cohort advances its members together, so it must "
                        "name the Program they advance through. Program Level is "
                        "not enough -- programs at one level keep their own "
                        "schedules."
                    ).format(frappe.bold(PACED))
                )
            program_type = frappe.db.get_value("Program", self.program, "program_type")
            if program_type and program_type != "Time-based":
                frappe.throw(
                    _(
                        "{0} is a {1} program, so there is no term boundary for a "
                        "{2} cohort to advance on. Use {3} instead."
                    ).format(
                        frappe.bold(self.program),
                        program_type,
                        frappe.bold(PACED),
                        frappe.bold(THROUGHOUT),
                    )
                )

        if self.category == THROUGHOUT and not (self.program or self.program_level):
            frappe.throw(
                _(
                    "A {0} cohort runs from enrollment to graduation, so it must "
                    "name the Program or the Program Level it runs alongside."
                ).format(frappe.bold(THROUGHOUT))
            )

    def validate_leaders_have_something_to_be_alumni_of(self):
        """`Alumnus of the bound program or level` needs a binding to read.

        Without one the rule has no question to ask, and the membership check
        would have to invent an answer: either refuse every candidate, or accept
        an alumnus of anywhere. It used to do the second silently, which granted
        leadership on a scope the school never named. `Any alumnus` is now that
        second answer, said out loud, so this refuses rather than guesses.
        """
        if not self.leaders_read_the_binding():
            return
        if self.program or self.program_level:
            return
        frappe.throw(
            _(
                "Leaders of this type must be alumni of the program or level it "
                "is bound to, and it is bound to neither. Name a {0} or a {1} "
                "above, or set Leader Eligibility to {2} if any graduate of this "
                "school may lead."
            ).format(_("Program"), _("Program Level"), frappe.bold(ANY_ALUMNUS))
        )

    def validate_alumni_self_service(self):
        """Cohorts a school does not set up, and the one limit it still sets.

        Asking alumni to lead is asking people who have left to come back to a
        platform they have no other reason to open, and requiring a staff member
        in the desk for each group is most of the friction. Letting the alumnus
        create their own removes it -- but it also removes the moment a person
        looked at the group, so the type has to say in advance how large one may
        get. Hence a limit that refuses rather than warns: there is nobody on the
        other side of the warning.

        Both settings only mean anything on an alumnus-led type, so they are
        cleared elsewhere rather than left as a rule nobody can see.
        """
        if self.leader_eligibility not in ALUMNUS_RULES:
            self.alumni_may_create = 0
            self.portal_size_limit = 0
            return

        # 0 means "no limit" on either field, so only two real numbers can
        # disagree -- and advising a size the portal then refuses is two answers
        # to how big a cohort of this type may be.
        if (
            self.portal_size_limit
            and self.default_max_size
            and self.default_max_size > self.portal_size_limit
        ):
            frappe.throw(
                _(
                    "Default Max Size ({0}) is above the Portal Size Limit ({1}), "
                    "so a cohort would be advised to grow to a size the portal "
                    "refuses to let it reach. Lower the suggestion, or raise the "
                    "limit."
                ).format(self.default_max_size, self.portal_size_limit)
            )

    def validate_graduation_target(self):
        """Graduating into a type is itself how that type gets filled.

        A type that both receives graduates and forms its own cohorts would
        place students into a stage they have not reached -- the planner would
        fill it from the enrolled pool while graduation was still years away
        (ADR 066 section 7.15). Checked from both sides, because either edit can
        create the conflict.
        """
        if self.graduates_to == self.name:
            frappe.throw(_("A Cohort Type cannot graduate into itself."))

        if self.graduates_to:
            target_plannable = frappe.db.get_value(
                "Cohort Type", self.graduates_to, "plannable"
            )
            if target_plannable:
                frappe.throw(
                    _(
                        "{0} forms its own cohorts in the planner, so it cannot "
                        "also receive graduates -- students would be placed "
                        "there before they graduate. Untick its bulk planning "
                        "box, or graduate into a hand-authored type."
                    ).format(frappe.bold(self.graduates_to))
                )

        if self.plannable:
            feeder = frappe.db.get_value(
                "Cohort Type",
                {"graduates_to": self.name, "name": ("!=", self.name)},
                "name",
            )
            if feeder:
                frappe.throw(
                    _(
                        "{0} already graduates into this type, which is how its "
                        "cohorts get their members. Planning it in bulk as well "
                        "would place students before they graduate."
                    ).format(frappe.bold(feeder))
                )

    def validate_planning_settings(self):
        """The planner needs a pool and a coherent pair of sizes.

        `mentor_unit` carries a `link_filters` hint on the form, which is a
        convenience and not a rule -- it constrains the picker and nothing else,
        so the type is re-checked here where a REST insert or an import also
        passes through (ADR 067 section 4).
        """
        if not self.plannable:
            return

        if not self.mentor_unit:
            frappe.throw(
                _(
                    "A type that may be planned in bulk needs a Mentor Unit -- "
                    "that is where the planner finds mentors and reads how many "
                    "students each of them can carry."
                )
            )

        unit_type, is_active = frappe.db.get_value(
            "Academic Unit", self.mentor_unit, ["unit_type", "is_active"]
        )
        if unit_type != MENTORING_DEPARTMENT:
            frappe.throw(
                _("{0} is {1}, so it cannot be a Mentor Unit. Choose a {2}.").format(
                    frappe.bold(self.mentor_unit),
                    unit_type or _("of no type"),
                    frappe.bold(MENTORING_DEPARTMENT),
                )
            )
        if not is_active:
            frappe.throw(
                _(
                    "{0} is not active, so the planner would find no mentors in it."
                ).format(frappe.bold(self.mentor_unit))
            )

        self.validate_criteria_have_their_data()

        # 0 means "no bound" on either field, so only two real numbers can
        # contradict each other. A minimum above the maximum is a type that can
        # never propose a group the planner is willing to show without a flag.
        if (
            self.automation_min_size
            and self.automation_max_size
            and self.automation_min_size > self.automation_max_size
        ):
            frappe.throw(
                _(
                    "The minimum cohort size ({0}) is larger than the maximum "
                    "({1}), so no proposed cohort could ever be the right size."
                ).format(self.automation_min_size, self.automation_max_size)
            )

    def validate_one_paced_type_per_program(self):
        """Two paced types over one program would advance a student two ways.

        Other types may coexist freely -- an academic grouping and a formation
        grouping serve different purposes and a school may want both. What may
        not coexist is two answers to "where does this student go next term"
        (ADR 066 section 7.9). Scoped to active types, so retiring one and
        defining its replacement is an ordinary two-step edit.
        """
        if self.category != PACED or not self.is_active:
            return
        clash = frappe.db.get_value(
            "Cohort Type",
            {
                "category": PACED,
                "program": self.program,
                "is_active": 1,
                "name": ("!=", self.name or ""),
            },
            "name",
        )
        if clash:
            frappe.throw(
                _(
                    "{0} is already the {1} type for {2}, and two of them would "
                    "advance the same student in two directions. Deactivate it "
                    "first, or use another category."
                ).format(frappe.bold(clash), PACED, frappe.bold(self.program))
            )

    def validate_criteria_have_their_data(self):
        """A rule may only be chosen when its datum is guaranteed (ADR 067 §9).

        Checked here and not only in the picker, because a picker filter is a
        convenience and this is a rule: a REST insert, an import or a fixture
        never sees one. A criterion whose detail the school has not made
        required would match nobody and say nothing about why -- the failure
        would look like a data problem in every individual student rather than
        a configuration one, which is exactly the shape of bug this refuses.
        """
        if not self.criteria:
            return
        for row in self.criteria:
            entry = frappe.db.get_value(
                "Cohort Assignment Criterion",
                row.criterion,
                ["criterion_name", "requires_field", "is_active"],
                as_dict=True,
            )
            if not entry:
                continue
            if not entry.is_active:
                frappe.msgprint(
                    _(
                        "{0} has been retired, so it will be skipped when this "
                        "type is planned."
                    ).format(frappe.bold(entry.criterion_name)),
                    indicator="orange",
                )
                continue
            if not entry.requires_field:
                continue
            required = frappe.db.get_value(
                "Mandatory Personal Field",
                entry.requires_field,
                ["mandatory", "field_label"],
                as_dict=True,
            )
            if required and required.mandatory:
                continue
            frappe.throw(
                _(
                    "{0} matches on {1}, so {1} has to be a detail your school "
                    "requires — otherwise the rule would quietly match nobody. "
                    "Tick Required on it under Mandatory Personal Field, or "
                    "remove this rule."
                ).format(
                    frappe.bold(entry.criterion_name),
                    frappe.bold(
                        (required and required.field_label) or entry.requires_field
                    ),
                )
            )
