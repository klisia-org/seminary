import frappe
import json
import os
from itertools import cycle

DEMO_PREFIX = "DEMO-"
DEMO_TAG = "Seminary Demo Data"

def install_demo_data():
    """Main entry point to install all demo data."""
    if frappe.db.exists("Academic Year", f"{DEMO_PREFIX}2024-25"):
        frappe.log("Demo data already installed, skipping.")
        return

    frappe.flags.in_demo_install = True

    try:
        create_academic_years()
        create_academic_terms()
        create_programs()
        create_courses()
        create_students()
        create_program_enrollments()
        create_course_enrollments()

        # Mark demo as installed
        frappe.db.set_single_value("Seminary Settings", "demo_data_installed", 1)
        frappe.db.commit()
        frappe.msgprint("✅ Seminary demo data installed successfully!", alert=True)

    except Exception:
        frappe.db.rollback()
        frappe.log_error("Demo data installation failed")
        raise
    finally:
        frappe.flags.in_demo_install = False


def load_json(filename):
    """Load data from a JSON file in the data directory."""
    path = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(path, "r") as f:
        return json.load(f)


def insert_demo_doc(doctype, data):
    """Insert a document and tag it as demo data."""
    doc = frappe.get_doc({"doctype": doctype, **data})
    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory = True
    doc.insert()

    # Tag for easy identification and deletion later
    doc.add_tag(DEMO_TAG)

    return doc

def create_academic_years():
    years = load_json("academic_years.json")
    for year in years:
        if not frappe.db.exists("Academic Year", year["academic_year_name"]):
            insert_demo_doc("Academic Year", year)

def create_academic_terms():
    terms = load_json("terms.json")
    for term in terms:
        if not frappe.db.exists("Academic Term", term.get("term_name")):
            insert_demo_doc("Academic Term", term)

def create_programs():
    programs = load_json("programs.json")
    for program in programs:
        if not frappe.db.exists("Program", program["program_name"]):
            insert_demo_doc("Program", program)

def create_courses():
    courses = load_json("courses.json")
    for course in courses:
        if not frappe.db.exists("Course", course["course_name"]):
            insert_demo_doc("Course", course)

def create_students():
    students = load_json("students.json")
    for student_data in students:
        if not frappe.db.exists("Student", {"student_email_id": student_data.get("student_email_id")}):
            doc = insert_demo_doc("Student", student_data)
            # Store generated student ID for enrollment
            student_data["name"] = doc.name

def create_program_enrollments():
    enrollments = load_json("program_enrollments.json")
    for enrollment in enrollments:
        insert_demo_doc("Program Enrollment", enrollment)

def create_course_enrollments():
    enrollments = load_json("course_enrollments.json")
    for enrollment in enrollments:
        insert_demo_doc("Course Enrollment Individual", enrollment)

def create_program_enrollments():
    """
    Create program enrollments by:
    1. Reading students.json to get email identifiers
    2. Looking up actual student records (which have auto-generated names)
    3. Round-robin assigning programs from programs.json
    """
    students_json = load_json("students.json")
    programs_json = load_json("programs.json")

    # Look up actual student records using the email from JSON as the key
    students = []
    for s in students_json:
        student = frappe.db.get_value(
            "Student",
            {"student_email_id": s["student_email_id"]},
            ["name", "student_name"],
            as_dict=True
        )
        if student:
            students.append(student)
        else:
            frappe.log_error(
                f"Demo student not found: {s['student_email_id']}",
                "Demo Data"
            )

    if not students:
        frappe.throw("No demo students found. Install students first.")

    # Look up actual program records
    programs = []
    for p in programs_json:
        program_name = frappe.db.get_value(
            "Program",
            {"program_name": p["name"]},
            "name"
        )
        if program_name:
            programs.append(program_name)
        else:
            frappe.log_error(
                f"Demo program not found: {p['name']}",
                "Demo Data"
            )

    if not programs:
        frappe.throw("No demo programs found. Install programs first.")

    # Round-robin: cycle through programs, one per student
    program_cycle = cycle(programs)

    for student in students:
        program = next(program_cycle)

        # Skip if enrollment already exists
        existing = frappe.db.exists("Program Enrollment", {
            "student": student.name,
            "program": program
        })

        if existing:
            continue

        enrollment = insert_demo_doc("Program Enrollment", {
            "student": student.name,           # e.g. "EDU-STU-2024-00001"
            "student_name": student.student_name,  # e.g. "Jonathan Edwards"
            "program": program,
            "enrollment_date": "2024-08-01",
            "academic_term": "DEMO-Fall24"
        })

        # Program Enrollment is submittable — submit it
        enrollment.submit()

        frappe.logger().info(
            f"Enrolled {student.student_name} ({student.name}) "
            f"in {program}"
        )
