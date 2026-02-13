import frappe
import json
import os
import random

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

def generate_program_enrollments():
    """
    Generate program enrollments by linking students to programs.
    Each student is enrolled in one program, and all programs have at least one student.
    """
    # Load students and programs data
    with open("/home/drmrmelo/lms/apps/seminary/seminary/demo/data/students.json", "r") as students_file:
        students = json.load(students_file)

    with open("/home/drmrmelo/lms/apps/seminary/seminary/demo/data/programs.json", "r") as programs_file:
        programs = json.load(programs_file)

    # Shuffle students to ensure random distribution
    random.shuffle(students)

    # Distribute students across programs
    enrollments = []
    program_count = len(programs)

    for i, student in enumerate(students):
        program = programs[i % program_count]  # Assign students to programs in a round-robin fashion
        enrollment = {
            "student": student["user"],
            "program": program["program_name"],
            "enrollment_date": "2024-08-01"
        }
        enrollments.append(enrollment)

    # Save enrollments to a new JSON file
    with open("/home/drmrmelo/lms/apps/seminary/seminary/demo/data/program_enrollments.json", "w") as enrollments_file:
        json.dump(enrollments, enrollments_file, indent=4)

    print("Program enrollments generated successfully.")

# Call the function to generate enrollments
generate_program_enrollments()