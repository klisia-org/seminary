from frappe import _

from . import __version__ as app_version

app_name = "seminary"
app_title = "Seminary"
app_publisher = "Klisia / SeminaryERP"
app_description = "Seminary Management System"
app_icon = "klisia_icon.png"
app_logo_url = "/assets/seminary/images/klisia_icon.png"
source_link = "https://github.com/klisia-org/seminary"
app_color = "#0D3049"
app_email = "support@seminaryerp.org"
app_license = "GNU GPL V3"
app_home = "/app/seminary"

required_apps = ["erpnext"]

# Include app in Apps Screen
# --------------------------
add_to_apps_screen = [
    {
        "name": "seminary",
        "logo": "/assets/seminary/images/klisia_icon.png",  # Update this path to your custom app's logo
        "title": "Seminary ERP",
        "route": "/app/seminary",
    }
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "assets/seminary/css/seminary.css"
# app_include_js = "/assets/seminary/js/seminary.js"
app_include_js = "assets/seminary/js/global_seminary.js"

# include js, css files in header of web template
# web_include_css = "/assets/seminary/css/seminary.css"
# web_include_js = "/assets/seminary/js/seminary.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "seminary/public/scss/website"

# website
update_website_context = []

website_generators = ["Student Admission"]

website_route_rules = [
    {"from_route": "/admissions", "to_route": "Student Admission"},
    {
        "from_route": "/program",
        "to_route": "Program",
        "defaults": {"my-account-header.title": "Programs"},
    },
]

# treeviews = ["Assessment Group"]

calendars = [
    "Course Schedule",
]

standard_portal_menu_items = [
    {
        "title": "Admission",
        "route": "/admissions",
        "reference_doctype": "Student Admission",
        "role": "Student Applicant",
    },
    {
        "title": "Financials",
        "route": "/financials",
        "reference_doctype": "Sales Invoice",
        "role": "Student",
        "condition": "frappe.get_all('Sales Invoice', filters={'custom_student': frappe.session.user})",
    },
]

default_roles = [
    {
        "role": "Student Applicant",
        "doctype": "Student Applicant",
        "email_field": "student_email_id",
    },
]


global_search_doctypes = {
    "Seminary": [
        {"doctype": "Student Admission", "index": 1},
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
doctype_js = {"Customer" : "public/js/custom.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

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

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes


# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }


# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Course Enrollment Individual": {
        "on_submit": [
            "seminary.seminary.api.copy_data_to_scheduled_course_roster",
            "seminary.seminary.api.copy_data_to_program_enrollment_course",
        ]
        # ,
        # "on_cancel": "method",
        # "on_trash": "method"
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
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    # 	"all": [
    # 		"seminary.tasks.all"
    # 	],
    "daily": ["seminary.tasks.daily"],
    # 	"hourly": [
    # 		"seminary.tasks.hourly"
    # 	],
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
    "Assessment Criteria",
]


# Translation
# --------------------------------

# Make link fields search translated document names for these DocTypes
# Recommended only for DocTypes which have limited documents with untranslated names
# For example: Role, Gender, etc.
# translated_search_doctypes = []

website_route_rules = [
    {"from_route": "/seminary", "to_route": "seminary"},
    {"from_route": "/seminary/<path:app_path>", "to_route": "seminary"},
]
