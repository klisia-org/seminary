from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class GradeConversionPolicy(Document):
    def validate(self):
        self._validate_scales_submitted()
        self._validate_method_vs_scale()
        self._validate_conversion_map()

    def _validate_scales_submitted(self):
        for field in ("source_grading_scale", "target_grading_scale"):
            scale = self.get(field)
            if not scale:
                continue
            docstatus = frappe.db.get_value("Grading Scale", scale, "docstatus")
            if docstatus != 1:
                frappe.throw(
                    _(
                        "{0} must reference a Submitted Grading Scale. '{1}' is not submitted."
                    ).format(self.meta.get_label(field), scale)
                )

    def _validate_method_vs_scale(self):
        """Narrative (Descriptive) sources cannot use linear methods — see ADR 006."""
        if self.conversion_method not in ("linear_multiplier", "linear_with_offset"):
            return
        if not self.source_grading_scale:
            return
        source_type = frappe.db.get_value(
            "Grading Scale", self.source_grading_scale, "grscale_type"
        )
        if source_type == "Descriptive":
            frappe.throw(
                _(
                    "Linear conversion methods are not valid for Descriptive (narrative) source scales. "
                    "Use 'interval_map' or 'manual_per_course' instead."
                )
            )

    def _validate_conversion_map(self):
        if self.conversion_method != "interval_map":
            return
        if not self.conversion_map:
            return

        source_symbols = [row.source_symbol for row in self.conversion_map]
        duplicates = {s for s in source_symbols if source_symbols.count(s) > 1}
        if duplicates:
            frappe.throw(
                _("Duplicate source symbol(s) in conversion map: {0}").format(
                    ", ".join(sorted(duplicates))
                )
            )

        source_codes = self._scale_grade_codes(self.source_grading_scale)
        target_codes = self._scale_grade_codes(self.target_grading_scale)

        for row in self.conversion_map:
            if source_codes and row.source_symbol not in source_codes:
                frappe.throw(
                    _(
                        "Source symbol '{0}' on row {1} is not a grade code of source scale '{2}'."
                    ).format(row.source_symbol, row.idx, self.source_grading_scale)
                )
            if target_codes and row.target_symbol not in target_codes:
                frappe.throw(
                    _(
                        "Target symbol '{0}' on row {1} is not a grade code of target scale '{2}'."
                    ).format(row.target_symbol, row.idx, self.target_grading_scale)
                )

        # One-way coverage: every source-scale grade code must be mapped.
        # Target grades without a source mapping are allowed.
        if source_codes:
            mapped = set(source_symbols)
            unmapped = source_codes - mapped
            if unmapped:
                frappe.throw(
                    _(
                        "Every source-scale grade code must be mapped. Missing mapping(s) for: {0}."
                    ).format(", ".join(sorted(unmapped)))
                )

    @staticmethod
    def _scale_grade_codes(scale_name):
        if not scale_name:
            return set()
        return {
            row.grade_code
            for row in frappe.get_all(
                "Grading Scale Interval",
                filters={"parent": scale_name},
                fields=["grade_code"],
            )
        }


def convert_grade(policy_name, source_grade):
    """Apply a submitted Grade Conversion Policy to a source grade.
    Returns: {grade_code, grade_threshold, warning}
    - grade_code: target-scale symbol resolved for the input
    - grade_threshold: target-scale threshold (serving grade-point role) for that symbol
    - warning: None / 'clamped_high' / 'clamped_low' / 'no_mapping' / 'unparseable_source'
    """
    policy = frappe.get_cached_doc("Grade Conversion Policy", policy_name)
    method = policy.conversion_method

    if method == "identity":
        return _resolve_target_symbol(policy.target_grading_scale, source_grade)

    if method == "manual_per_course":
        return _resolve_target_symbol(policy.target_grading_scale, source_grade)

    if method == "interval_map":
        mapping = _find_map_row(policy.conversion_map, source_grade)
        if mapping is None:
            return {
                "grade_code": None,
                "grade_threshold": None,
                "warning": "no_mapping",
            }
        return _resolve_target_symbol(policy.target_grading_scale, mapping)

    if method in ("linear_multiplier", "linear_with_offset"):
        try:
            source_value = flt(source_grade)
        except (ValueError, TypeError):
            return {
                "grade_code": None,
                "grade_threshold": None,
                "warning": "unparseable_source",
            }
        raw = source_value * flt(policy.multiplier)
        if method == "linear_with_offset":
            raw += flt(policy.offset)
        rounded = float(
            Decimal(repr(raw)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
        return _resolve_by_threshold(policy.target_grading_scale, rounded)

    frappe.throw(_("Unknown conversion_method '{0}'.").format(method))


def _find_map_row(conversion_map_rows, source_symbol):
    for row in conversion_map_rows or []:
        if row.source_symbol == source_symbol:
            return row.target_symbol
    return None


def _resolve_target_symbol(target_scale_name, target_symbol):
    """Look up a target-scale interval by grade_code (symbol)."""
    interval = frappe.db.get_value(
        "Grading Scale Interval",
        {"parent": target_scale_name, "grade_code": target_symbol},
        ["grade_code", "threshold"],
        as_dict=True,
    )
    if not interval:
        return {
            "grade_code": None,
            "grade_threshold": None,
            "warning": "no_mapping",
        }
    return {
        "grade_code": interval.grade_code,
        "grade_threshold": flt(interval.threshold),
        "warning": None,
    }


def _resolve_by_threshold(target_scale_name, value):
    """Find the target-scale interval whose threshold is the largest <= value.
    Clamps high/low and raises a warning if the value is outside the scale."""
    intervals = frappe.get_all(
        "Grading Scale Interval",
        filters={"parent": target_scale_name},
        fields=["grade_code", "threshold"],
        order_by="threshold desc",
    )
    if not intervals:
        return {"grade_code": None, "grade_threshold": None, "warning": "no_mapping"}

    max_threshold = flt(intervals[0].threshold)
    min_threshold = flt(intervals[-1].threshold)

    if value > max_threshold:
        return {
            "grade_code": intervals[0].grade_code,
            "grade_threshold": max_threshold,
            "warning": "clamped_high",
        }
    if value < min_threshold:
        return {
            "grade_code": intervals[-1].grade_code,
            "grade_threshold": min_threshold,
            "warning": "clamped_low",
        }
    for interval in intervals:
        if value >= flt(interval.threshold):
            return {
                "grade_code": interval.grade_code,
                "grade_threshold": flt(interval.threshold),
                "warning": None,
            }
    return {"grade_code": None, "grade_threshold": None, "warning": "no_mapping"}
