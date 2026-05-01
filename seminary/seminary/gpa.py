"""GPA calculation for Program Enrollment.

Aggregates PEC rows where count_in_gpa = 1 and pec_finalgradenum is set.
For each row, the raw numeric is converted to grade points on the Program's
basis_for_gpa scale, then the per-row points are credit-weighted (or simple-meaned)
into Program Enrollment.current_gpa. The matching honors level is written to
current_honor.

Hooked from:
- seminary.api.send_grades (after grades are sent for a Course Schedule)
- seminary.withdrawal.process_academic_approval (after withdrawal writeback)
- partner_transcript_import_batch.py (after transcript import)
"""

import frappe


def recompute_program_enrollment_gpa(pe_name):
    """Recompute current_gpa and current_honor for a Program Enrollment.

    Idempotent. Safe to call from any hook point.
    """
    if not pe_name:
        return

    pe = frappe.get_doc("Program Enrollment", pe_name)
    program = frappe.get_cached_doc("Program", pe.program)
    if program.is_ongoing:
        return
    basis = float(program.basis_for_gpa or 0)
    if basis <= 0:
        return

    weighted_sum = 0.0
    credit_sum = 0.0
    point_sum = 0.0
    counted_rows = 0

    for pec in pe.courses or []:
        if not pec.count_in_gpa:
            continue
        if pec.pec_finalgradenum is None:
            continue
        credits = pec.credits or 0
        if program.is_weighted and not credits:
            continue

        scale = _resolve_grading_scale(pec)
        if not scale:
            continue

        gpa_pts = _convert_to_gpa_points(pec, scale, basis)
        if gpa_pts is None:
            continue

        weighted_sum += gpa_pts * credits
        credit_sum += credits
        point_sum += gpa_pts
        counted_rows += 1

    if counted_rows == 0:
        gpa = 0.0
    elif program.is_weighted:
        gpa = weighted_sum / credit_sum if credit_sum else 0.0
    else:
        gpa = point_sum / counted_rows

    gpa = round(gpa, 2)
    honor = _resolve_honor(program, gpa)

    frappe.db.set_value(
        "Program Enrollment",
        pe_name,
        {"current_gpa": gpa, "current_honor": honor},
        update_modified=False,
    )


def _resolve_grading_scale(pec):
    """Return the Grading Scale doc to use for converting this PEC's numeric.

    Internal rows use the Course Schedule's grading scale (gradesc_cs).
    Transfer rows use the conversion policy's target_grading_scale, since
    pec_finalgradenum was written on the target scale's units at import time.
    """
    if pec.partner_seminary and pec.conversion_policy_applied:
        scale_name = frappe.db.get_value(
            "Grade Conversion Policy",
            pec.conversion_policy_applied,
            "target_grading_scale",
        )
    elif pec.course:
        scale_name = frappe.db.get_value("Course Schedule", pec.course, "gradesc_cs")
    else:
        return None

    if not scale_name:
        return None
    return frappe.get_cached_doc("Grading Scale", scale_name)


def _convert_to_gpa_points(pec, scale, basis):
    """Map a PEC row's grade to grade points on the basis scale.

    Points scales: linear scaling pec_finalgradenum / scale.maxnumgrade * basis.
    Descriptive scales: look up the matching interval by grade_code and use its
    threshold (which doubles as the GPA-points value for Descriptive scales,
    per the field's description).
    """
    if scale.grscale_type == "Points":
        max_num = float(scale.maxnumgrade or 0)
        if max_num <= 0:
            return None
        pts = (float(pec.pec_finalgradenum) / max_num) * basis
        return _clamp(pts, 0, basis)

    if scale.grscale_type == "Descriptive":
        if not pec.pec_finalgradecode:
            return None
        for interval in scale.intervals or []:
            if interval.grade_code == pec.pec_finalgradecode:
                return _clamp(float(interval.threshold or 0), 0, basis)
        return None

    return None


def _resolve_honor(program, gpa):
    levels = sorted(
        program.honors_levels or [],
        key=lambda h: float(h.min_gpa or 0),
        reverse=True,
    )
    for level in levels:
        if gpa >= float(level.min_gpa or 0):
            return level.honor_name
    return ""


def _clamp(value, low, high):
    return max(low, min(high, value))
