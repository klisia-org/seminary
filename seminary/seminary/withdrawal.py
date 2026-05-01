import frappe
from frappe import _


def on_withdrawal_workflow_update(doc, method):
    """Handle workflow state transitions for Course Withdrawal Request."""
    if doc.workflow_state == "Academically Approved":
        process_academic_approval(doc)
    elif doc.workflow_state == "Financially Approved":
        process_financial_approval(doc)
    elif doc.workflow_state == "Completed":
        process_completion(doc)


def process_academic_approval(doc):
    """Apply the withdrawal rule's grade treatment to the academic record.

    Treatments:
      - Clean Drop: delete roster and PEC rows so no transcript record remains.
        The Course Withdrawal Request is the audit trail.
      - Flat Symbol: write the rule's transcript_symbol (e.g. "W") to the roster
        and PEC. count_in_gpa = 0 (no numeric, not in GPA).
      - Calculated As-Is: run grade_thisstudent + fgrade_this_std (ungraded work
        sums as 0). Use the calculated letter and numeric directly. count_in_gpa = 1.
      - Calculated WP/WF: same calculation, then look up wp_code / wf_code on the
        course's Grading Scale by Pass/Fail. count_in_gpa follows wp_gpa / wf_gpa
        on the scale. The numeric (fscore) is preserved on PEC for transcript truth.
    """
    from seminary.seminary.api import grade_thisstudent, fgrade_this_std
    from seminary.seminary.gpa import recompute_program_enrollment_gpa

    doc.academic_processed_by = frappe.session.user

    if not doc.withdrawal_rule:
        return

    rule = frappe.get_doc("Withdrawal Rules", doc.withdrawal_rule)
    treatment = rule.grade_treatment

    cei = doc.course_enrollment_individual
    course_schedule = frappe.db.get_value(
        "Course Enrollment Individual", cei, "coursesc_ce"
    )
    student = frappe.db.get_value("Course Enrollment Individual", cei, "student_ce")

    if treatment == "Clean Drop":
        frappe.db.delete(
            "Scheduled Course Roster",
            {"course_sc": course_schedule, "student": student},
        )
        frappe.db.delete(
            "Program Enrollment Course",
            {"course": course_schedule, "parent": doc.program_enrollment},
        )
        _mark_cei_withdrawn(cei, doc.name)
        recompute_program_enrollment_gpa(doc.program_enrollment)
        return

    roster_name = frappe.db.get_value(
        "Scheduled Course Roster",
        {"course_sc": course_schedule, "student": student},
        "name",
    )
    pec = frappe.db.get_value(
        "Program Enrollment Course",
        {"course": course_schedule, "parent": doc.program_enrollment},
        "name",
    )

    if treatment == "Flat Symbol":
        symbol = rule.transcript_symbol or ""
        if roster_name:
            frappe.db.set_value(
                "Scheduled Course Roster",
                roster_name,
                {
                    "active": 0,
                    "fgrade": symbol,
                    "fgradepass": "Withdrawn",  # nosec B105
                },
            )
        if pec:
            frappe.db.set_value(
                "Program Enrollment Course",
                pec,
                {
                    "pec_finalgradecode": symbol,
                    "status": "Withdrawn",  # nosec B105
                    "count_in_gpa": 0,
                },
            )
        doc.db_set("resulting_grade", symbol, update_modified=False)
        _mark_cei_withdrawn(cei, doc.name)
        recompute_program_enrollment_gpa(doc.program_enrollment)
        return

    # Calculated * — needs a roster to score against.
    if not roster_name:
        return

    grade_thisstudent(roster_name)
    fgrade_this_std(roster_name)
    fscore, calc_grade, fgradepass = frappe.db.get_value(
        "Scheduled Course Roster",
        roster_name,
        ["fscore", "fgrade", "fgradepass"],
    )

    final_code = calc_grade
    count_in_gpa = 1
    if treatment == "Calculated WP/WF":
        gscale_name = frappe.db.get_value(
            "Course Schedule", course_schedule, "gradesc_cs"
        )
        if gscale_name:
            scale = frappe.get_cached_doc("Grading Scale", gscale_name)
            if fgradepass == "Pass" and scale.wp_code:
                final_code = scale.wp_code
                count_in_gpa = 1 if scale.wp_gpa else 0
            elif fgradepass == "Fail" and scale.wf_code:
                final_code = scale.wf_code
                count_in_gpa = 1 if scale.wf_gpa else 0

    frappe.db.set_value(
        "Scheduled Course Roster",
        roster_name,
        {
            "active": 0,
            "fgrade": final_code,
            "fgradepass": "Withdrawn",  # nosec B105
        },
    )
    if pec:
        frappe.db.set_value(
            "Program Enrollment Course",
            pec,
            {
                "pec_finalgradecode": final_code,
                "pec_finalgradenum": fscore,
                "status": "Withdrawn",  # nosec B105
                "count_in_gpa": count_in_gpa,
            },
        )
    doc.db_set("resulting_grade", final_code, update_modified=False)
    _mark_cei_withdrawn(cei, doc.name)
    recompute_program_enrollment_gpa(doc.program_enrollment)


def _mark_cei_withdrawn(cei, withdrawal_request):
    frappe.db.set_value(
        "Course Enrollment Individual",
        cei,
        {
            "withdrawn": 1,
            "withdrawal_request": withdrawal_request,
        },
    )


def process_financial_approval(doc):
    """Generate credit notes against Sales Invoices for the withdrawn CEI."""
    from erpnext.controllers.sales_and_purchase_return import make_return_doc

    doc.financial_processed_by = frappe.session.user

    if not doc.withdrawal_rule:
        return

    rule = frappe.get_doc("Withdrawal Rules", doc.withdrawal_rule)
    if not rule.has_refund or not rule.withdrawal_refunds:
        return

    cei_name = doc.course_enrollment_individual

    # Find all submitted, non-return Sales Invoices for this CEI
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "custom_cei": cei_name,
            "docstatus": 1,
            "is_return": 0,
        },
        fields=["name", "customer", "grand_total"],
    )

    if not invoices:
        return

    # Get payer type references
    settings = frappe.get_cached_doc("Seminary Settings")
    scholarship_cust = settings.scholarship_cust
    scholarship_procedure = settings.default_scholarship_withdrawal_procedure

    student = frappe.db.get_value(
        "Course Enrollment Individual", cei_name, "student_ce"
    )
    student_customer = (
        frappe.db.get_value("Student", student, "customer") if student else None
    )

    # Build refund map by payer type
    refund_map = {}
    for row in rule.withdrawal_refunds:
        refund_map[row.payer_type] = {
            "refund_percent": row.refund_percent,
            "refund_to": row.refund_to,
        }

    for inv in invoices:
        # Determine payer type
        if scholarship_cust and inv.customer == scholarship_cust:
            payer_type = "Scholarships"
        elif student_customer and inv.customer == student_customer:
            payer_type = "Student"
        else:
            payer_type = "Other Payers"

        refund_info = refund_map.get(payer_type)
        if not refund_info or not refund_info["refund_percent"]:
            continue

        refund_pct = refund_info["refund_percent"] / 100

        # Skip scholarship invoices with 0 grand_total (100% discount)
        if inv.grand_total == 0 and payer_type == "Scholarships":
            continue

        # Create return doc using ERPNext's built-in method
        return_doc = make_return_doc("Sales Invoice", inv.name)

        # Scale item quantities by refund percentage
        for item in return_doc.items:
            item.qty = item.qty * refund_pct

        return_doc.remarks = (
            f"Withdrawal refund for {cei_name} ({refund_info['refund_percent']}%)"
        )
        return_doc.insert(ignore_permissions=True)
        return_doc.submit()

        # If scholarship procedure requires invoicing the student
        if (
            payer_type == "Scholarships"
            and scholarship_procedure
            == "Refund to Scholarship Fund and Create Invoice for Student"
            and student_customer
            and inv.grand_total > 0
        ):
            _create_student_invoice_for_scholarship(
                inv, student_customer, refund_pct, cei_name, settings
            )


def _create_student_invoice_for_scholarship(
    original_inv, student_customer, refund_pct, cei_name, settings
):
    """Create a new Sales Invoice to the student for the scholarship amount being clawed back."""
    source_doc = frappe.get_doc("Sales Invoice", original_inv.name)

    items = []
    for item in source_doc.items:
        items.append(
            {
                "item_name": item.item_name,
                "item_code": item.item_code,
                "qty": abs(item.qty) * refund_pct,
                "rate": item.rate,
                "income_account": item.income_account,
                "cost_center": item.cost_center,
                "description": f"Scholarship withdrawal charge for {cei_name}",
            }
        )

    si = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "naming_series": "ACC-SINV-.YYYY.-",
            "posting_date": frappe.utils.today(),
            "company": source_doc.company,
            "currency": source_doc.currency,
            "debit_to": frappe.db.get_single_value(
                "Seminary Settings", "receivable_account"
            ),
            "customer": student_customer,
            "selling_price_list": source_doc.selling_price_list,
            "remarks": f"Scholarship withdrawal charge for {cei_name}",
            "items": items,
            "custom_student": frappe.db.get_value(
                "Course Enrollment Individual", cei_name, "student_ce"
            ),
        }
    )
    si.insert(ignore_permissions=True)
    si.submit()


def process_completion(doc):
    """Handle final completion — check if Full Program Withdrawal needs to deactivate enrollment."""
    if doc.withdrawal_scope == "Full Program Withdrawal" and doc.is_parent:
        all_children = frappe.get_all(
            "Course Withdrawal Request",
            filters={
                "parent_withdrawal": doc.name,
                "docstatus": 1,
            },
            fields=["workflow_state"],
        )

        all_completed = all(c.workflow_state == "Completed" for c in all_children)

        if all_completed:
            frappe.db.set_value(
                "Program Enrollment",
                doc.program_enrollment,
                "pgmenrol_active",
                0,
            )


@frappe.whitelist()
def get_withdrawal_rule_for_date(academic_term, effective_date):
    """Find the matching withdrawal rule for a given term and date."""
    term_rule = frappe.db.get_value(
        "Term Withdrawal Rules",
        filters={
            "academic_term": academic_term,
            "applies_until": (">=", effective_date),
        },
        fieldname=["name", "withdrawal_rule"],
        order_by="applies_until asc",
        as_dict=True,
    )
    if term_rule:
        return term_rule.withdrawal_rule
    return None


@frappe.whitelist()
def calculate_dynamic_date(withdrawal_rule, academic_term):
    """Calculate the applies_until date for a Term Withdrawal Rule based on the dynamic date fields."""
    from datetime import timedelta

    rule = frappe.get_doc("Withdrawal Rules", withdrawal_rule)
    term = frappe.get_doc("Academic Term", academic_term)

    if not rule.term_based_date or not rule.days_after_term_start:
        return None

    base_date = frappe.utils.add_days(term.term_start_date, rule.days_after_term_start)

    if rule.day_of_week and rule.day_of_week != "Any":
        day_map = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6,
        }
        target_day = day_map.get(rule.day_of_week, 0)
        current_day = base_date.weekday()
        days_ahead = target_day - current_day
        if days_ahead <= 0:
            days_ahead += 7
        base_date = base_date + timedelta(days=days_ahead)

    if rule.adjust_for_holidays and rule.adjust_for_holidays != "No adjustment":
        from frappe.utils import getdate

        holiday_list = frappe.db.get_single_value("Seminary Settings", "company")
        if holiday_list:
            company_holiday_list = frappe.db.get_value(
                "Company", holiday_list, "default_holiday_list"
            )
            if company_holiday_list:
                is_holiday = frappe.db.exists(
                    "Holiday",
                    {"parent": company_holiday_list, "holiday_date": base_date},
                )
                if is_holiday:
                    if rule.adjust_for_holidays == "Subtract one day":
                        base_date = base_date - timedelta(days=1)
                    elif rule.adjust_for_holidays == "Add one day":
                        base_date = base_date + timedelta(days=1)

    if base_date > frappe.utils.getdate(term.term_end_date):
        base_date = frappe.utils.getdate(term.term_end_date)

    return str(base_date)
