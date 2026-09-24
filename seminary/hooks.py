from frappe import _

from . import __version__ as app_version

app_name = "seminary"
app_title = "Seminary"
app_publisher = "Klisia / SeminaryERP"
app_description = "Seminary Management System"
app_icon = "SeminaryERP_tile.png"
app_logo_url = "/assets/seminary/images/SeminaryERP_tile.png"
source_link = "https://github.com/klisia-org/seminary"
app_color = "#0D3049"
app_email = "support@seminaryerp.org"
app_license = "mit"
app_home = "/desk/seminary"

# Seminary runs on the Frappe framework alone. Billing/payments/ERPNext
# integration lives in the optional `oikonomos` bridge app (which depends on
# both seminary and erpnext). Seminary never requires erpnext.
required_apps = []

# Financial backend (oikonomos decoupling). Seminary routes all billing facts /
# side effects through `seminary.seminary.financial.backend.get_financial_backend`,
# which resolves whatever app registers `seminary_financial_backend` (the
# oikonomos bridge does) or falls back to NullFinancialBackend on a Frappe-only
# install. Seminary itself never registers a backend.

# Include app in Apps Screen
# --------------------------
add_to_apps_screen = [
    {
        "name": "seminary",
        "logo": "/assets/seminary/images/SeminaryERP_tile.png",  # Update this path to your custom app's logo
        "title": "Seminary ERP",
        "route": "/desk/seminary",
    }
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = [
    "assets/seminary/css/seminary.css",
    # Styles for the Local Notes panel rendered by seminary_help.js.
    "assets/seminary/css/seminary_help.css",
]
# **The `.bundle.js` suffix is load-bearing, not a naming convention.**
# `bundled_asset()` (frappe/utils/jinja_globals.py) rewrites an entry to its
# content-hashed build output *only* when the name contains `.bundle.`. Any
# other path is emitted verbatim — no hash, no `?v=` — so a browser keeps
# serving whatever it cached, forever, and `bench build` has nothing to bump.
# That is not theoretical: a Desk tab went on calling a whitelisted method for
# hours after the method had been deleted from this app, because it was still
# running the previous day's copy of the address autocomplete.
#
# So: a file listed here is named `*.bundle.js`, lives in `public/js/`, and is
# referenced by bare basename (esbuild picks up every `*.bundle.js` there and
# `assets.json` maps the basename to the hashed URL).
app_include_js = [
    "login_redirect.bundle.js",
    # Address autocomplete, shared by the Person form and the public
    # application form (ADR 068 §7). No API key reaches the browser: the
    # predictions come from our own whitelisted endpoints, so this is inert
    # only when Address Geocoding Settings is disabled.
    "address_autocomplete.bundle.js",
    # The Location surface that sits on top of it — the summary of the last
    # lookup, the on-demand button, and the form wiring — shared by the Person
    # and Partner Organization forms, which differ only in which Link field
    # holds the postal country.
    "geo_location.bundle.js",
    # The tax-ID field's label, mask and shape check, shared by Person, Student
    # Applicant, Partner Organization and the public application form (ADR 071).
    # Country-agnostic: it renders whatever rule `tax_ids.py` hands it, so a new
    # country is one Python entry and no change here.
    "tax_id.bundle.js",
    "seminary_help.bundle.js",
    # Fills a Frappe gap: a DocType's `documentation` link is rendered only in
    # list-view empty-state, never in form view. Adds a form-header Help icon.
    # Registry: docs/frappe-workarounds.md (#5).
    "seminary_doc_link.bundle.js",
    # Guards an upstream Frappe bug: Script Reports with a ref_doctype crash on
    # render when the client meta lacks `masked_fields`.
    # Registry: docs/frappe-workarounds.md (#1); see project_frappe_quirks.md.
    "masked_fields_report_guard.bundle.js",
]
# app_include_js = "/assets/seminary/js/seminary.js"
# app_include_js = "seminary/public/js/global_seminary.js"

# include js, css files in header of web template
# Public website branding (website_brand.css) is injected with an mtime-based
# cache-buster by seminary.overrides.update_website_context — a raw web_include_css
# path gets no ?v= and is cached indefinitely, which breaks color/style updates
# (ADR 061).
# web_include_js = "/assets/seminary/js/seminary.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "seminary/public/scss/website"

# website
update_website_context = ["seminary.overrides.update_website_context"]

website_route_rules = [
    {
        "from_route": "/program",
        "to_route": "Program",
        "defaults": {"my-account-header.title": "Programs"},
    },
    {"from_route": "/seminary", "to_route": "seminary"},
    {"from_route": "/seminary/<path:app_path>", "to_route": "seminary"},
]

# treeviews = ["Assessment Group"]

calendars = [
    "Course Schedule",
]

standard_portal_menu_items = [
    # The "Financials" portal item (references the ERPNext Sales Invoice doctype)
    # is contributed by the oikonomos bridge.
    {
        "title": "Alumni",
        "route": "/seminary/alumni",
        "reference_doctype": "Alumni Profile",
        "role": "Alumni",
    },
]

default_roles = [
    {
        "role": "Student Applicant",
        "doctype": "Student Applicant",
        "email_field": "student_email_id",
    },
    {
        "role": "Alumni",
        "doctype": "Alumni Profile",
        "email_field": "email",
    },
]


global_search_doctypes = {
    "Seminary": [
        {"doctype": "Term Admission", "index": 1},
        {"doctype": "Program", "index": 2},
        {"doctype": "Course", "index": 3},
        {"doctype": "Instructor", "index": 4},
        {"doctype": "Student", "index": 5},
        {"doctype": "Grading Scale", "index": 7},
        {"doctype": "Assessment Criteria", "index": 8},
        {"doctype": "Course Schedule", "index": 9},
        {"doctype": "Student Attendance", "index": 10},
        {"doctype": "Announcement", "index": 11},
        {"doctype": "Student Log", "index": 12},
        {"doctype": "Room", "index": 13},
        {"doctype": "Student Leave Application", "index": 14},
        {"doctype": "Program Enrollment", "index": 15},
        {"doctype": "Course Enrollment Individual", "index": 16},
        {"doctype": "Quiz", "index": 17},
        {"doctype": "Question", "index": 18},
        {"doctype": "Course Activity", "index": 19},
        {"doctype": "Quiz Activity", "index": 20},
        {"doctype": "Academic Term", "index": 21},
        {"doctype": "Academic Year", "index": 22},
        {"doctype": "Withdrawal Request", "index": 23},
        {"doctype": "Alumni Profile", "index": 24},
    ]
}

# fixed route to seminary setup
domains = {
    "Seminary": "seminary.seminary.setup",
}
# include js, css files in header of web form
webform_include_js = {
    "Student Applicant": [
        # Read from disk and inlined into the form's own script, so this one is
        # always current regardless of the bundling above.
        "public/js/address_autocomplete.bundle.js",
        "public/js/tax_id.bundle.js",
        "public/js/student_applicant_webform.js",
    ]
}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# Customer / Item Price form customizations are ERPNext-facing and live in the
# oikonomos bridge (oikonomos/public/js/{customer,item_price}.js).
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role) — works for Website Users only
role_home_page = {
    "Student": "/seminary/courses",
    "Alumni": "/seminary/alumni",
    "Partner": "/seminary/partner",
}

# Authentication hooks
after_login = "seminary.seminary.auth.redirect_student_on_login"


# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
    "methods": [
        "seminary.seminary.utils.get_lesson_count",
        "seminary.seminary.utils.get_instructors",
        "seminary.seminary.utils.get_lesson_index",
        "seminary.seminary.utils.get_lesson_url",
        "seminary.page_renderers.get_profile_url",
        "seminary.seminary.utils.is_instructor",
    ],
    "filters": [],
}

## Markdown Macros for Lessons
seminary_markdown_macro_renderers = {
    "YouTubeVideo": "seminary.plugins.youtube_video_renderer",
    "Video": "seminary.plugins.video_renderer",
    "Embed": "seminary.plugins.embed_renderer",
    "Audio": "seminary.plugins.audio_renderer",
    "PDF": "seminary.plugins.pdf_renderer",
}

# Installation
# ------------

after_install = "seminary.install.after_install"
after_migrate = "seminary.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "seminary.uninstall.before_uninstall"
# after_uninstall = "seminary.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

notification_config = "seminary.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    # Pairs with the `has_permission` below. It was the only unpaired
    # registration of the 41: the second gate applied to opening a plagiarism
    # result and not to listing them (p010 H16, p005a A06-5).
    "Plagiarism Check Result": "seminary.seminary.plagiarism.permissions.get_permission_query_conditions",
    "Instructor": "seminary.seminary.doctype.instructor.instructor.get_permission_query_conditions",
    # p008a G8: the list must not show a folder a per-document read would deny.
    "Course Folder": "seminary.seminary.doctype.course_folder.course_folder.get_permission_query_conditions",
    # Competency assessments and results carry a student's own account of their
    # formation; the list view must not become a way to read a classmate's.
    "Competency Assessment": "seminary.seminary.doctype.competency_assessment.competency_assessment.get_permission_query_conditions",
    "Competency Result": "seminary.seminary.doctype.competency_result.competency_result.get_permission_query_conditions",
    "Personal Development Plan": "seminary.seminary.doctype.personal_development_plan.personal_development_plan.get_permission_query_conditions",
    "Personal Development Note": "seminary.seminary.doctype.personal_development_note.personal_development_note.get_permission_query_conditions",
    "Diploma": "seminary.seminary.doctype.diploma.diploma.get_permission_query_conditions",
    "Communication Log": "seminary.seminary.communication_log_permissions.get_permission_query_conditions",
    "Partner Organization": "seminary.partner.permissions.org_query",
    "Partner Organization Location": "seminary.partner.permissions.location_query",
    "Partner Job Opening": "seminary.partner.permissions.opening_query",
    "Partner Job Application": "seminary.partner.permissions.application_query",
    "Internship Position": "seminary.partner.permissions.internship_position_query",
    "Internship Application": "seminary.partner.permissions.internship_application_query",
    "Internship Placement": "seminary.partner.permissions.internship_placement_query",
    "Internship Hours Log": "seminary.partner.permissions.internship_hours_log_query",
    "Internship Requirement": "seminary.partner.permissions.internship_requirement_query",
    "Internship Supervisor Evaluation": "seminary.partner.permissions.internship_supervisor_evaluation_query",
    "Cohort": "seminary.seminary.discipleship.permissions.cohort_query",
    "Cohort Membership": "seminary.seminary.discipleship.permissions.membership_query",
    "Cohort Post": "seminary.seminary.discipleship.permissions.post_query",
    "Cohort Post Comment": "seminary.seminary.discipleship.permissions.comment_query",
    "Cohort Post Reaction": "seminary.seminary.discipleship.permissions.reaction_query",
    "Cohort Content Flag": "seminary.seminary.discipleship.permissions.flag_query",
    # p007 §2.2 / §2.8: student-keyed rows and instructor tiers, one factory.
    "Student": "seminary.seminary.student_permissions.query_student",
    "Scheduled Course Roster": "seminary.seminary.student_permissions.query_scheduled_course_roster",
    "Course Enrollment Individual": "seminary.seminary.student_permissions.query_course_enrollment_individual",
    "Exam Submission": "seminary.seminary.student_permissions.query_exam_submission",
    "Assignment Submission": "seminary.seminary.student_permissions.query_assignment_submission",
    "Discussion Submission": "seminary.seminary.student_permissions.query_discussion_submission",
    "Quiz Submission": "seminary.seminary.student_permissions.query_quiz_submission",
    "Course Schedule Progress": "seminary.seminary.student_permissions.query_course_schedule_progress",
    "SCORM Attempt": "seminary.seminary.student_permissions.query_scorm_attempt",
    "Withdrawal Request": "seminary.seminary.student_permissions.query_withdrawal_request",
    "Graduation Request": "seminary.seminary.student_permissions.query_graduation_request",
    "Recommendation Letter": "seminary.seminary.student_permissions.query_recommendation_letter",
    "Culminating Project": "seminary.seminary.student_permissions.query_culminating_project",
    "Chapel Attendance": "seminary.seminary.student_permissions.query_chapel_attendance",
    "Course Schedule": "seminary.seminary.student_permissions.query_course_schedule",
    "Course Schedule Chapter": "seminary.seminary.student_permissions.query_course_schedule_chapter",
    "Course Lesson": "seminary.seminary.student_permissions.query_course_lesson",
    "Student Attendance": "seminary.seminary.student_permissions.query_student_attendance",
}
# Instructors can only see their own records
# Students can only see Sales Invoices where custom_student matches their own Student record
# Students can only see their own Diplomas
has_permission = {
    "Instructor": "seminary.seminary.doctype.instructor.instructor.has_permission",
    "Course Folder": "seminary.seminary.doctype.course_folder.course_folder.has_permission",
    "Competency Assessment": "seminary.seminary.doctype.competency_assessment.competency_assessment.has_permission",
    "Competency Result": "seminary.seminary.doctype.competency_result.competency_result.has_permission",
    "Personal Development Plan": "seminary.seminary.doctype.personal_development_plan.personal_development_plan.has_permission",
    "Personal Development Note": "seminary.seminary.doctype.personal_development_note.personal_development_note.has_permission",
    "Diploma": "seminary.seminary.doctype.diploma.diploma.has_permission",
    "Communication Log": "seminary.seminary.communication_log_permissions.has_permission",
    "Plagiarism Check Result": "seminary.seminary.plagiarism.permissions.has_permission",
    "Partner Organization": "seminary.partner.permissions.org_has",
    "Partner Organization Location": "seminary.partner.permissions.location_has",
    "Partner Job Opening": "seminary.partner.permissions.opening_has",
    "Partner Job Application": "seminary.partner.permissions.application_has",
    "Internship Position": "seminary.partner.permissions.internship_position_has",
    "Internship Application": "seminary.partner.permissions.internship_application_has",
    "Internship Placement": "seminary.partner.permissions.internship_placement_has",
    "Internship Hours Log": "seminary.partner.permissions.internship_hours_log_has",
    "Internship Requirement": "seminary.partner.permissions.internship_requirement_has",
    "Internship Supervisor Evaluation": "seminary.partner.permissions.internship_supervisor_evaluation_has",
    "Cohort": "seminary.seminary.discipleship.permissions.cohort_has",
    "Cohort Membership": "seminary.seminary.discipleship.permissions.membership_has",
    "Cohort Post": "seminary.seminary.discipleship.permissions.post_has",
    "Cohort Post Comment": "seminary.seminary.discipleship.permissions.comment_has",
    "Cohort Post Reaction": "seminary.seminary.discipleship.permissions.reaction_has",
    "Cohort Content Flag": "seminary.seminary.discipleship.permissions.flag_has",
    # p007 §2.2 / §2.8
    "Student": "seminary.seminary.student_permissions.has_permission_student",
    "Scheduled Course Roster": "seminary.seminary.student_permissions.has_permission_scheduled_course_roster",
    "Course Enrollment Individual": "seminary.seminary.student_permissions.has_permission_course_enrollment_individual",
    "Exam Submission": "seminary.seminary.student_permissions.has_permission_exam_submission",
    "Assignment Submission": "seminary.seminary.student_permissions.has_permission_assignment_submission",
    "Discussion Submission": "seminary.seminary.student_permissions.has_permission_discussion_submission",
    "Quiz Submission": "seminary.seminary.student_permissions.has_permission_quiz_submission",
    "Course Schedule Progress": "seminary.seminary.student_permissions.has_permission_course_schedule_progress",
    "SCORM Attempt": "seminary.seminary.student_permissions.has_permission_scorm_attempt",
    "Withdrawal Request": "seminary.seminary.student_permissions.has_permission_withdrawal_request",
    "Graduation Request": "seminary.seminary.student_permissions.has_permission_graduation_request",
    "Recommendation Letter": "seminary.seminary.student_permissions.has_permission_recommendation_letter",
    "Culminating Project": "seminary.seminary.student_permissions.has_permission_culminating_project",
    "Chapel Attendance": "seminary.seminary.student_permissions.has_permission_chapel_attendance",
    "Course Schedule": "seminary.seminary.student_permissions.has_permission_course_schedule",
    "Course Schedule Chapter": "seminary.seminary.student_permissions.has_permission_course_schedule_chapter",
    "Course Lesson": "seminary.seminary.student_permissions.has_permission_course_lesson",
    "Student Attendance": "seminary.seminary.student_permissions.has_permission_student_attendance",
}

# DocType Class
# ---------------
# Override standard doctype classes


override_doctype_class = {
    # Payment Request (ERPNext doctype) is overridden by the oikonomos bridge.
    # Frappe gap: webform_include_js is only wired for standard web forms.
    # Frappe workaround — registry: docs/frappe-workarounds.md (#4).
    "Web Form": "seminary.seminary.overrides.web_form.SeminaryWebForm",
    # Frappe gap: there is no read seam for file content — File.get_content()
    # open()s a filesystem path, so an object-storage-backed file cannot be read
    # through any hook. The subclass overrides that one method and delegates to
    # super() for every non-offloaded file, so it is a no-op unless a storage
    # backend is configured. See privatedocs/p004.
    "File": "seminary.storage.overrides.SeminaryFile",
}


# Object storage (privatedocs/p004)
# ---------------------------------
# Large media is offloaded to object storage; everything else stays on disk.
# These are Frappe's only write-side file seams, and both are called with two
# different signatures — seminary.storage.hooks dispatches on the call form and
# delegates every non-offloaded branch to the exact upstream default. With no
# app registering `seminary_storage_backend`, `should_offload` is always False
# and file handling is byte-identical to a stock install.
write_file = "seminary.storage.hooks.write_file"
delete_file_data_content = "seminary.storage.hooks.delete_file_data_content"


# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Academic Term": {
        "on_update": "seminary.tasks.refresh_term_flags_on_save",
    },
    "File": {
        "validate": [
            # Per-role upload caps (privatedocs/p004). Nests *under* Frappe's
            # global max_file_size, which save_file has already enforced.
            "seminary.storage.limits.enforce_upload_limits",
            # Hard size ceiling for in-platform lesson recordings (the client-side
            # length cap can be bypassed). Scoped to recorder output by filename
            # prefix, and tighter still than any role cap.
            "seminary.seminary.lesson_media.enforce_recording_limits",
        ],
    },
    "Course Enrollment Individual": {
        "on_update_after_submit": "seminary.seminary.cei_lifecycle.on_workflow_update",
    },
    # A lesson row inserted on its own (the lesson form, the importers) lands
    # last; a chapter's closing reflection lesson must stay last (ADR 079).
    "Course Schedule Lesson Reference": {
        "after_insert": "seminary.seminary.cbe_reflection.on_lesson_reference_insert",
    },
    # Competency roll-ups (ADR 065). An activity grade feeds the existing
    # gradebook cell, so everything downstream of Course Assess Results Detail
    # keeps working without competency awareness.
    "Activity Competency Grade": {
        "on_update": "seminary.seminary.cbe.on_activity_grade_update",
    },
    "Competency Assessment": {
        "on_update": "seminary.seminary.cbe.on_assessment_update",
    },
    "Program Enrollment": {
        # Payer-row construction (oikonomos.financial.payers.get_payers) is owned
        # by the oikonomos bridge (Program Enrollment before_submit). A Frappe-only
        # seminary just fulfills required enrollments — no billing.
        "on_submit": [
            "seminary.seminary.required_enrollment.fulfill_for_program_enrollment_hook",
        ],
    },
    "Course Schedule": {
        "on_update": "seminary.seminary.required_enrollment.on_course_schedule_update",
        "after_insert": "seminary.seminary.required_enrollment.on_course_schedule_insert",
    },
    "Scheduled Course Assess Criteria": {
        "on_update": "seminary.seminary.api.update_card",
    },
    # before_insert on every submission: content gating (ADR 065) has to refuse
    # the submission itself, not only hide the activity in the outline.
    "Quiz Submission": {
        "before_insert": "seminary.seminary.cbe.assert_activity_unlocked",
        "on_update": "seminary.seminary.api.quizresult_to_card",
    },
    "Assignment Submission": {
        "before_insert": "seminary.seminary.cbe.assert_activity_unlocked",
        "on_update": [
            "seminary.seminary.api.quizresult_to_card",
            "seminary.seminary.plagiarism.service.on_submission_update",
        ],
    },
    "Exam Submission": {
        "before_insert": "seminary.seminary.cbe.assert_activity_unlocked",
        "on_update": "seminary.seminary.api.quizresult_to_card",
    },
    "Discussion Submission": {
        "on_update": "seminary.seminary.api.quizresult_to_card",
        "before_insert": [
            "seminary.seminary.cbe.assert_activity_unlocked",
            "seminary.seminary.api.sanitize_submission",
        ],
        "before_save": "seminary.seminary.api.sanitize_submission",
    },
    "Discussion Submission Replies": {
        "before_insert": "seminary.seminary.api.sanitize_reply",
        "before_save": "seminary.seminary.api.sanitize_reply",
    },
    "Withdrawal Request": {
        "on_update_after_submit": "seminary.seminary.withdrawal.on_withdrawal_workflow_update",
    },
    "Disciplinary Incident": {
        "on_update": "seminary.seminary.disciplinary.on_incident_update",
    },
    "Course Assess Results Detail": {
        "on_update": "seminary.seminary.cs_lifecycle.maybe_advance_to_grading",
    },
    "Scheduled Course Roster": {
        "on_update": "seminary.seminary.cs_lifecycle.maybe_advance_to_grading_from_roster",
    },
    # Billing documents (Sales Invoice, Payment Entry) belong entirely to the
    # financial backend: the bridge (oikonomos) subscribes to them from its own
    # hooks.py and calls seminary's academic advancement entry points
    # (cei_lifecycle.react_to_cei_payment / graduation_request_lifecycle.
    # react_to_gr_payment). Seminary never names an ERPNext billing doctype, so a
    # different backend (e.g. a QBO bridge) could drive the same academic flow.
    "Seminary Settings": {
        "validate": "seminary.seminary.overrides.seminary_settings.validate",
        "on_update": "seminary.seminary.overrides.seminary_settings.on_update",
    },
    # Salary Slip (instructor payroll) is owned by the oikonomos bridge — it
    # subscribes to Salary Slip's lifecycle from its own hooks.py.
    "Graduation Requirement Item": {
        "on_update": "seminary.seminary.graduation.invalidate_linked_doctype_cache",
        "on_trash": "seminary.seminary.graduation.invalidate_linked_doctype_cache",
    },
    # Reflect attendance on a category Event back onto the Student Graduation
    # Requirement snapshot (cohort = fulfil all on Completed; per-student =
    # fulfil those attending). Cheap short-circuit for non-category events.
    "Event": {
        "on_update": "seminary.seminary.events.reflect_event_attendance",
    },
    # Student self check-in: recompute the student's count-based Chapel
    # Attendance graduation requirement(s) on each check-in / removal.
    # (Chapel's own Event mirroring lives in the Chapel controller's lifecycle
    # methods, so it needs no doc_events entry.)
    "Chapel Attendance": {
        "after_insert": "seminary.seminary.chapel.reflect_attendance",
        "on_trash": "seminary.seminary.chapel.reflect_attendance",
    },
    # Recompute the student's per-course attendance standing (absence tally,
    # limit, alert level + once-per-crossing notifications) on every change.
    "Student Attendance": {
        "after_insert": "seminary.seminary.attendance.recompute_for_attendance",
        "on_update": "seminary.seminary.attendance.recompute_for_attendance",
        "on_trash": "seminary.seminary.attendance.recompute_for_attendance",
    },
    # Re-level affected attendance standings when a program's max absence %
    # changes (the Auto per-student limit is derived from it).
    "Program": {
        "on_update": [
            "seminary.seminary.attendance.recompute_on_program_update",
            # A course bound to a competency programme after its sections were
            # created: they get their reflection lessons now (ADR 079).
            "seminary.seminary.cbe_reflection.on_program_update",
        ],
    },
    # Soft integration with frappe_giving (optional app): mirror the canonical
    # Donor.person link onto the read-only Person.donor field. Fires only when a
    # Donor doc is saved, i.e. only when frappe_giving is installed, so the
    # dependency stays one-directional -- giving never imports seminary.
    "Donor": {
        "on_update": "seminary.seminary.integrations.giving.on_donor_update",
        "on_trash": "seminary.seminary.integrations.giving.on_donor_trash",
    },
    # Wildcard hook reflects linked-document status changes back onto the
    # student's graduation requirement snapshot. Cheap short-circuit when the
    # doc's doctype isn't a registered Linked Document target.
    "Academic Unit Membership": {
        "after_delete": "seminary.seminary.file_policy.on_membership_gone",
    },
    "*": {
        # Fills the snapshot fields declared in `person_fields.SNAPSHOTS`
        # (ADR 068 §3) — a person's name as it stood when the record was
        # written, never re-derived afterwards. Hung off the wildcard rather
        # than five controllers so that declaring a new snapshot needs no
        # controller edit; it is an O(1) dict miss for every other doctype.
        "before_validate": [
            "seminary.seminary.person_fields.capture_snapshots",
            # Every rich-text field on every doctype (p008 F6, p005 A05-1b).
            # Frappe's own save-time sanitiser is bypassed for most content --
            # `_sanitize_content` omits `always_sanitize`, and `sanitize_html`
            # returns the value unchanged when BeautifulSoup finds no element --
            # so staff-authored HTML reached the database raw, including
            # `Program.program_description`, which renders on the public site.
            # Measured before it was wired up: of 137 rich values on potestas,
            # 13 change, all of them the same p005a XSS probe losing its
            # smuggled `<!---->`. JSON-in-a-Text-field is skipped by shape.
            "seminary.seminary.content_safety.sanitize_rich_text",
        ],
        # URL scheme allow-list (p008 F7, p005 A05-2 rows 9-10).
        # `frappe.utils.validate_url` accepts `javascript:` unless it is told
        # which schemes are valid, and no caller in this app told it. Typed
        # `Data(options="URL")` fields are picked up automatically; the rest are
        # named in `url_policy.URL_FIELDS`. Only changed values are checked on an
        # existing document, so a value stored before this cannot block an
        # unrelated edit. Measured on potestas first: 0 of 4 stored values
        # would be refused.
        "validate": [
            "seminary.seminary.url_policy.validate_urls",
            # Attach fields (p008 F16, p005a A02-8). Frappe's own attach step
            # takes any *unattached* File matching the URL and binds it to the
            # caller's document with no permission check, so naming a guessed
            # `/private/files/...` was a way to gain read on it through your own
            # record. Refused here, at validate, because that is the only point
            # the association can be refused rather than undone.
            "seminary.seminary.file_policy.guard_attach_fields",
        ],
        "on_update": [
            "seminary.seminary.communication_triggers.process",
            # File privacy (p007 §8.2): keeps registered web images in step
            # with their host and attaches files embedded in lesson content
            # and submissions. Dict misses for every other doctype.
            "seminary.seminary.file_policy.on_host_update",
        ],
        "on_update_after_submit": [
            "seminary.seminary.graduation.reflect_linked_doc_status",
            "seminary.seminary.communication_triggers.process",
        ],
        "on_submit": "seminary.seminary.communication_triggers.process",
        "on_cancel": "seminary.seminary.communication_triggers.process",
    },
}

# Communication channel adapters (ADR 043). Other apps extend this hook with
# {provider_key: "dotted.path.AdapterClass"}; Channel Provider Account rows
# reference the keys.
communication_channel_providers = {
    "frappe-email": "seminary.seminary.comms.EmailAdapter",
    "in-app": "seminary.seminary.comms.InAppAdapter",
    "telegram": "seminary.seminary.telegram_adapter.TelegramAdapter",
    "twilio": "seminary.seminary.twilio_adapter.TwilioAdapter",
    "print": "seminary.seminary.comms.PrintAdapter",
}

# Plagiarism provider adapters. Other apps extend this hook with
# {provider_key: "dotted.path.AdapterClass"}; Plagiarism Provider Account rows
# (external only) reference the keys. internal needs no account.
plagiarism_providers = {
    "internal": "seminary.seminary.plagiarism.internal.InternalPlagiarismAdapter",
    "external-http": "seminary.seminary.plagiarism.external.ExternalHTTPPlagiarismAdapter",
}

# Scheduled Tasks
# ---------------

# Security response headers (p008 F14, p005a A02-9). The app shipped none; what
# protected the site was the bench-generated nginx.conf, which is outside this
# repo, absent under `bench serve` or any other proxy, drops the whole header set
# inside `location` blocks that declare their own, and skips non-2xx/3xx -- so
# every error page was bare. CSP ships **report-only**: set `seminary_csp_enforce`
# in site_config to enforce, once the reports are clean.
# The SCORM delivery origin (privatedocs/p009 §2.2, §2.6). Registered as a page
# renderer rather than a whitelisted method because a package's relative
# references resolve against the DOCUMENT URL, so the URL has to be a real path.
# It renders only on `scorm_delivery_host`, and only for `/scorm/...`.
page_renderer = ["seminary.scorm.delivery.SCORMDelivery"]

# The other half of that split, and the half that makes it real: frappe routes
# on path and ignores `Host`, so without this the whole app would answer on the
# delivery domain. There, only `/scorm/...` exists.
before_request = ["seminary.scorm.delivery.guard_delivery_host"]

after_request = [
    "seminary.seminary.http_headers.apply_security_headers",
    # Every 403/401 that never passed through `guards` -- frappe's own
    # has_permission, a query-condition refusal, a whitelist miss. Before
    # this a successful escalation attempt left no record at all (p010 H1).
    "seminary.seminary.security_log.log_denied_response",
]

scheduler_events = {
    # 	"all": [
    # 		"seminary.tasks.all"
    # 	],
    "cron": {
        # Communication Log drainer (ADR 043): rate-limited per provider account.
        "*/5 * * * *": ["seminary.seminary.comms.dispatch"],
    },
    "daily": [
        "seminary.tasks.daily",
        "seminary.partner.internship.activate_due_placements",
        # Content gating means a student who stops reflecting locks themselves
        # out; nothing else would surface that (ADR 065).
        "seminary.seminary.cbe.notify_stalled_self_assessments",
        # A geocode that failed because the provider was down that afternoon
        # would otherwise stay missing until the address happened to change
        # again (ADR 068 §7). Retries `Failed` only, never `Unresolvable`.
        "seminary.seminary.integrations.geocoding.retry_failed_geocodes",
        # Generated Course Packs are reproducible artifacts, so they expire rather
        # than accumulate one stored copy per export (privatedocs/p004).
        "seminary.seminary.course_pack.export.cleanup_old_packs",
        # An unpack killed between writing its objects and committing its row
        # leaves bytes nobody will ever ask for. A lifecycle rule on the prefix
        # cannot do this one: the prefix is live for packages that ARE claimed,
        # and age alone does not tell them apart (privatedocs/p009 §2.13).
        "seminary.scorm.lifecycle.sweep_orphaned_packages",
        # Course folder download archives are reproducible artifacts keyed by a
        # hash of the folder's contents; superseded ones are retired at build
        # time, and this expires the rest (p008 F17a).
        "seminary.api.folder_archive.cleanup_stale_archives",
        # A direct upload the user abandoned leaves an object no File row will ever
        # reference, and nothing in the database to notice it (privatedocs/p004).
        "seminary.storage.direct.sweep_pending_uploads",
    ],
    "hourly": ["seminary.tasks.hourly"],
    # 	"weekly": [
    # 		"seminary.tasks.weekly"
    # 	],
    # 	"monthly": [
    # 		"seminary.tasks.monthly"
    # 	],
}

# Testing
# -------

# before_tests = "seminary.install.before_tests"

# Overriding Methods
# ------------------------------
#
# Workaround for Frappe v16's workspace localization gap: the workspace title
# and the JSON content blob (header text, card/chart references) are returned
# to the desk untranslated. The wrappers in `seminary.workspace_i18n`
# post-process the responses through `_()`. Remove the two entries below and
# delete `workspace_i18n.py` once upstream wires translation into these paths.
override_whitelisted_methods = {
    # Workspace i18n gap (Frappe v16). Registry: docs/frappe-workarounds.md (#3); ADR 020.
    "frappe.desk.desktop.get_desktop_page": "seminary.workspace_i18n.get_desktop_page",
    "frappe.desk.desktop.get_workspace_sidebar_items": "seminary.workspace_i18n.get_workspace_sidebar_items",
    # Frappe v16 regression: `save_page`'s guard uses AND where it needs OR,
    # so saving any public workspace is a silent no-op (the desk editor hangs
    # and edits vanish on reload). See `seminary.workspace_save_fix`.
    # Frappe workaround — registry: docs/frappe-workarounds.md (#2).
    "frappe.desk.doctype.workspace.workspace.save_page": "seminary.workspace_save_fix.save_page",
}

# Example of original commented-out form retained for reference:
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "seminary.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "seminary.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"seminary.auth.validate"
# ]
# Export and Import Fixtures
# --------------------------
fixtures = [
    # Grading Scale is NOT fixtured: it's submittable and seminaries define their
    # own scales; a re-import would clobber edits. Seeded create-only-if-missing
    # by install.seed_grading_scale() instead.
    # Fee Category is NOT fixtured: its validate_audit() cross-checks each row
    # against Seminary Settings, so a re-import throws once a seminary changes
    # the audit setting or edits a category. Seeded create-only-if-missing by
    # install.seed_fee_categories() instead.
    "Program Level",
    # Instructor Category is NOT fixtured: seeded create-only-if-missing by
    # install.setup_fixtures() so seminary edits to the catalog survive migrate.
    # Assessment Criteria is NOT fixtured: seeded create-only-if-missing by
    # install.seed_assessment_criteria() so seminary edits survive migrate.
    # NOT fixtured: local_notes is per-institution user content; fixturing would
    # clobber it on every migrate (see ADR 049 / feedback on fixtures).
    "Custom HTML Block",
    # Course Cancellation Reason is NOT fixtured: seeded create-only-if-missing
    # by install.seed_course_cancellation_reasons() so seminary edits survive.
    {
        # Seminary Sales Invoice print format is owned by oikonomos.
        "dt": "Print Format",
        "filters": [["name", "in", ["Seminary Diploma"]]],
    },
    {
        "dt": "Workflow",
        "filters": [
            [
                "name",
                "in",
                [
                    "Course Withdrawal",
                    "Recommendation Letter Workflow",
                    "Culminating Project Workflow",
                    "Course Schedule Lifecycle",
                    "Course Enrollment Lifecycle",
                    "Graduation Request Lifecycle",
                    "Program Graduation Requirement Versioning",
                    "Graduation Requirement Item",
                ],
            ]
        ],
    },
    {
        "dt": "Workflow State",
        "filters": [
            [
                "name",
                "in",
                [
                    "Draft",
                    "Submitted",
                    "Academic Review",
                    "Academically Approved",
                    "Financial Review",
                    "Financially Approved",
                    "Completed",
                    "Rejected",
                    "Requested",
                    "Awaiting Response",
                    "Under Review",
                    "Approved",
                    "Resend Required",
                    "Proposal Submitted",
                    "Proposal Approved",
                    "Drafting",
                    "Revisions Required",
                    "Defended",
                    "Open for Enrollment",
                    "Enrollment Closed",
                    "Grading",
                    "Closed",
                    "Cancelled",
                    "Awaiting Payment",
                    "Withdrawn",
                    "Active",
                    "Superseded",
                    "Retired",
                    "Waitlisted",
                    "Unseated",
                    "Suspended",
                    "Ended",
                ],
            ]
        ],
    },
    {
        "dt": "Workflow Action Master",
        "filters": [
            [
                "name",
                "in",
                [
                    "Submit",
                    "Submit & Approve Academically",
                    "Submit & Conclude",
                    "Approve Academically & Conclude",
                    "Send for Academic Review",
                    "Approve Academically",
                    "Send for Financial Review",
                    "Approve Financially",
                    "Complete",
                    "Reject",
                    "Approve",
                    "Mark Awaiting Response",
                    "Mark Submitted",
                    "Send for Review",
                    "Resend Request",
                    "Submit Proposal",
                    "Approve Proposal",
                    "Begin Drafting",
                    "Request Revisions",
                    "Mark Defended",
                    "Open Enrollment",
                    "Close Enrollment",
                    "Cancel Course",
                    "Begin Grading",
                    "Send Grades",
                    "Submit & Skip Academic Review",
                    "Submit & Complete",
                    "Mark as Paid",
                    "Change Version",
                    "Activate",
                    "Send for Final Review",
                    "Return for Revisions",
                    "Withdraw",
                    "Retire",
                    "Reactivate",
                    "Join Waitlist",
                    "Promote",
                    "Release Seat Request",
                    "Grant Directly",
                    "Suspend",
                    "End",
                ],
            ]
        ],
    },
]


# Translation
# --------------------------------

# Make link fields search translated document names for these DocTypes
# Recommended only for DocTypes which have limited documents with untranslated names
# For example: Role, Gender, etc.
# translated_search_doctypes = []
