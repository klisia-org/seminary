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
app_license = "GNU GPL V3"
app_home = "/desk/seminary"

required_apps = ["erpnext"]

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
app_include_css = "assets/seminary/css/seminary.css"
app_include_js = [
    "assets/seminary/js/login_redirect.js",
    "assets/seminary/js/seminary_help.js",
]
# app_include_js = "/assets/seminary/js/seminary.js"
# app_include_js = "seminary/public/js/global_seminary.js"

# include js, css files in header of web template
# web_include_css = "/assets/seminary/css/seminary.css"
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
    {
        "title": "Financials",
        "route": "/financials",
        "reference_doctype": "Sales Invoice",
        "role": "Student",
        "condition": "frappe.get_all('Sales Invoice', filters={'custom_student': frappe.session.user})",
    },
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
        {"doctype": "Fee Category", "index": 6},
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
        {"doctype": "Course Withdrawal Request", "index": 23},
        {"doctype": "Alumni Profile", "index": 24},
    ]
}

# fixed route to seminary setup
domains = {
    "Seminary": "seminary.seminary.setup",
}
# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Customer": "seminary/public/js/customer.js",
    "Item Price": "seminary/public/js/item_price.js",
}
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
    "Audio": "reminary.plugins.audio_renderer",
    "PDF": "seminary.plugins.pdf_renderer",
}

# Installation
# ------------

before_install = "seminary.install.before_install"
after_install = "seminary.install.after_install"
after_migrate = "seminary.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "seminary.uninstall.before_uninstall"
# after_uninstall = "seminary.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "seminary.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "Instructor": "seminary.seminary.doctype.instructor.instructor.get_permission_query_conditions",
    "Sales Invoice": "seminary.seminary.sales_invoice_permissions.get_permission_query_conditions",
    "Student Balance": "seminary.seminary.doctype.student_balance.student_balance_permissions.get_permission_query_conditions",
    "Diploma": "seminary.seminary.doctype.diploma.diploma.get_permission_query_conditions",
}
# Instructors can only see their own records
# Students can only see Sales Invoices where custom_student matches their own Student record
# Students can only see their own Diplomas
has_permission = {
    "Instructor": "seminary.seminary.doctype.instructor.instructor.has_permission",
    "Sales Invoice": "seminary.seminary.sales_invoice_permissions.has_permission",
    "Student Balance": "seminary.seminary.doctype.student_balance.student_balance_permissions.has_permission",
    "Diploma": "seminary.seminary.doctype.diploma.diploma.has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes


override_doctype_class = {
    "Payment Request": "seminary.seminary.overrides.payment_request.SeminaryPaymentRequest"
}


# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Course Enrollment Individual": {
        "on_update_after_submit": "seminary.seminary.cei_lifecycle.on_workflow_update",
    },
    "Program Enrollment": {
        "on_submit": "seminary.seminary.api.get_payers",
    },
    "Scheduled Course Assess Criteria": {
        "on_update": "seminary.seminary.api.update_card",
    },
    "Quiz Submission": {
        "on_update": "seminary.seminary.api.quizresult_to_card",
    },
    "Assignment Submission": {
        "on_update": "seminary.seminary.api.quizresult_to_card",
    },
    "Exam Submission": {
        "on_update": "seminary.seminary.api.quizresult_to_card",
    },
    "Discussion Submission": {
        "on_update": "seminary.seminary.api.quizresult_to_card",
        "before_insert": "seminary.seminary.api.sanitize_submission",
        "before_save": "seminary.seminary.api.sanitize_submission",
    },
    "Discussion Submission Replies": {
        "before_insert": "seminary.seminary.api.sanitize_reply",
        "before_save": "seminary.seminary.api.sanitize_reply",
    },
    "Course Withdrawal Request": {
        "on_update_after_submit": "seminary.seminary.withdrawal.on_withdrawal_workflow_update",
    },
    "Course Assess Results Detail": {
        "on_update": "seminary.seminary.cs_lifecycle.maybe_advance_to_grading",
    },
    "Scheduled Course Roster": {
        "on_update": "seminary.seminary.cs_lifecycle.maybe_advance_to_grading_from_roster",
    },
    "Student": {
        "after_insert": "seminary.seminary.doctype.student_balance.student_balance.create_student_balance",
    },
    "Sales Invoice": {
        "on_submit": [
            "seminary.seminary.doctype.student_balance.student_balance.add_invoice_to_student_balance",
            "seminary.seminary.cei_lifecycle.maybe_advance_cei_on_payment",
            "seminary.seminary.graduation_request_lifecycle.on_si_submit",
        ],
        "on_update_after_submit": [
            "seminary.seminary.doctype.student_balance.student_balance.refresh_balance_on_invoice_update",
            "seminary.seminary.cei_lifecycle.maybe_advance_cei_on_payment",
            "seminary.seminary.graduation_request_lifecycle.on_si_update_after_submit",
        ],
        "on_cancel": [
            "seminary.seminary.doctype.student_balance.student_balance.remove_cancelled_invoice_from_balance",
            "seminary.seminary.cei_lifecycle.maybe_notify_registrar_on_invoice_cancel",
        ],
    },
    "Payment Entry": {
        "on_submit": [
            "seminary.seminary.cei_lifecycle.on_payment_entry_submit",
            "seminary.seminary.graduation_request_lifecycle.on_payment_entry_submit",
        ],
        "on_cancel": [
            "seminary.seminary.cei_lifecycle.on_payment_entry_cancel",
            "seminary.seminary.graduation_request_lifecycle.on_payment_entry_cancel",
        ],
    },
    "Seminary Settings": {
        "validate": "seminary.seminary.overrides.seminary_settings.validate",
        "on_update": "seminary.seminary.overrides.seminary_settings.on_update",
    },
    "Salary Slip": {
        "before_validate": "seminary.seminary.overrides.salary_slip.populate_instructor_summary",
        "on_submit": "seminary.seminary.overrides.salary_slip.post_submit_instructor_log_payments",
        "on_cancel": "seminary.seminary.overrides.salary_slip.cancel_instructor_log_payments",
    },
    "Graduation Requirement Item": {
        "on_update": "seminary.seminary.graduation.invalidate_linked_doctype_cache",
        "on_trash": "seminary.seminary.graduation.invalidate_linked_doctype_cache",
    },
    # Wildcard hook reflects linked-document status changes back onto the
    # student's graduation requirement snapshot. Cheap short-circuit when the
    # doc's doctype isn't a registered Linked Document target.
    "*": {
        "on_update_after_submit": "seminary.seminary.graduation.reflect_linked_doc_status",
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    # 	"all": [
    # 		"seminary.tasks.all"
    # 	],
    "daily": ["seminary.tasks.daily"],
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
    "Trigger Fee Events",
    "Grading Scale",
    "Item",
    "Payment Term",
    "Payment Terms Template",
    "Fee Category",
    "Program Level",
    "Instructor Category",
    "Assessment Criteria",
    "Custom HTML Block",
    "Seminary Help Entry",
    "Messaging App",
    "Course Cancellation Reason",
    {"dt": "UOM", "filters": [["name", "=", "Fee"]]},
    {
        "dt": "Print Format",
        "filters": [["name", "in", ["Seminary Sales Invoice", "Seminary Diploma"]]],
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
