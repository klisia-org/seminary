# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from seminary.seminary.utils import assert_url_safe_code


class GradingScale(Document):
    def validate(self):
        self.protect_dimension_codes()
        thresholds = []
        for d in self.intervals:
            threshold = flt(d.threshold)
            if threshold in thresholds:
                frappe.throw(
                    _("Threshold {0} appears more than once").format(threshold)
                )
            thresholds.append(threshold)
        if self.grscale_type == "Points" and 0 not in thresholds:
            frappe.throw(_("Please define a grade for Threshold 0"))
        self.validate_cbe_scale()

    def protect_dimension_codes(self):
        """Refuse to drop or rename a dimension code that records still carry.

        `dimension_code` is a stable key, not a label: every competency
        descriptor, assessment weight and grade in this scale's orbit stores the
        string rather than a reference to the row (ADR 065 section 1). Frappe
        will not cascade an edit to it, so a rename here silently detaches those
        records -- the verdict pipeline looks up the new code, finds no grades
        under it, and reports a competency as ungraded rather than failing.

        The label is free to change: only `dimension_code` is guarded. To retire
        a dimension that is in use, add the replacement alongside it, move the
        records over, then remove the old row.
        """
        before = self.get_doc_before_save()
        if not before:
            return

        lost = {d.dimension_code for d in (before.gradingscaledimensions or [])} - {
            d.dimension_code for d in (self.gradingscaledimensions or [])
        }
        lost.discard(None)
        if not lost:
            return

        for code in sorted(lost):
            usage = dimension_code_usage(self.name, code)
            if usage:
                frappe.throw(
                    _(
                        "Dimension code {0} is still used by {1}. Renaming or "
                        "removing it would detach those records, because every one "
                        "of them stores the code rather than a link to this row. "
                        "Add the replacement dimension alongside it, move the "
                        "records over, then remove this one."
                    ).format(
                        frappe.bold(code),
                        ", ".join(
                            _("{0} {1}").format(count, label) for label, count in usage
                        ),
                    ),
                    title=_("Dimension code in use"),
                )

    def validate_cbe_scale(self):
        """Validate the extra structure a competency-based scale must carry.

        A CBE scale supplies two vocabularies to everything downstream: the
        proficiency levels (the intervals, whose threshold is the level value)
        and the dimensions. Both must be complete and stable before any
        competency record can reference them. Child-row rules live here on the
        parent per ADR 023.
        """
        if self.grscale_type != "Competency-based education":
            return

        if not self.gradingscaledimensions:
            frappe.throw(
                _("A Competency-based education scale needs at least one dimension.")
            )

        seen_codes = {}
        for d in self.gradingscaledimensions:
            if not d.dimension_code:
                frappe.throw(_("Row {0}: Dimension Code is required.").format(d.idx))
            assert_url_safe_code(
                d.dimension_code, _("Row {0}: Dimension Code").format(d.idx)
            )
            if d.dimension_code in seen_codes:
                frappe.throw(
                    _("Dimension Code {0} appears in rows {1} and {2}.").format(
                        d.dimension_code, seen_codes[d.dimension_code], d.idx
                    )
                )
            seen_codes[d.dimension_code] = d.idx

        if not self.intervals:
            frappe.throw(
                _(
                    "A Competency-based education scale needs at least one interval "
                    "to define its proficiency levels."
                )
            )

        for d in self.intervals:
            if d.threshold is None or d.threshold == "":
                frappe.throw(
                    _(
                        "Row {0}: Threshold is required on every interval of a "
                        "Competency-based education scale. It holds the level value "
                        "(for example 1, 2, 3, 4)."
                    ).format(d.idx)
                )


# The bridge from a scale to everything that stores one of its dimension codes.
# Each of these carries `course_competency`, so one set of competencies scopes
# them all; Course Competency Dimension is the exception, being the competency's
# own child rows.
DIMENSION_USERS = (
    ("Assessment Dimension Weight", "course_competency"),
    ("Assessment Grading Matrix", "course_competency"),
    ("Activity Competency Grade", "course_competency"),
    ("Personal Development Plan Goal", "course_competency"),
)


def dimension_code_usage(grading_scale, dimension_code):
    """Records under this scale that store `dimension_code`, as (label, count).

    Scoped to the scale rather than counted globally: two scales may legitimately
    both define `knowledge`, and a school editing one of them must not be blocked
    by records belonging to the other.
    """
    courses = [
        c.name
        for c in frappe.get_all(
            "Course", filters={"default_grading_scale": grading_scale}, fields=["name"]
        )
    ]
    if not courses:
        return []

    competencies = [
        c.name
        for c in frappe.get_all(
            "Course Competency", filters={"course": ["in", courses]}, fields=["name"]
        )
    ]
    if not competencies:
        return []

    usage = []

    descriptors = frappe.db.count(
        "Course Competency Dimension",
        {
            "parenttype": "Course Competency",
            "parent": ["in", competencies],
            "dimension_code": dimension_code,
        },
    )
    if descriptors:
        usage.append((_("competency descriptors"), descriptors))

    for doctype, field in DIMENSION_USERS:
        count = frappe.db.count(
            doctype, {field: ["in", competencies], "dimension_code": dimension_code}
        )
        if count:
            usage.append((_(doctype), count))

    # Ratings and result rows hang off a parent that carries the competency, so
    # they need the extra hop their siblings above do not.
    for parent_doctype, child_doctype, label in (
        (
            "Competency Assessment",
            "Competency Assessment Rating",
            _("assessment ratings"),
        ),
        ("Competency Result", "Competency Result Dimension", _("result rows")),
    ):
        parents = [
            p.name
            for p in frappe.get_all(
                parent_doctype,
                filters={"course_competency": ["in", competencies]},
                fields=["name"],
            )
        ]
        if not parents:
            continue
        count = frappe.db.count(
            child_doctype,
            {
                "parenttype": parent_doctype,
                "parent": ["in", parents],
                "dimension_code": dimension_code,
            },
        )
        if count:
            usage.append((label, count))

    return usage
