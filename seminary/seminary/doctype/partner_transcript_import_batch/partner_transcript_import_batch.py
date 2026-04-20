import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class PartnerTranscriptImportBatch(Document):
    def validate(self):
        self._validate_partner_and_policy_submitted()

    def before_submit(self):
        if self.batch_status != "Dry-Run Clean":
            frappe.throw(
                _(
                    "Batch must reach 'Dry-Run Clean' status before it can be committed. "
                    "Current status: {0}."
                ).format(self.batch_status)
            )
        unresolved = [row for row in self.rows if row.warning and not row.override_note]
        if unresolved:
            frappe.throw(
                _(
                    "{0} row(s) have unresolved warnings. Provide an override note or correct the source data and re-run dry-run."
                ).format(len(unresolved))
            )
        missing_student = [r for r in self.rows if not r.student]
        if missing_student:
            frappe.throw(
                _(
                    "{0} row(s) still lack a resolved Student. Run Dry-Run again."
                ).format(len(missing_student))
            )

    def on_submit(self):
        self._commit_rows()
        self.db_set("batch_status", "Committed", update_modified=False)
        self.db_set("committed_on", now_datetime(), update_modified=False)
        self.db_set("committed_by", frappe.session.user, update_modified=False)

    def before_cancel(self):
        """Cancellation of a committed batch is blocked unless the resulting transcript
        entries have been separately removed. This is a supervised operation."""
        committed_pes = {
            row.committed_program_enrollment
            for row in self.rows
            if row.committed_program_enrollment
        }
        still_referencing = frappe.db.count(
            "Program Enrollment Course",
            filters={
                "partner_seminary": self.partner_seminary,
                "parent": ("in", list(committed_pes)) if committed_pes else ("=", ""),
            },
        )
        if still_referencing:
            frappe.throw(
                _(
                    "Cannot cancel: {0} transcript row(s) from this batch still exist on Program Enrollments. "
                    "Remove them first (supervised operation)."
                ).format(still_referencing)
            )

    def _validate_partner_and_policy_submitted(self):
        if not self.partner_seminary:
            return
        partner = frappe.get_cached_doc("Partner Seminary", self.partner_seminary)
        if partner.status in ("Inactive", "Archived"):
            frappe.throw(
                _(
                    "Partner Seminary '{0}' has status '{1}' and cannot accept new imports."
                ).format(self.partner_seminary, partner.status)
            )
        policy_docstatus = frappe.db.get_value(
            "Grade Conversion Policy",
            partner.default_conversion_policy,
            "docstatus",
        )
        if policy_docstatus != 1:
            frappe.throw(
                _(
                    "Partner Seminary '{0}' default conversion policy '{1}' must be submitted before importing."
                ).format(self.partner_seminary, partner.default_conversion_policy)
            )

    @frappe.whitelist()
    def get_import_options(self):
        """Returns autocomplete options for manual row entry: submitted equivalences'
        source_course_codes and the partner's default grading scale grade codes."""
        if not self.partner_seminary:
            return {"course_codes": [], "grade_codes": []}

        equivalences = frappe.get_all(
            "Partner Seminary Course Equivalence",
            filters={"partner_seminary": self.partner_seminary, "docstatus": 1},
            fields=["source_course_code"],
            order_by="source_course_code asc",
            limit_page_length=0,
        )
        seen = set()
        course_codes = []
        for row in equivalences:
            code = row.source_course_code
            if code and code not in seen:
                seen.add(code)
                course_codes.append(code)

        partner = frappe.get_cached_doc("Partner Seminary", self.partner_seminary)
        grade_codes = []
        if partner.default_grading_scale:
            intervals = frappe.get_all(
                "Grading Scale Interval",
                filters={"parent": partner.default_grading_scale},
                fields=["grade_code", "threshold"],
                order_by="threshold desc",
                limit_page_length=0,
            )
            grade_codes = [i.grade_code for i in intervals if i.grade_code]

        return {"course_codes": course_codes, "grade_codes": grade_codes}

    @frappe.whitelist()
    def dry_run(self):
        """Resolve every row: internal course via equivalence, credit via credit_unit_ratio × source_credit_value
        (or credit_override), converted grade via the policy's convert() service. Flags warnings without creating
        transcript entries. Clears any prior resolution before recomputing."""
        from seminary.seminary.doctype.grade_conversion_policy.grade_conversion_policy import (
            convert_grade,
        )

        if not self.rows:
            frappe.throw(_("Cannot run dry-run on an empty batch."))

        partner = frappe.get_cached_doc("Partner Seminary", self.partner_seminary)
        clean = True
        for row in self.rows:
            student_warning = _resolve_student(row)
            if student_warning:
                row.warning = student_warning
                row.resolved_internal_course = None
                row.resolved_credit = None
                row.resolved_grade_code = None
                row.resolved_grade_threshold = None
                if not row.override_note:
                    clean = False
                continue

            result = _resolve_row(row, partner, convert_grade)
            row.resolved_internal_course = result.get("internal_course")
            row.resolved_credit = result.get("credit")
            row.resolved_grade_code = result.get("grade_code")
            row.resolved_grade_threshold = result.get("grade_threshold")
            row.warning = result.get("warning") or ""
            if row.warning and not row.override_note:
                clean = False
        self.batch_status = "Dry-Run Clean" if clean else "Draft"
        self.save()
        return {"clean": clean}

    def _commit_rows(self):
        """Upsert Program Enrollment + Program Enrollment Course rows for every staged row.
        Idempotency key: (student, partner_seminary, source_course_code, source_term),
        or external_reference when present. Recalculates aggregate credit totals on each
        affected Program Enrollment after commit."""
        from seminary.seminary.api import (
            _check_auto_grant_emphases,
            _recalculate_emphasis_credits,
        )

        partner = frappe.get_cached_doc("Partner Seminary", self.partner_seminary)
        affected_pes = set()
        for row in self.rows:
            program_enrollment = _get_or_create_program_enrollment(
                student=row.student,
                program=self.target_program,
                academic_term=self.target_academic_term,
            )
            _upsert_transcript_row(
                program_enrollment=program_enrollment,
                row=row,
                partner=partner,
                batch=self,
            )
            row.db_set(
                "committed_program_enrollment",
                program_enrollment.name,
                update_modified=False,
            )
            affected_pes.add(program_enrollment.name)

        for pe_name in affected_pes:
            _refresh_totalcredits(pe_name)
            _recalculate_emphasis_credits(pe_name)
            _check_auto_grant_emphases(pe_name)


def _resolve_student(row):
    """Resolve a row's student from student_email when the Student link is blank.
    Conversely, back-fill student_email from Student.user when only the link is set.
    Returns a warning code (string) on failure, or None on success."""
    if not row.student and row.student_email:
        match = frappe.db.get_value("Student", {"user": row.student_email}, "name")
        if not match:
            return "unknown_student_email"
        row.student = match
    if row.student and not row.student_email:
        email = frappe.db.get_value("Student", row.student, "user")
        if email:
            row.student_email = email
    return None


def _resolve_row(row, partner, convert_grade):
    """Pure function — given an import row and partner context, returns a dict with resolved
    fields and (optionally) a warning code. No side effects. Called from dry_run."""
    equivalence = frappe.db.get_value(
        "Partner Seminary Course Equivalence",
        {
            "partner_seminary": partner.name,
            "source_course_code": row.source_course_code,
            "docstatus": 1,
        },
        [
            "name",
            "internal_course",
            "credit_override",
            "conversion_policy_override",
            "source_credit_value",
        ],
        as_dict=True,
    )
    if not equivalence:
        return {"warning": "no_submitted_equivalence"}

    policy_name = (
        equivalence.conversion_policy_override or partner.default_conversion_policy
    )
    conversion = convert_grade(policy_name, row.source_grade)

    if equivalence.credit_override:
        credit = flt(equivalence.credit_override)
    else:
        effective_source_credit = flt(row.source_credit_value) or flt(
            equivalence.source_credit_value
        )
        credit = flt(partner.credit_unit_ratio) * effective_source_credit

    warning = conversion.get("warning")
    if not credit:
        warning = "zero_credits"
    elif partner.minimum_transferable_grade and not _meets_minimum(
        conversion.get("grade_threshold"),
        partner.default_grading_scale,
        partner.minimum_transferable_grade,
    ):
        warning = "below_minimum_transferable"

    return {
        "internal_course": equivalence.internal_course,
        "credit": credit,
        "grade_code": conversion.get("grade_code"),
        "grade_threshold": conversion.get("grade_threshold"),
        "warning": warning,
    }


def _meets_minimum(resolved_threshold, scale_name, minimum_grade_code):
    minimum_threshold = frappe.db.get_value(
        "Grading Scale Interval",
        {"parent": scale_name, "grade_code": minimum_grade_code},
        "threshold",
    )
    if minimum_threshold is None:
        return True
    return flt(resolved_threshold) >= flt(minimum_threshold)


def _refresh_totalcredits(pe_name):
    """Re-sum credits from passing Program Enrollment Course rows and write to
    Program Enrollment.totalcredits. Bypass validate_update_after_submit via db_set."""
    total = frappe.db.sql(
        """SELECT COALESCE(SUM(credits), 0)
           FROM `tabProgram Enrollment Course`
           WHERE parent = %s AND status = 'Pass'""",
        (pe_name,),
    )[0][0]
    frappe.db.set_value(
        "Program Enrollment", pe_name, "totalcredits", int(total), update_modified=False
    )


def _get_or_create_program_enrollment(student, program, academic_term):
    existing = frappe.db.get_value(
        "Program Enrollment",
        {
            "student": student,
            "program": program,
            "academic_term": academic_term,
            "docstatus": 1,
        },
        "name",
    )
    if existing:
        return frappe.get_doc("Program Enrollment", existing)
    pe = frappe.new_doc("Program Enrollment")
    pe.student = student
    pe.program = program
    pe.academic_term = academic_term
    pe.pgmenrol_active = 1
    pe.insert()
    pe.submit()
    return pe


def _upsert_transcript_row(program_enrollment, row, partner, batch):
    """Idempotent append/update of a Program Enrollment Course child row for a partner-sourced grade.
    Looks up the existing row via a direct DB query so None/empty-string equivalence doesn't cause false misses.
    """
    if row.external_reference:
        filters = {
            "parent": program_enrollment.name,
            "partner_seminary": partner.name,
            "external_reference": row.external_reference,
        }
    else:
        filters = {
            "parent": program_enrollment.name,
            "partner_seminary": partner.name,
            "source_course_code": row.source_course_code,
            "source_term": row.source_term or "",
        }
    existing_name = frappe.db.get_value("Program Enrollment Course", filters, "name")

    existing_row = None
    if existing_name:
        for pec_row in program_enrollment.courses or []:
            if pec_row.name == existing_name:
                existing_row = pec_row
                break

    equivalence_name = frappe.db.get_value(
        "Partner Seminary Course Equivalence",
        {
            "partner_seminary": partner.name,
            "source_course_code": row.source_course_code,
            "docstatus": 1,
        },
        "name",
    )
    policy_name = (
        frappe.db.get_value(
            "Partner Seminary Course Equivalence",
            equivalence_name,
            "conversion_policy_override",
        )
        or partner.default_conversion_policy
    )
    mapping_type = "legacy_identity" if partner.is_internal_legacy else "equivalence"

    values = {
        "course_name": row.resolved_internal_course,
        "academic_term": batch.target_academic_term,
        "pec_finalgradecode": row.resolved_grade_code,
        "pec_finalgradenum": row.resolved_grade_threshold,
        "credits": int(flt(row.resolved_credit)),
        "status": "Pass",
        "is_transfer": 1,
        "partner_seminary": partner.name,
        "mapping_type": mapping_type,
        "course_equivalence": equivalence_name,
        "conversion_policy_applied": policy_name,
        "source_course_code": row.source_course_code,
        "source_term": row.source_term,
        "source_grade": row.source_grade,
        "external_reference": row.external_reference,
        "conversion_warning": row.warning or "None",
        "conversion_override_note": row.override_note,
    }

    if existing_row:
        # Parent Program Enrollment is already submitted; update the child row directly
        # via db.set_value to bypass validate_update_after_submit. Matches the pattern used
        # in api.py::_send_grades when instructor grades land after PE submission.
        frappe.db.set_value("Program Enrollment Course", existing_row.name, values)
    else:
        program_enrollment.append("courses", values)
        program_enrollment.save()
