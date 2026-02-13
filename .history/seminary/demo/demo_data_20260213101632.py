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
        create_courses()
        create_students()
        create_program_enrollments()
        create_course_schedules()
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
            {"program_name": p["program_name"]},
            "name"
        )
        if program_name:
            programs.append(program_name)
        else:
            frappe.log_error(
                f"Demo program not found: {p['program_name']}",
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
            "academic_term": "DEMO-2024-25 (DEMO-Fall24)",
        })

        # Program Enrollment is submittable — submit it
        enrollment.submit()

        frappe.logger().info(
            f"Enrolled {student.student_name} ({student.name}) "
            f"in {program}"
        )

def create_course_schedules():
    """
    Create course schedules:
    - 3 courses per term, round-robin from courses.json
    - Fixed instructor, assessment criteria, and modality
    """
    courses_json = load_json("courses.json")
    terms_json = load_json("terms.json")

    # Look up actual course names from DB
    courses = []
    for c in courses_json:
        course_name = frappe.db.get_value(
            "Course",
            {"course_name": c["course_name"]},
            "name"
        )
        if course_name:
            courses.append(course_name)
        else:
            frappe.log_error(
                f"Demo course not found: {c['course_name']}",
                "Demo Data"
            )

    if not courses:
        frappe.throw("No demo courses found. Install courses first.")

    if not terms_json:
        frappe.throw("No demo terms found. Install terms first.")

    # Round-robin: cycle through courses, 3 per term
    course_cycle = cycle(courses)

    for term in terms_json:
        for _ in range(3):
            course = next(course_cycle)

            # Skip if already exists for this course + term
            if frappe.db.exists("Course Schedule", {
                "course": course,
                "academic_term": term["term_name"]
            }):
                continue

            insert_demo_doc("Course Schedule", {
                "course": course,
                "academic_term": term["term_name"],
                "c_datestart": term["term_start_date"],
                "c_dateend": term["term_end_date"],
                "modality": "Virtual",
                "gradesc_cs": "Default Numeric Scale",
                "published": 1,
                "courseassescrit_sc": [
                    {
                        "title": "Academic Paper with Online Submission",
                        "assesscriteria_scac": "Academic Paper with Online Submission",
                        "weight_scac": 100,
                    }
                ],
                "instructor1": [
                    {
                        "instructor": "Martin Luther",
                        "user": "demo.mluther@seminary.edu",
                    }
                ],
            })

            frappe.logger().info(
                f"Scheduled {course} for {term['term_name']}"
            )

def create_course_enrollments():
    """
    Create Course Enrollment Individual for each student:
    1. Find their Program Enrollment
    2. Get the courses in their program (from Program → Program Courses child table)
    3. Match those courses to existing Course Schedules
    4. Enroll the student in each matching scheduled course
    """
    students_json = load_json("students.json")

    for s in students_json:
        # Look up student record
        student = frappe.db.get_value(
            "Student",
            {"student_email_id": s["student_email_id"]},
            ["name", "student_name"],
            as_dict=True
        )

        if not student:
            frappe.log_error(
                f"Demo student not found: {s['student_email_id']}",
                "Demo Data"
            )
            continue

        # Find their program enrollment
        program_enrollment = frappe.db.get_value(
            "Program Enrollment",
            {
                "student": student.name,
                "docstatus": 1
            },
            ["name", "program"],
            as_dict=True
        )

        if not program_enrollment:
            frappe.log_error(
                f"No program enrollment found for {student.student_name}",
                "Demo Data"
            )
            continue

        # Get courses in this program (from Program Courses child table)
        program_courses = frappe.get_all(
            "Program Course",
            filters={"parent": program_enrollment.program},
            pluck="course"
        )

        if not program_courses:
            frappe.log_error(
                f"No courses found in program {program_enrollment.program}",
                "Demo Data"
            )
            continue

        # Find Course Schedules that match these program courses
        course_schedules = frappe.get_all(
            "Course Schedule",
            filters={
                "course": ["in", program_courses]
            },
            fields=["name", "course"],
            order_by="c_datestart asc"
        )

        # Also check by tag to only get demo ones
        demo_schedules = []
        for cs in course_schedules:
            tags = frappe.get_all(
                "Tag Link",
                filters={
                    "document_type": "Course Schedule",
                    "document_name": cs.name,
                    "tag": DEMO_TAG
                }
            )
            if tags:
                demo_schedules.append(cs)

        if not demo_schedules:
            # Fallback: get all demo course schedules for these courses
            demo_schedules = get_demo_course_schedules(program_courses)

        if not demo_schedules:
            frappe.log_error(
                f"No demo course schedules found for {student.student_name}'s program courses",
                "Demo Data"
            )
            continue

        # Build child table rows — one row per matching course schedule
        coursesc_ce = [
            {"coursesc_ce": cs.name}
            for cs in demo_schedules
        ]

        # Skip if enrollment already exists
        if frappe.db.exists("Course Enrollment Individual", {
            "student_ce": student.name,
            "program_ce": program_enrollment.name
        }):
            continue

        insert_demo_doc("Course Enrollment Individual", {
            "program_ce": program_enrollment.name,
            "student_ce": student.name,
            "coursesc_ce": coursesc_ce,
        })

        frappe.logger().info(
            f"Course enrollment created for {student.student_name}: "
            f"{len(coursesc_ce)} courses"
        )


def get_demo_course_schedules(program_courses):
    """
    Helper: get all demo-tagged Course Schedules for a list of courses.
    """
    tagged_names = frappe.get_all(
        "Tag Link",
        filters={
            "document_type": "Course Schedule",
            "tag": DEMO_TAG
        },
        pluck="document_name"
    )

    if not tagged_names:
        return []

    return frappe.get_all(
        "Course Schedule",
        filters={
            "name": ["in", tagged_names],
            "course": ["in", program_courses]
        },
        fields=["name", "course"],
        order_by="c_datestart asc"
    )