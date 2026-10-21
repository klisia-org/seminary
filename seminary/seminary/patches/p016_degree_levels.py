"""Split Masters and Doctorate into the degree levels, give every level a tier, and bind cohort
types to a tier instead of a level (p016)."""

import frappe

from seminary.seminary.doctype.program_level.program_level import (
    SEEDED,
    seed_program_levels,
)

# Old level -> (abbreviation start -> new level), with the fallback for anything else.
SPLIT = {
    "Masters": (
        [
            ("mdiv", "Master of Divinity"),
            ("thm", "Master of Theology"),
            ("stm", "Master of Theology"),
        ],
        "Master of Arts",
    ),
    "Doctorate": (
        [
            ("dmin", "Doctor of Ministry"),
            ("phd", "PhD/Research Doctorate"),
            ("thd", "PhD/Research Doctorate"),
        ],
        "Other Professional Doctorate",
    ),
}
# Fields that are not policy: never copied from the old level.
NOT_POLICY = {"pgm_level", "degree_tier", "description", "amended_from", "amended"}


def execute():
    frappe.flags.in_patch = True
    old_levels = {
        name: frappe.get_doc("Program Level", name)
        for name in SPLIT
        if frappe.db.exists("Program Level", name)
    }
    new_names = [n for n in SEEDED if not frappe.db.exists("Program Level", n)]
    seed_program_levels()
    for old, (_rules, fallback) in SPLIT.items():
        if old in old_levels:
            for new in {fallback, *(level for _p, level in _rules)}:
                if new in new_names:
                    _copy_policies(old_levels[old], new)

    _tier_custom_levels()
    for old in old_levels:
        _move_programs(old)
    _bind_cohort_types_to_tiers()
    for old in old_levels:
        _retire(old)


def _copy_policies(source, target):
    meta = frappe.get_meta("Program Level")
    values = {
        f.fieldname: source.get(f.fieldname)
        for f in meta.fields
        if f.fieldname not in NOT_POLICY
        and f.fieldtype not in frappe.model.no_value_fields
    }
    if values:
        frappe.db.set_value("Program Level", target, values, update_modified=False)


def _tier_custom_levels():
    for row in frappe.get_all(
        "Program Level",
        filters={"name": ("not in", list(SEEDED) + list(SPLIT))},
        fields=["name", "degree_tier"],
    ):
        if not row.degree_tier:
            frappe.db.set_value(
                "Program Level",
                row.name,
                "degree_tier",
                _guess_tier(row.name),
                update_modified=False,
            )
    for old, tier in (("Masters", "Master's"), ("Doctorate", "Doctoral")):
        if frappe.db.exists("Program Level", old):
            frappe.db.set_value(
                "Program Level", old, "degree_tier", tier, update_modified=False
            )


def _guess_tier(name):
    n = name.lower()
    if "master" in n:
        return "Master's"
    if "doct" in n or "phd" in n:
        return "Doctoral"
    if "bach" in n:
        return "Bachelor's"
    if "cert" in n or "diploma" in n:
        return "Certificate"
    if "formal" in n:
        return "Non-formal"
    return "Other"


def _abbreviation_start(abbreviation):
    """The degree part of an abbreviation: "DEMO-MDiv" -> "mdiv"."""
    return (abbreviation or "").strip().split("-")[-1].split(" ")[-1].lower()


def _move_programs(old):
    rules, fallback = SPLIT[old]
    for p in frappe.get_all(
        "Program",
        filters={"program_level": old},
        fields=["name", "program_abbreviation"],
    ):
        start = _abbreviation_start(p.program_abbreviation)
        level = next(
            (lvl for prefix, lvl in rules if start.startswith(prefix)), fallback
        )
        frappe.db.set_value(
            "Program", p.name, "program_level", level, update_modified=False
        )
        print(f"Program {p.name}: {old} -> {level}")


def _bind_cohort_types_to_tiers():
    if not frappe.db.has_column("Cohort Type", "program_level"):
        return
    tiers = dict(
        frappe.get_all("Program Level", fields=["name", "degree_tier"], as_list=True)
    )
    for name, level in frappe.db.sql(
        "select name, program_level from `tabCohort Type` where ifnull(program_level, '') != ''"
    ):
        frappe.db.set_value(
            "Cohort Type",
            name,
            "program_tier",
            tiers.get(level) or "Other",
            update_modified=False,
        )
        frappe.db.sql(
            "update `tabCohort Type` set program_level = null where name = %s", name
        )


def _retire(old):
    if frappe.db.exists("Program", {"program_level": old}):
        print(f"Program Level {old} kept: programs still use it.")
        return
    frappe.db.set_value("Program Level", old, "docstatus", 2, update_modified=False)
    try:
        frappe.delete_doc("Program Level", old, ignore_permissions=True)
    except frappe.LinkExistsError:
        frappe.db.set_value("Program Level", old, "docstatus", 1, update_modified=False)
        print(f"Program Level {old} kept: other records link to it.")
