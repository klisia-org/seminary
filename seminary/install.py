import frappe

# from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.desk.page.setup_wizard.setup_wizard import make_records
import os
import re
from frappe.desk.doctype.global_search_settings.global_search_settings import (
    update_global_search_doctypes,
)
from frappe.utils.dashboard import sync_dashboards
from frappe import _


# TODO: create uninstall file and remove all the custom fields, roles, assessment groups, fixtures, etc
# TODO: Remove all Items created when Fee Category is created
# TODO: Remove all Customers (with group = Student) & Users created (with role = Student) when Student is created.


def before_install():
    check_erpnext()


def after_install():
    check_erpnext()
    setup_fixtures()
    create_studentappl_role()
    create_student_role()
    create_alumni_role()
    create_partner_role()
    create_registrar_role()
    create_instructor_role()
    create_external_examiner_role()
    create_program_chair_role()
    create_seminary_manager_role()
    get_custom_fields()
    setup_sales_invoice_permissions()
    update_company_in_item_details()
    seed_fee_categories()
    seed_assessment_criteria()
    seed_course_cancellation_reasons()
    seed_grading_scale()
    seed_culminating_project_types()
    seed_disciplinary_actions()
    seed_faculty_capabilities()
    seed_room_features()
    seed_communication_channels()
    seed_channel_provider_accounts()
    seed_mailing_label_formats()
    seed_communication_templates()
    seed_portal_messaging_rules()
    seed_partner_types()
    seed_skill_tags()
    seed_allowed_graduation_documents()
    seed_internship_types()
    seed_internship_communication()
    setup_customer_person_field()


def check_erpnext():
    check_erpnext_installed()
    status = check_erpnext_setup_complete()
    if status["errors"]:
        frappe.throw(
            _(
                "ERPNext setup is incomplete. Please complete the setup before installing {0}"
            ).format("SeminaryERP"),
            title=_("Setup Incomplete"),
        )


def check_erpnext_installed():
    """Check if ERPNext app is installed on the site."""
    installed_apps = frappe.get_installed_apps()
    if "erpnext" not in installed_apps:
        frappe.throw(
            _("ERPNext must be installed before installing {0}").format("SeminaryERP"),
            title=_("Missing Dependency"),
        )


def check_erpnext_setup_complete():
    """
    Check if ERPNext has been set up (i.e., the Setup Wizard was completed
    and at least one Company exists).
    Returns a dict with detailed status.
    """
    status = {
        "company_exists": False,
        "fiscal_year_exists": False,
        "selling_price_list_exists": False,
        "buying_price_list_exists": False,
        "default_company": None,
        "errors": [],
    }

    # Check for Company
    companies = frappe.get_all("Company", limit=1, pluck="name")
    if companies:
        status["company_exists"] = True
        status["default_company"] = companies[0]
    else:
        status["errors"].append(
            _("No Company found. Please complete the ERPNext Setup Wizard first.")
        )

    # Check for Fiscal Year
    if frappe.db.count("Fiscal Year") > 0:
        status["fiscal_year_exists"] = True
    else:
        status["errors"].append(_("No Fiscal Year found."))

    # Check for Selling Price List
    selling_pl = frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name")
    if selling_pl:
        status["selling_price_list_exists"] = True
    else:
        status["errors"].append(_("No active Selling Price List found."))

    # Check for Buying Price List
    buying_pl = frappe.db.get_value("Price List", {"buying": 1, "enabled": 1}, "name")
    if buying_pl:
        status["buying_price_list_exists"] = True
    else:
        status["errors"].append(_("No active Buying Price List found."))

    return status


def setup_fixtures():
    default_price_list = frappe.db.get_value(
        "Price List", {"selling": 1, "enabled": 1}, "name", order_by="creation asc"
    )
    records = [
        # Item Group Records
        {"doctype": "Item Group", "item_group_name": "Tuition"},
        # Customer Group Records
        {
            "doctype": "Customer Group",
            "customer_group_name": "Student",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Donor",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Church",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Denomination",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Seminary",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Para-church Organization",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Alumni",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Board Member",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Volunteer",
            "default_price_list": default_price_list,
        },
        # UOM
        {"doctype": "UOM", "uom_name": _("Academic Event"), "must_be_whole_number": 0},
        {"doctype": "UOM", "uom_name": _("Credit hour"), "must_be_whole_number": 0},
        # Supplier Group for non-employee instructors (volunteers, guest lecturers)
        {"doctype": "Supplier Group", "supplier_group_name": _("Instructor")},
        # Instructor Category defaults — schools can add/remove
        {
            "doctype": "Instructor Category",
            "category_name": _("Instructor of Record"),
            "is_instructor_of_record": 1,
            "description": _(
                "Primary instructor responsible for the course for accreditation purposes."
            ),
        },
        {
            "doctype": "Instructor Category",
            "category_name": _("Co-Instructor"),
            "description": _("Shares teaching duties with the Instructor of Record."),
        },
        {
            "doctype": "Instructor Category",
            "category_name": _("Graduate Teaching Assistant"),
            "description": _(
                "Graduate student assisting with teaching and grading under faculty supervision."
            ),
        },
        {
            "doctype": "Instructor Category",
            "category_name": _("Grader"),
            "description": _("Grades assignments and assessments only."),
        },
    ]
    make_records(records)


def seed_fee_categories():
    """Seed the starter Fee Categories if they don't already exist.

    NOT fixtures: Fee Category.validate_audit() cross-checks a category's
    is_credit against Seminary Settings (auditcredit / allow_audit). The moment a
    seminary flips that setting — or edits a category — a fixture re-import on
    migrate re-validates the shipped rows and throws (e.g. "set to charge audit
    as a flat fee, not per credit"). So we create the defaults once
    (create-only-if-missing) and never re-touch them.

    The Audit Fee is seeded as a flat fee (is_credit=0) to match the default
    auditcredit=0 setting, so a fresh seed validates cleanly; a seminary that
    charges audit per credit flips both the setting and this category itself.

    Each row references a fixtured Item and Payment Terms Template — we skip any
    row whose dependencies aren't present yet (so install ordering can't make us
    throw); the next migrate, with fixtures loaded, fills it in.
    """
    # category_name, fc_event, item, is_audit, is_credit
    defaults = [
        ("Program Admission Fee", "Program Enrollment", "Admission Fee", 0, 0),
        ("Registration fee (new term)", "New Academic Term", "Admission Fee", 0, 0),
        ("Credit hour", "Course Enrollment", "Credit hour", 0, 1),
        ("Audit Fee", "Course Enrollment", "Audit Flat Fee", 1, 0),
    ]
    payment_term_template = "For immediate payment"
    has_payment_term = frappe.db.exists("Payment Terms Template", payment_term_template)
    for category_name, fc_event, item, is_audit, is_credit in defaults:
        if frappe.db.exists("Fee Category", category_name):
            continue
        if not frappe.db.exists("Item", item):
            continue
        frappe.get_doc(
            {
                "doctype": "Fee Category",
                "category_name": category_name,
                "feecategory_type": "Tuition",
                "fc_event": fc_event,
                "item": item,
                "is_audit": is_audit,
                "is_credit": is_credit,
                "payment_term_template": (
                    payment_term_template if has_payment_term else None
                ),
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_assessment_criteria():
    """Seed the starter Assessment Criteria if they don't already exist.

    NOT fixtures: seminaries curate their own grading criteria on the desk, and a
    fixture re-import would clobber those edits every migrate. Created once,
    create-only-if-missing. (The "Discussion" row shipped in the old fixture was
    mis-typed as a Discussion Activity — a per-course transactional doctype, not
    a catalog — so it never became a real criterion; it's seeded correctly here.)
    """
    # assessment_criteria (name), type
    defaults = [
        ("Project", "Assignment"),
        ("Participation", "Offline"),
        ("Quiz", "Quiz"),
        ("Exam", "Exam"),
        ("Discussion", "Discussion"),
        ("Academic Paper with Online Submission", "Assignment"),
    ]
    for criteria, criteria_type in defaults:
        if frappe.db.exists("Assessment Criteria", criteria):
            continue
        frappe.get_doc(
            {
                "doctype": "Assessment Criteria",
                "assessment_criteria": criteria,
                "type": criteria_type,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_course_cancellation_reasons():
    """Seed the starter Course Cancellation Reasons if they don't already exist.

    NOT fixtures: seminaries add/retire reasons on the desk, and a fixture
    re-import would clobber those edits (and the is_active toggle) every migrate.
    Created once, create-only-if-missing.
    """
    # reason_name, description
    defaults = [
        (
            "Insufficient Enrollment",
            _(
                "The course did not reach the minimum number of enrolled students by the enrollment deadline."
            ),
        ),
        (
            "Instructor Unavailable",
            _(
                "The instructor cannot teach the course (illness, leave, departure, scheduling conflict)."
            ),
        ),
        (
            "Curriculum Change",
            _(
                "The course was removed from or changed in the curriculum after the schedule was published."
            ),
        ),
        (
            "Administrative Decision",
            _(
                "The course is cancelled by administrative or departmental decision (resource constraints, restructuring)."
            ),
        ),
        (
            "Force Majeure",
            _(
                "The course is cancelled due to circumstances beyond the seminary's control (natural disaster, public health, civil unrest)."
            ),
        ),
    ]
    for reason_name, description in defaults:
        if frappe.db.exists("Course Cancellation Reason", reason_name):
            continue
        frappe.get_doc(
            {
                "doctype": "Course Cancellation Reason",
                "reason_name": reason_name,
                "is_active": 1,
                "description": description,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_grading_scale():
    """Seed the starter Default Numeric Scale if it doesn't already exist.

    NOT a fixture: Grading Scale is submittable and seminaries define their own
    scales; a fixture re-import would clobber edits every migrate. Created once,
    create-only-if-missing, and submitted (docstatus=1) so it can be used.
    """
    name = "Default Numeric Scale"
    if frappe.db.exists("Grading Scale", name):
        return
    # grade_code, grade_pass, threshold
    intervals = [
        ("A+", "Pass", 98.0),
        ("A", "Pass", 96.0),
        ("A-", "Pass", 94.0),
        ("B+", "Pass", 92.0),
        ("B", "Pass", 89.0),
        ("B-", "Pass", 86.0),
        ("C+", "Pass", 83.0),
        ("C", "Pass", 80.0),
        ("C-", "Pass", 77.0),
        ("D+", "Pass", 74.0),
        ("D", "Pass", 72.0),
        ("D-", "Pass", 69.0),
        ("F", "Fail", 0.0),
    ]
    doc = frappe.get_doc(
        {
            "doctype": "Grading Scale",
            "grading_scale_name": name,
            "grscale_type": "Points",
            "maxnumgrade": 100.0,
            "fa_code": "FA",
            "fa_gpa": 0,
            "intervals": [
                {
                    "grade_code": code,
                    "grade_description": code,
                    "grade_pass": grade_pass,
                    "threshold": threshold,
                }
                for code, grade_pass, threshold in intervals
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    doc.submit()
    frappe.db.commit()


def seed_culminating_project_types():
    """Seed the starter Culminating Project Types if they don't already exist.

    These are NOT shipped as fixtures: seminaries configure each type's
    milestones on the desk, and a fixture re-import on every migrate would wipe
    those milestone rows. So we create the defaults once (create-only-if-missing)
    and never overwrite an existing type or its milestones.
    """
    defaults = [
        (
            "Thesis",
            _("A formal research thesis directed by an advisor and a second reader."),
        ),
        (
            "Capstone",
            _("An integrative capstone project demonstrating mastery of the program."),
        ),
        ("Dissertation", _("An extended doctoral-level research dissertation.")),
        (
            "Summative Paper",
            _("A summative research paper offered as an alternative to a full thesis."),
        ),
        (
            "Doctrinal Statement",
            _("A written doctrinal statement offered as a culminating-project option."),
        ),
    ]
    for type_name, description in defaults:
        if frappe.db.exists("Culminating Project Type", type_name):
            continue
        frappe.get_doc(
            {
                "doctype": "Culminating Project Type",
                "type_name": type_name,
                "is_active": 1,
                "description": description,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_disciplinary_actions():
    """Seed the starter Disciplinary Actions if they don't already exist.

    Like Culminating Project Types, these are NOT fixtures: seminaries adjust
    the catalog on the desk and a fixture re-import would clobber edits. Created
    once, create-only-if-missing. The Dismissal action carries
    `triggers_dismissal` so an applied dismissal sanction drives a program
    separation through the shared spine (see ADR 032).
    """
    defaults = [
        ("Verbal Warning", "Informal", 0, _("An informal verbal warning.")),
        ("Written Warning", "Formal", 0, _("A formal written warning on record.")),
        (
            "Disciplinary Probation",
            "Probation",
            0,
            _("A defined period of probation with conditions."),
        ),
        (
            "Suspension",
            "Suspension",
            0,
            _("Temporary suspension from program activities."),
        ),
        (
            "Dismissal",
            "Dismissal",
            1,
            _("Involuntary dismissal from the program."),
        ),
    ]
    for action_name, severity, triggers, description in defaults:
        if frappe.db.exists("Disciplinary Action", action_name):
            continue
        frappe.get_doc(
            {
                "doctype": "Disciplinary Action",
                "action_name": action_name,
                "severity": severity,
                "triggers_dismissal": triggers,
                "is_active": 1,
                "description": description,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_faculty_capabilities():
    """Seed the starter Faculty Capabilities if they don't already exist (ADR 059).

    NOT fixtures: seminaries curate the catalog on the desk and a fixture
    re-import would clobber edits. One starter capability per ``routes_to``
    machine key; schools rename the display name or add more freely.
    """
    # (capability_name, routes_to, tracks_capacity, description). Capacity-aware
    # routes (advising/examining/verifying) feed claim_capability's round-robin;
    # Course Instructor (CS-driven) / Mentor (free link) / Board carry no cap.
    defaults = [
        ("Course Instructor", "Course Instructor", 0, _("Teaches course sections.")),
        (
            "Thesis/CP Advisor",
            "Thesis/CP Advisor",
            1,
            _("Advises culminating projects."),
        ),
        ("Internship Advisor", "Internship Advisor", 1, _("Oversees internships.")),
        (
            "Placement Examiner",
            "Placement Examiner",
            1,
            _("Grades placement assessments."),
        ),
        (
            "Manual-Verification Verifier",
            "Manual-Verification Verifier",
            1,
            _("Verifies manual graduation requirements."),
        ),
        ("Mentor", "Mentor", 0, _("Mentors student groups.")),
        (
            "Committee/Board Member",
            "Committee/Board Member",
            0,
            _("Serves on a board or committee (no instructor record required)."),
        ),
    ]
    for capability_name, routes_to, tracks_capacity, description in defaults:
        if frappe.db.exists("Faculty Capability", capability_name):
            continue
        frappe.get_doc(
            {
                "doctype": "Faculty Capability",
                "capability_name": capability_name,
                "routes_to": routes_to,
                "tracks_capacity": tracks_capacity,
                "is_active": 1,
                "description": description,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_room_features():
    """Seed starter Room Features if they don't already exist.

    Not fixtures (seminaries curate their own catalog on the desk, and a
    fixture re-import would clobber edits — see ADR 035). The accessibility
    feature in particular lets a Course Type *require* an accessible room,
    which the standalone Room.accessible check could never express. Created
    once, create-only-if-missing.
    """
    defaults = [
        ("Wheelchair Accessible", "Specialized"),
        ("Projector", "AV Equipment"),
        ("Screen", "AV Equipment"),
        ("Sound System", "AV Equipment"),
        ("Whiteboard", "Room Configuration"),
        ("Piano", "Musical"),
        ("Movable Seating", "Room Configuration"),
    ]
    for feature, category in defaults:
        if frappe.db.exists("Room Feature", {"feature": feature}):
            continue
        frappe.get_doc(
            {
                "doctype": "Room Feature",
                "feature": feature,
                "category": category,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


# Inline brand SVGs for the portal contact icons (formerly the Messaging App
# master, retired into Communication Channel — see the migration patch).
_WHATSAPP_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#25D366"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>'  # noqa: E501
_TELEGRAM_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#26A5E4"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>'  # noqa: E501
_INAPP_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'  # noqa: E501
_EMAIL_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>'  # noqa: E501


def seed_communication_channels():
    """Seed the semantic Communication Channels (ADR 042/043).

    Not fixtures (a re-import would clobber seminary edits — channels grow
    configuration like provider accounts and rate limits in ADR 043). Created
    once, create-only-if-missing. Names are stable identifiers referenced from
    code (Person primary-address sync); descriptions are free to edit.

    Portal-contact metadata (icon, deep-link prefix, the portal_contactable
    flag) is seeded here and backfilled onto existing rows when empty, so the
    instructor contact icons (formerly the Messaging App master) render from the
    channel itself — without clobbering a seminary's edits.
    """
    # name, description, portal_contactable, weblink_prefix, svg_icon
    defaults = [
        ("Email", _("Email delivery."), 1, "mailto:", _EMAIL_SVG),
        ("SMS", _("Text messages to the primary mobile number."), 0, None, None),
        ("WhatsApp", _("WhatsApp messages."), 1, "https://wa.me/", _WHATSAPP_SVG),
        ("Telegram", _("Telegram messages."), 1, "https://t.me/", _TELEGRAM_SVG),
        ("In-App", _("Portal inbox messages."), 1, None, _INAPP_SVG),
        ("Print", _("Generated PDF documents / printed letters."), 0, None, None),
        ("Voice", _("Voice / IVR calls."), 0, None, None),
    ]
    for channel_name, description, contactable, prefix, svg in defaults:
        if not frappe.db.exists("Communication Channel", channel_name):
            frappe.get_doc(
                {
                    "doctype": "Communication Channel",
                    "channel_name": channel_name,
                    "enabled": 1,
                    "description": description,
                    "portal_contactable": contactable,
                    "weblink_prefix": prefix,
                    "svg_icon": svg,
                }
            ).insert(ignore_permissions=True)
            continue
        # Backfill contact metadata onto an existing row only where empty, so a
        # re-run (or an old install predating these fields) lights up the icons
        # without overwriting any seminary customisation.
        if not contactable and not prefix and not svg:
            continue
        current = frappe.db.get_value(
            "Communication Channel",
            channel_name,
            ["portal_contactable", "weblink_prefix", "svg_icon"],
            as_dict=True,
        )
        updates = {}
        if contactable and not current.portal_contactable:
            updates["portal_contactable"] = 1
        if prefix and not current.weblink_prefix:
            updates["weblink_prefix"] = prefix
        if svg and not current.svg_icon:
            updates["svg_icon"] = svg
        if updates:
            frappe.db.set_value("Communication Channel", channel_name, updates)
    frappe.db.commit()


def seed_mailing_label_formats():
    """Seed common Avery label layouts (ADR 045). Create-only-if-missing; a
    seminary edits these or adds its own measured stock."""
    # name, page, cols, rows, label_w, label_h, margin_top, margin_left, description
    defaults = [
        (
            "Avery 5160",
            "Letter",
            3,
            10,
            66.7,
            25.4,
            12.7,
            4.8,
            _("30 per US Letter sheet, 2.625×1 in"),
        ),
        (
            "Avery 5161",
            "Letter",
            2,
            10,
            101.6,
            25.4,
            12.7,
            4.0,
            _("20 per US Letter sheet, 4×1 in"),
        ),
        (
            "Avery 5163",
            "Letter",
            2,
            5,
            101.6,
            50.8,
            12.7,
            4.8,
            _("10 per US Letter sheet, 4×2 in"),
        ),
        (
            "Avery L7160",
            "A4",
            3,
            7,
            63.5,
            38.1,
            15.1,
            7.0,
            _("21 per A4 sheet, 63.5×38.1 mm"),
        ),
    ]
    for name, page, cols, rows, lw, lh, mt, ml, desc in defaults:
        if frappe.db.exists("Mailing Label Format", name):
            continue
        frappe.get_doc(
            {
                "doctype": "Mailing Label Format",
                "format_name": name,
                "page_size": page,
                "columns": cols,
                "rows": rows,
                "label_width": lw,
                "label_height": lh,
                "margin_top": mt,
                "margin_left": ml,
                "description": desc,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_channel_provider_accounts():
    """Default provider accounts so Email and In-App work out of the box
    (ADR 043). Create-only-if-missing per CHANNEL — if the seminary configured
    any account for a channel (even renamed), we never add another."""
    defaults = [
        ("Default Email", "Email", "frappe-email"),
        ("Portal Inbox", "In-App", "in-app"),
        ("Print Spool", "Print", "print"),
    ]
    for account_name, channel, provider in defaults:
        if not frappe.db.exists("Communication Channel", channel):
            continue
        if frappe.db.exists("Channel Provider Account", {"channel": channel}):
            continue
        frappe.get_doc(
            {
                "doctype": "Channel Provider Account",
                "account_name": account_name,
                "channel": channel,
                "provider": provider,
                "enabled": 1,
                "hourly_limit": 0,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_communication_templates():
    """Seed the Communication Templates the system call sites reference
    (ADR 043/044). Create-only-if-missing by template_key — seminaries edit
    bodies and add language versions on the desk, so a fixture re-import would
    clobber them. Bodies are deliberately NOT gettext-wrapped: per-language
    copy lives in additional Communication Template Version rows, not .po
    files."""
    defaults = [
        {
            "template_key": "waitlist-promoted",
            "category": "Transactional",
            "description": "Student notice: promoted off a course waitlist.",
            "subject": "You're off the waitlist: {{ course }}",
            "body": (
                "<p>Good news — a seat opened in {{ course }} and you've been "
                "moved off the waitlist.{% if awaiting_payment %} A seat invoice "
                "has been issued — please complete payment to keep your seat."
                "{% endif %}</p>"
            ),
        },
        {
            "template_key": "waitlist-promoted-registrar",
            "category": "Transactional",
            "description": "Registrar notice: a student was auto-promoted from a waitlist.",
            "subject": "Waitlist promotion: {{ course }}",
            "body": (
                "<p>{{ student }} was auto-promoted from the waitlist into "
                "{{ course }} (now {{ state }}).</p>"
            ),
        },
        {
            "template_key": "waitlist-closed",
            "category": "Transactional",
            "description": "Student notice: enrollment closed without a seat opening.",
            "subject": "Waitlist closed: {{ course }}",
            "body": (
                "<p>Enrollment for {{ course }} has closed and a seat did not open "
                "before the deadline. Please contact the registrar about "
                "alternatives.</p>"
            ),
        },
        {
            "template_key": "cei-payment-threshold",
            "category": "Transactional",
            "description": "Registrar notice: a Submitted enrollment dropped below the payment threshold.",
            "subject": "Payment threshold dropped: {{ student }}",
            "body": (
                "<p>Payment threshold no longer met for {{ student }} (course "
                "{{ course }}). Now at {{ paid_percent }}%, threshold is "
                "{{ threshold }}%. Review whether to file a Withdrawal Request or "
                "follow up with the student.</p>"
            ),
        },
        {
            "template_key": "late-grades-nag",
            "category": "Transactional",
            "description": "Instructor/registrar nag: final grades are past the grade close date.",
            "subject": "Grades overdue for {{ course }}",
            "body": (
                "<p>Final grades for <b>{{ course }}</b> ({{ term }}) were due on "
                "<b>{{ due }}</b> ({{ days }} day(s) ago) and have not yet been "
                "sent.</p><p>Please enter and finalize all grades, then use "
                "<b>Send Grades</b> to close the course for the term.</p>"
            ),
        },
        {
            "template_key": "few-academic-terms",
            "category": "Transactional",
            "description": "Registrar warning: fewer than two future Academic Terms exist.",
            "subject": "Few Academic Terms",
            "body": (
                "<p>There are only {{ count }} future academic term(s) in the "
                "pipeline. Please create more to avoid disruptions.</p>"
            ),
        },
        {
            "template_key": "recommendation-request",
            "category": "Transactional",
            "description": "External recommender: secure-link request for a recommendation letter.",
            "subject": "Recommendation request for {{ student }}",
            "body": (
                "Dear {{ recommender }},<br><br>{{ student }} has requested a "
                "recommendation letter from you for their seminary program. "
                "Please use the secure link below to submit your letter:<br><br>"
                '<a href="{{ url }}">{{ url }}</a><br><br>'
                "This link expires on {{ expires }}. Thank you."
            ),
        },
    ]
    for tpl in defaults:
        if frappe.db.exists("Communication Template", tpl["template_key"]):
            continue
        frappe.get_doc(
            {
                "doctype": "Communication Template",
                "template_key": tpl["template_key"],
                "category": tpl["category"],
                "description": tpl["description"],
                "enabled": 1,
                "versions": [
                    {
                        "channel": "Email",
                        "subject": tpl["subject"],
                        "body": tpl["body"],
                    }
                ],
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_portal_messaging_rules():
    """Seed the default Portal Messaging Rules on Seminary Settings (ADR 043) so
    the portal Inbox works out of the box: students reach their course
    instructors plus the support user; staff reach the whole roster.

    Seeded once, create-only-if-empty — if a seminary has configured any rule
    we never touch the table. NOT fixtures: a re-import would clobber the
    seminary's desk edits (and child rows) on every migrate.
    """
    if not frappe.db.exists("DocType", "Portal Messaging Rule"):
        return
    settings = frappe.get_single("Seminary Settings")
    if settings.get("portal_messaging_rules"):
        return
    defaults = [
        ("Student", "Course Instructors"),
        ("Student", "Support User"),
        ("Instructor", "All Instructors"),
        ("Instructor", "All Students"),
        ("Seminary Manager", "All Instructors"),
        ("Seminary Manager", "All Students"),
        ("Program Chair", "All Instructors"),
        ("Program Chair", "All Students"),
    ]
    for sender_role, audience in defaults:
        if not frappe.db.exists("Role", sender_role):
            continue
        settings.append(
            "portal_messaging_rules",
            {"enabled": 1, "sender_role": sender_role, "audience": audience},
        )
    settings.flags.ignore_permissions = True
    settings.save()
    frappe.db.commit()


def seed_partner_types():
    """Seed the starter Partner Types if they don't already exist (ADR 053).

    NOT fixtures: partner_type is an open taxonomy seminaries curate on the
    desk, and a fixture re-import would clobber those edits (and the is_active
    toggle) every migrate. Created once, create-only-if-missing. The starter set
    mirrors the partner-flavored Customer Groups already seeded in
    setup_fixtures(). Skipped silently until the doctype exists (install
    ordering)."""
    if not frappe.db.exists("DocType", "Partner Type"):
        return
    defaults = [
        ("Church", _("A local church or congregation.")),
        ("Denomination", _("A denominational or network body of churches.")),
        (
            "Mission Agency",
            _("A sending or field mission organization."),
        ),
        (
            "Para-church Organization",
            _("A ministry working alongside churches (camps, media, relief)."),
        ),
        ("NGO", _("A non-governmental / non-profit organization.")),
    ]
    for type_name, description in defaults:
        if frappe.db.exists("Partner Type", type_name):
            continue
        frappe.get_doc(
            {
                "doctype": "Partner Type",
                "partner_type_name": type_name,
                "is_active": 1,
                "description": description,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_internship_communication():
    """Seed starter internship notification templates + triggers (ADR 044/054).

    Create-only-if-missing; seminaries edit the wording and enable/disable each
    trigger on the desk. Edge-triggered, consent-aware and rate-limited through
    the communication ledger (ADR 043), so they never spam."""
    if not frappe.db.exists("DocType", "Communication Trigger"):
        return

    templates = [
        (
            "internship-accepted",
            "Your internship application was accepted",
            "<p>Good news — your internship application has been accepted. Open "
            "<b>My Internships</b> on your student portal for your placement and next steps.</p>",
        ),
        (
            "internship-rejected",
            "Update on your internship application",
            "<p>Your internship application was not accepted this time. Please speak with "
            "your faculty advisor or the registrar about other opportunities.</p>",
        ),
        (
            "internship-completed",
            "Your internship is complete",
            "<p>Your internship has been marked complete. Thank you for your faithful service.</p>",
        ),
    ]
    for key, subject, body in templates:
        if frappe.db.exists("Communication Template", key):
            continue
        frappe.get_doc(
            {
                "doctype": "Communication Template",
                "template_key": key,
                "category": "Academic",
                "description": _("Internship notice: {0}.").format(key),
                "enabled": 1,
                "versions": [{"channel": "Email", "subject": subject, "body": body}],
            }
        ).insert(ignore_permissions=True)

    triggers = [
        ("Internship Accepted", "Accepted", "internship-accepted"),
        ("Internship Rejected", "Rejected", "internship-rejected"),
        ("Internship Completed", "Completed", "internship-completed"),
    ]
    for name, status_value, template_key in triggers:
        if frappe.db.exists("Communication Trigger", {"trigger_name": name}):
            continue
        if not frappe.db.exists("Communication Template", template_key):
            continue
        frappe.get_doc(
            {
                "doctype": "Communication Trigger",
                "trigger_name": name,
                "reference_doctype": "Internship Application",
                "trigger_on": "Save",
                "enabled": 1,
                "once_per_document": 1,
                "template": template_key,
                "conditions": [
                    {"fieldname": "status", "operator": "Equals", "value": status_value}
                ],
                "recipients": [
                    {"recipient_type": "Document Field", "document_field": "student"}
                ],
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()

    from seminary.seminary.communication_triggers import clear_trigger_cache

    clear_trigger_cache()


def seed_allowed_graduation_documents():
    """Seed the built-in Allowed Graduation Document options (ADR 054).

    The curated picker behind a 'Linked Document' graduation requirement, so staff
    choose from a friendly list instead of every DocType in the system. NOT
    fixtures: seminaries may extend the list on the desk and a re-import would
    clobber those edits. Created once, create-only-if-missing. Skipped silently
    until the doctype exists (install ordering)."""
    if not frappe.db.exists("DocType", "Allowed Graduation Document"):
        return
    defaults = [
        ("Culminating Project", _("Thesis / Culminating Project"), "Completed"),
        ("Recommendation Letter", _("Recommendation Letter"), "Approved"),
        ("Internship Application", _("Internship"), "Completed"),
    ]
    for doctype, label, status in defaults:
        if frappe.db.exists("Allowed Graduation Document", doctype):
            # Ensure the built-in flag is set even if the backfill patch created
            # the row first (it can't know which doctypes are canonical built-ins).
            if not frappe.db.get_value(
                "Allowed Graduation Document", doctype, "built_in"
            ):
                frappe.db.set_value(
                    "Allowed Graduation Document", doctype, "built_in", 1
                )
            continue
        if not frappe.db.exists("DocType", doctype):
            continue
        frappe.get_doc(
            {
                "doctype": "Allowed Graduation Document",
                "document_type": doctype,
                "label": label,
                "fulfilling_status": status,
                "is_active": 1,
                "built_in": 1,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_internship_types():
    """Seed starter Internship Types and their requirement templates if missing (ADR 054).

    NOT fixtures: seminaries configure each type's hours, templates, and faculty
    pool on the desk, and a fixture re-import would clobber those edits every
    migrate. Created once, create-only-if-missing. Skipped silently until the
    doctype exists (install ordering)."""
    if not frappe.db.exists("DocType", "Internship Type"):
        return

    defaults = [
        (
            "Worship Internship",
            200,
            _("A supervised worship-ministry placement in a partner congregation."),
        ),
        (
            "Chaplaincy Internship",
            400,
            _(
                "A supervised chaplaincy placement (hospital, military, or institutional)."
            ),
        ),
    ]
    for type_name, hours, description in defaults:
        if frappe.db.exists("Internship Type", type_name):
            continue
        frappe.get_doc(
            {
                "doctype": "Internship Type",
                "type_name": type_name,
                "is_active": 1,
                "total_hours_required": hours,
                "hours_tracking": "Portal Daily Log with Supervisor Confirmation",
                "evaluation_model": "Pass/Fail",
                "description": description,
            }
        ).insert(ignore_permissions=True)

        # A minimal starter template set, only when this type has none yet.
        if not frappe.db.exists(
            "Internship Requirement Template", {"internship_type": type_name}
        ):
            frappe.get_doc(
                {
                    "doctype": "Internship Requirement Template",
                    "internship_type": type_name,
                    "title": _("Learning Covenant"),
                    "scope": "Application",
                    "sequence": 1,
                    "mandatory": 1,
                    "due_anchor": "Application Date",
                    "due_offset_value": 14,
                    "due_offset_unit": "Days",
                    "student_submits": 1,
                    "student_label": _("Signed learning covenant"),
                    "student_submission_type": "Attachment",
                    "seminary_submits": 0,
                    "seminary_signs_complete": 1,
                    "partner_submits": 0,
                }
            ).insert(ignore_permissions=True)
            frappe.get_doc(
                {
                    "doctype": "Internship Requirement Template",
                    "internship_type": type_name,
                    "title": _("Final Site Evaluation"),
                    "scope": "Placement",
                    "sequence": 2,
                    "mandatory": 1,
                    "due_anchor": "Placement End",
                    "due_offset_value": 7,
                    "due_offset_unit": "Days",
                    "student_submits": 0,
                    "seminary_submits": 0,
                    "partner_submits": 1,
                    "partner_label": _("Completed site evaluation form"),
                    "partner_submission_type": "Attachment",
                    "partner_signs_complete": 1,
                }
            ).insert(ignore_permissions=True)
    frappe.db.commit()


def seed_skill_tags():
    """Seed a starter set of Skill Tags if they don't already exist (ADR 053).

    NOT fixtures: skill_tag is an open taxonomy seminaries curate on the desk
    (and tag onto people / job openings), and a fixture re-import would clobber
    those edits every migrate. Created once, create-only-if-missing. Skipped
    silently until the doctype exists (install ordering)."""
    if not frappe.db.exists("DocType", "Skill Tag"):
        return
    defaults = [
        ("Preaching", "Ministry"),
        ("Teaching", "Ministry"),
        ("Youth Ministry", "Ministry"),
        ("Worship Leading", "Ministry"),
        ("Pastoral Care / Counseling", "Ministry"),
        ("Church Administration", "Administration"),
        ("Bookkeeping / Finance", "Administration"),
        ("Biblical Languages", "Language"),
        ("Cross-cultural Missions", "Missions"),
        ("Discipleship", "Ministry"),
    ]
    for skill_name, category in defaults:
        if frappe.db.exists("Skill Tag", skill_name):
            continue
        frappe.get_doc(
            {
                "doctype": "Skill Tag",
                "skill_name": skill_name,
                "category": category,
                "is_active": 1,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def setup_customer_person_field():
    """Reverse link Customer → Person (ADR 042 addendum): Person.customer
    records the financial party; this mirrors it on the Customer so finance
    views show which human a Customer is. Maintained by person.link_customer."""
    if frappe.db.exists("Custom Field", "Customer-person"):
        return
    frappe.get_doc(
        {
            "doctype": "Custom Field",
            "dt": "Customer",
            "fieldname": "person",
            "fieldtype": "Link",
            "options": "Person",
            "label": "Person",
            "insert_after": "customer_group",
            "read_only": 1,
            "search_index": 1,
        }
    ).insert(ignore_permissions=True)
    frappe.db.commit()


def setup_donor_person_field():
    """Soft link Donor (frappe_giving) <-> Person. frappe_giving is an optional
    app, so these fields are created programmatically only when its Donor
    doctype is present -- re-checked on every migrate, so installing
    frappe_giving later and migrating adds them. Donor.person is the canonical
    FK (set by giving admins); Person.donor is a read-only reverse mirror kept
    in sync by seminary.seminary.integrations.giving. Mirrors the
    Customer<->Person pattern in setup_customer_person_field()."""
    if not frappe.db.exists("DocType", "Donor"):
        return
    if not frappe.db.exists("Custom Field", "Donor-person"):
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": "Donor",
                "fieldname": "person",
                "fieldtype": "Link",
                "options": "Person",
                "label": "Person",
                "insert_after": "customer",
                "search_index": 1,
            }
        ).insert(ignore_permissions=True)
    if not frappe.db.exists("Custom Field", "Person-donor"):
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": "Person",
                "fieldname": "donor",
                "fieldtype": "Link",
                "options": "Donor",
                "label": "Donor",
                "insert_after": "customer",
                "read_only": 1,
                "search_index": 1,
            }
        ).insert(ignore_permissions=True)
    frappe.db.commit()


def create_studentappl_role():
    if not frappe.db.exists("Role", _("Student Applicant")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Student Applicant"), "desk_access": 0}
        ).save()


def create_student_role():
    if not frappe.db.exists("Role", _("Student")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Student"), "desk_access": 0}
        ).save()


def create_alumni_role():
    if not frappe.db.exists("Role", _("Alumni")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Alumni"), "desk_access": 0}
        ).save()


def create_partner_role():
    """Portal role for partner-organization staff (the job-board employer side,
    ADR 053). No desk access; record-level scoping in seminary.partner.permissions
    limits each partner user to their own organization."""
    if not frappe.db.exists("Role", _("Partner")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Partner"), "desk_access": 0}
        ).save()


def setup_sales_invoice_permissions():
    """Grant the Student and Alumni roles read + print access to Sales Invoice.

    Row-level access is scoped to the user's own linked Student record by
    seminary.seminary.sales_invoice_permissions. Idempotent: re-running only
    ensures the read/print flags are set, it never duplicates the rule.
    """
    from frappe.permissions import add_permission, update_permission_property

    if not frappe.db.exists("DocType", "Sales Invoice"):
        return

    for role in (_("Student"), _("Alumni")):
        if not frappe.db.exists("Role", role):
            continue
        add_permission("Sales Invoice", role, 0)
        update_permission_property("Sales Invoice", role, 0, "read", 1)
        update_permission_property("Sales Invoice", role, 0, "print", 1)

    frappe.db.commit()


def create_registrar_role():
    if not frappe.db.exists("Role", _("Registrar")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Registrar"), "desk_access": 1}
        ).save()


def create_instructor_role():
    if not frappe.db.exists("Role", _("Instructor")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Instructor"), "desk_access": 1}
        ).save()


def create_external_examiner_role():
    """Reduced-access role for outside readers/examiners (ADR 059/060). Portal
    gates on this (is_external_examiner) so they reach the CP screens without
    inheriting instructor access. No desk access."""
    if not frappe.db.exists("Role", "External Examiner"):
        frappe.get_doc(
            {"doctype": "Role", "role_name": "External Examiner", "desk_access": 0}
        ).save()


def create_program_chair_role():
    """Broad academic authority over programs & curriculum.

    Replaces the ERPNext-inherited "Academics User" role, which Seminary used as
    its de-facto content-owner role but never created itself. See ADR 030.
    """
    if not frappe.db.exists("Role", _("Program Chair")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Program Chair"), "desk_access": 1}
        ).save()


def create_seminary_manager_role():
    """Module administrator. Previously relied on ERPNext to provide this role."""
    if not frappe.db.exists("Role", _("Seminary Manager")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Seminary Manager"), "desk_access": 1}
        ).save()


def get_custom_fields():
    """Seminary specific custom fields that needs to be added to the Sales Invoice DocType."""
    return {
        "Sales Invoice": [
            {
                "fieldname": "student_info_section",
                "fieldtype": "Section Break",
                "label": _("Student Info"),
                "collapsible": 1,
                "insert_after": "ignore_pricing_rule",
            },
            {
                "fieldname": "student",
                "fieldtype": "Link",
                "label": _("Student"),
                "options": _("Student"),
                "insert_after": "student_info_section",
            },
            {
                "fieldname": "custom_cei",
                "fieldtype": "Link",
                "options": "Course Enrollment Individual",
                "label": _("Course Enrollment Individual"),
                "insert_after": "custom_student",
                "read_only": 1,
            },
        ],
    }


def update_company_in_item_details():
    """
    Update the company in the "Item Default" table to use the default company
    instead of the hardcoded value 'ToBeReplaced' in fixtures.
    """
    # Get the default company
    default_company = frappe.db.get_single_value("Global Defaults", "default_company")
    default_price_list = frappe.db.get_value(
        "Price List", {"selling": 1, "enabled": 1}, "name", order_by="creation asc"
    )
    default_income_account = frappe.db.get_value(
        "Company", {"company_name": default_company}, "default_income_account"
    )
    # Update the company in the "Item Default" table

    items_to_update = frappe.db.sql(
        "SELECT name FROM `tabItem Default` WHERE company = 'ToBeReplaced'"
    )

    if items_to_update:
        frappe.db.sql(
            """
            UPDATE `tabItem Default`
            SET company = %s, default_price_list = %s, income_account = %s
            WHERE company = 'ToBeReplaced'
            """,
            (default_company, default_price_list, default_income_account),
        )

    frappe.db.commit()


def setup_withdrawal_workflow():
    """Create the Course Withdrawal workflow and its dependencies if they don't exist."""
    import json

    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")

    # Create workflow states
    states_path = os.path.join(fixtures_dir, "workflow_state.json")
    if os.path.exists(states_path):
        with open(states_path) as f:
            states = json.load(f)
        for state_data in states:
            if not frappe.db.exists("Workflow State", state_data["name"]):
                doc = frappe.get_doc(state_data)
                doc.insert(ignore_permissions=True)

    # Create workflow actions
    actions_path = os.path.join(fixtures_dir, "workflow_action_master.json")
    if os.path.exists(actions_path):
        with open(actions_path) as f:
            actions = json.load(f)
        for action_data in actions:
            if not frappe.db.exists("Workflow Action Master", action_data["name"]):
                doc = frappe.get_doc(action_data)
                doc.insert(ignore_permissions=True)

    # Create workflow
    if not frappe.db.exists("Workflow", "Course Withdrawal"):
        wf_path = os.path.join(fixtures_dir, "workflow.json")
        if os.path.exists(wf_path):
            with open(wf_path) as f:
                workflows = json.load(f)
            for wf_data in workflows:
                wf_data.pop("creation", None)
                wf_data.pop("modified", None)
                wf_data.pop("modified_by", None)
                doc = frappe.get_doc(wf_data)
                doc.insert(ignore_permissions=True)

    frappe.db.commit()


def after_migrate():
    setup_genders()
    setup_withdrawal_workflow()
    create_alumni_role()
    create_partner_role()
    create_external_examiner_role()
    create_program_chair_role()
    create_seminary_manager_role()
    setup_sales_invoice_permissions()
    seed_fee_categories()
    seed_assessment_criteria()
    seed_course_cancellation_reasons()
    seed_grading_scale()
    seed_faculty_capabilities()
    seed_room_features()
    seed_communication_channels()
    seed_channel_provider_accounts()
    seed_mailing_label_formats()
    seed_communication_templates()
    seed_portal_messaging_rules()
    seed_partner_types()
    seed_skill_tags()
    seed_allowed_graduation_documents()
    seed_internship_types()
    seed_internship_communication()
    setup_customer_person_field()
    setup_donor_person_field()


def setup_genders():
    """Disable non-binary genders. Runs after fixtures are loaded."""

    # Check if our custom "enabled" field exists yet
    if not frappe.db.has_column("Gender", "enabled"):
        return

    # Disable all genders first
    frappe.db.sql("UPDATE `tabGender` SET enabled = 0")

    # Enable only Male and Female
    frappe.db.sql(
        "UPDATE `tabGender` SET enabled = 1 WHERE name IN (%s, %s)",
        (_("Male"), _("Female")),
    )

    frappe.db.commit()
