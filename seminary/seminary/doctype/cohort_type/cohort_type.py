# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Cohort Type: the policy record for a family of cohorts (ADR 066 section 2).

Everything a school wants to say about a *kind* of cohort is said once here and
enforced on each `Cohort Membership` as it is written. Policy on the type rather
than the cohort, because a rule that can be edited per cohort is not a rule.

Three axes, deliberately separate -- lifecycle (`category` and what it binds to),
leadership (`leader_eligibility`) and automation (`automation_rule`). They vary
independently in the schools we have seen, and one rich `category` cannot express
a program-long cohort led by an alumnus.
"""

import frappe
from frappe import _
from frappe.model.document import Document

PACED = "Paced Program"
THROUGHOUT = "Throughout Program"
COURSE_SCOPED = "Course scoped"
UNRESTRICTED = "Unrestricted"

PROGRAM_CATEGORIES = (PACED, THROUGHOUT)


class CohortType(Document):
    def validate(self):
        self.clear_fields_the_category_does_not_use()
        self.validate_binding()
        self.validate_graduation_target()
        self.validate_one_paced_type_per_program()

    def clear_fields_the_category_does_not_use(self):
        """A hidden field that still holds a value is a rule nobody can see.

        `depends_on` only hides; it does not clear. Two kinds of field are
        hidden by a category, and they want different treatment:

        Fields that make the system *act* -- the automation rule and the
        withdrawal sweep -- are cleared on every save. A stale one is a job
        firing on a type whose form does not admit to having it.

        Bindings and destinations are inert without a lifecycle to run them, so
        they are cleared only when the category actually moves away from them.
        That is what lets a type parked at `Unrestricted` (the state the ADR 066
        patch left every existing type in) be reclassified later and find its
        `graduates_to` still there, rather than punishing the chair for having
        opened the record in between.
        """
        if self.category not in PROGRAM_CATEGORIES:
            self.automation_rule = None
            self.remove_on_withdrawal = 0
        if not self.automation_rule:
            self.automation_max_size = 0

        before = self.get_doc_before_save()
        if before and before.category == self.category:
            return
        if self.category not in PROGRAM_CATEGORIES:
            self.graduates_to = None
        if self.category != THROUGHOUT:
            # Only a program-long cohort can span a whole level; everything else
            # is bound to one program or to none.
            self.program_level = None
        if self.category == UNRESTRICTED:
            self.program = None

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

    def validate_graduation_target(self):
        """Graduating into a type is itself the automation for that type.

        A type that both receives graduates and carries its own rule would place
        students into a stage they have not reached -- the rule would fill it on
        enrollment while graduation was still years away (ADR 066 section 7.15).
        Checked from both sides, because either edit can create the conflict.
        """
        if self.graduates_to == self.name:
            frappe.throw(_("A Cohort Type cannot graduate into itself."))

        if self.graduates_to:
            target_rule = frappe.db.get_value(
                "Cohort Type", self.graduates_to, "automation_rule"
            )
            if target_rule:
                frappe.throw(
                    _(
                        "{0} forms its own cohorts ({1}), so it cannot also "
                        "receive graduates -- students would be placed there "
                        "before they graduate. Clear its automation rule, or "
                        "graduate into a hand-authored type."
                    ).format(frappe.bold(self.graduates_to), target_rule)
                )

        if self.automation_rule:
            feeder = frappe.db.get_value(
                "Cohort Type",
                {"graduates_to": self.name, "name": ("!=", self.name)},
                "name",
            )
            if feeder:
                frappe.throw(
                    _(
                        "{0} already graduates into this type, which is how its "
                        "cohorts get their members. Adding an automation rule "
                        "here would place students before they graduate."
                    ).format(frappe.bold(feeder))
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
