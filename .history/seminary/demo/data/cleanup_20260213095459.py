import frappe

DEMO_TAG = "Seminary Demo Data"

# Order matters — delete children before parents

DEMO_DOCTYPES = [
    "Course Enrollment Individual",  # ← first
    "Course Schedule",
    "Program Enrollment",
    "Student",
    "Course",
    "Program",
    "Academic Term",
    "Academic Year",
]

