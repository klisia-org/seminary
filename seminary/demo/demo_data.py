import frappe
import json
import os
from itertools import cycle

DEMO_PREFIX = "DEMO-"
DEMO_TAG = "Seminary Demo Data"

#: The demo faculty member. Held as the *user*, never as an Instructor docname:
#: since ADR 068 §5 an Instructor is named `INST-.#####`, so the old literal
#: ("Martin Luther") is not a docname any more and a Link to it fails.
DEMO_INSTRUCTOR_USER = "demo.mluther@seminary.edu"


def install_demo_data():
    """Main entry point to install all demo data."""
    # The flag, not a hardcoded Academic Year: the calendar is generated from
    # today now, so no year name is stable enough to key on — and the old guard
    # had the opposite failure too, silently skipping a *failed* install that
    # had rolled back and left the flag unset.
    if frappe.db.get_single_value("Seminary Settings", "demo_data_installed"):
        frappe.log("Demo data already installed, skipping.")
        return

    frappe.flags.in_demo_install = True

    try:
        create_academic_years()
        create_academic_terms()
        create_courses()
        create_programs()
        create_users()
        create_students()
        create_instructor_categories()
        create_instructors()
        # Commit so subsequent lookups can find the records
        frappe.db.commit()
        create_program_enrollments()
        create_course_schedules()
        create_course_enrollments()
        activate_current_term()

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


#: Terms within an academic year that starts on 1 August: (label, start month,
#: start day, end month, end day). Contiguous by construction, so every date in
#: the year falls inside exactly one term and `tasks._update_term_flags` always
#: has a term to mark current.
TERM_SHAPE = (
    ("Fall", 8, 1, 12, 31),
    ("Spring", 1, 1, 5, 31),
    ("Summer", 6, 1, 7, 31),
)

#: Academic years to build, relative to the one containing today.
YEAR_OFFSETS = (-1, 0, 1)


def demo_calendar(today=None):
    """The demo's academic years and terms, anchored on today.

    These used to be two JSON files of fixed 2024–2026 dates. A demo whose
    calendar has already ended is not a demo: there is no current term, so
    nothing is open for enrollment, no course schedule is live, and every
    screen that asks "what term is it" answers nothing. It got worse every
    month after the file was written.

    Anchored instead: the academic year runs 1 August to 31 July, and we build
    the previous, current and next one — so the demo always has history to look
    at, a term running now, and a term to register for.
    """
    from frappe.utils import getdate

    # `today` is a parameter so the shape can be tested across a whole year
    # rather than only on the day the suite happens to run.
    today = getdate(today) if today else getdate()
    # Before August, the running academic year is the one that began last year.
    current_start_year = today.year if today.month >= 8 else today.year - 1

    years, terms = [], []
    for offset in YEAR_OFFSETS:
        start_year = current_start_year + offset
        end_year = start_year + 1
        year_name = "DEMO-%d-%02d" % (start_year, end_year % 100)
        years.append(
            {
                "academic_year_name": year_name,
                "year_start_date": "%d-08-01" % start_year,
                "year_end_date": "%d-07-31" % end_year,
            }
        )
        for label, sm, sd, em, ed in TERM_SHAPE:
            # Fall opens the year; Spring and Summer fall in the calendar year
            # after it, which is what makes "Fall26" and "Spring27" siblings.
            term_year = start_year if sm >= 8 else end_year
            terms.append(
                {
                    "academic_year": year_name,
                    "term_name": "DEMO-%s%02d" % (label, term_year % 100),
                    "term_start_date": "%d-%02d-%02d" % (term_year, sm, sd),
                    "term_end_date": "%d-%02d-%02d" % (term_year, em, ed),
                }
            )
    return years, terms


def current_demo_term(today=None):
    """The generated term containing today — the one the demo revolves around."""
    from frappe.utils import getdate

    today = getdate(today) if today else getdate()
    for term in demo_calendar(today)[1]:
        if getdate(term["term_start_date"]) <= today <= getdate(term["term_end_date"]):
            return term
    # Unreachable while TERM_SHAPE stays contiguous, but a silent None here
    # would surface much later as an unenrollable demo.
    frappe.throw("The demo calendar has no term covering today.")


def demo_term_docname(term):
    """Academic Term autonames `{academic_year} ({term_name})`."""
    return "%s (%s)" % (term["academic_year"], term["term_name"])


def create_academic_years():
    years, _terms = demo_calendar()
    for year in years:
        if not frappe.db.exists("Academic Year", year["academic_year_name"]):
            insert_demo_doc("Academic Year", year)


def create_academic_terms():
    _years, terms = demo_calendar()
    for term in terms:
        if not frappe.db.exists("Academic Term", demo_term_docname(term)):
            insert_demo_doc("Academic Term", term)


def create_programs():
    programs = load_json("programs.json")
    for program in programs:
        if not frappe.db.exists("Program", program["program_name"]):
            doc = insert_demo_doc(
                "Program", {**program, "name": program["program_name"]}
            )
            frappe.logger().info(
                f"Created program: '{doc.name}' / '{doc.program_name}'"
            )
            print(f"Created program: '{doc.name}' / '{doc.program_name}'")


def create_courses():
    courses = load_json("courses.json")
    for course in courses:
        if not frappe.db.exists("Course", course["course_name"]):
            insert_demo_doc("Course", course)


def create_users():
    """
    Create user accounts for demo students and instructors.
    Must run BEFORE create_students().
    """
    students_json = load_json("students.json")

    # Student users
    for s in students_json:
        email = s["student_email_id"]

        if frappe.db.exists("User", email):
            continue

        user = insert_demo_doc(
            "User",
            {
                "email": email,
                "first_name": s["first_name"],
                "last_name": s["last_name"],
                "enabled": 1,
                "send_welcome_email": 0,
                "user_type": "Website User",
                "roles": [{"role": "Student"}],
            },
        )

        # Set a default password (won't send email since send_welcome_email=0)
        from frappe.utils.password import update_password

        update_password(email, "Demo@1234")

        frappe.logger().info(f"Created user: {email}")

    # Instructor user (Martin Luther)
    instructor_email = DEMO_INSTRUCTOR_USER
    if not frappe.db.exists("User", instructor_email):
        user = insert_demo_doc(
            "User",
            {
                "email": instructor_email,
                "first_name": "Martin",
                "last_name": "Luther",
                "enabled": 1,
                "send_welcome_email": 0,
                "user_type": "System User",
                "roles": [{"role": "Instructor"}, {"role": "Program Chair"}],
            },
        )

        from frappe.utils.password import update_password

        update_password(instructor_email, "Demo@1234")

        frappe.logger().info(f"Created instructor user: {instructor_email}")


def create_students():
    """Person first, then the Student (ADR 068 §1).

    The demo data used to build Students straight from the JSON, carrying
    names, email, gender and a date of birth. Those are all attributes of the
    human, not of their enrollment: the identity fields are `fetch_from
    person.*` mirrors now and `date_of_birth` no longer exists on Student at
    all, so the demo has to seed the spine and hang the Student off it.
    """
    from seminary.seminary import intake
    from seminary.seminary.person import ensure_person

    students = load_json("students.json")
    for student_data in students:
        email = student_data.get("student_email_id")
        if frappe.db.exists("Student", {"student_email_id": email}):
            continue
        person = ensure_person(
            email,
            first_name=student_data.get("first_name"),
            last_name=student_data.get("last_name"),
            mobile=student_data.get("student_mobile_number"),
            gender=student_data.get("gender"),
            date_of_birth=student_data.get("date_of_birth"),
        )
        doc = intake.make_student(person, user=student_data.get("user"))
        # Store generated student ID for enrollment
        student_data["name"] = doc.name
        # The auto-created Customer (a billing identity) is tagged for cleanup
        # by the oikonomos demo installer — seminary stays Frappe-only here.


def create_instructor_categories():
    categories = [
        {
            "category_name": "Instructor of Record",
            "is_instructor_of_record": 1,
            "description": "Lead instructor responsible for the course.",
        },
    ]
    for cat in categories:
        if not frappe.db.exists("Instructor Category", cat["category_name"]):
            insert_demo_doc("Instructor Category", cat)


def create_instructors():
    """Person first, then the Instructor (ADR 068 §1).

    `instructor_name` is a `fetch_from person.full_name` mirror now, and the
    JSON carried no `prof_email` at all — which was survivable only while the
    controller resolved its own Person from the User.
    """
    from seminary.seminary import intake
    from seminary.seminary.person import ensure_person

    instructors = load_json("instructors.json")
    for instructor_data in instructors:
        user = instructor_data.get("user")
        if frappe.db.exists("Instructor", {"user": user}):
            continue
        name_parts = (instructor_data.get("instructor_name") or "").split(" ", 1)
        person = ensure_person(
            user=user,
            first_name=name_parts[0] or None,
            last_name=name_parts[1] if len(name_parts) > 1 else None,
        )
        intake.make_instructor(
            person,
            user=user,
            shortbio=instructor_data.get("shortbio"),
        )


def demo_instructor():
    """The demo Instructor's docname, resolved rather than written down.

    `Course Schedule Instructors.instructor` is a `reqd` Link, and the demo
    used to hardcode "Martin Luther" — which *was* the docname while Instructor
    autonamed from `instructor_name`. ADR 068 §5 made it opaque, so on any site
    built after that change the literal names nothing and the whole demo
    install fails at the course schedules, after the students and instructors
    are already in. An existing site never noticed: the rename patch moved its
    record, and the demo skips a doctype it has already created.
    """
    name = frappe.db.get_value("Instructor", {"user": DEMO_INSTRUCTOR_USER})
    if not name:
        frappe.throw(
            f"Demo instructor {DEMO_INSTRUCTOR_USER} was not created; "
            "course schedules cannot be scheduled without it."
        )
    return name


def activate_current_term():
    """Leave the demo sitting in a term that is actually running.

    `Academic Term.iscurrent_acterm` is the app-wide answer to "what term is
    it" — `tasks._update_term_flags` is its only writer, and it runs from the
    daily scheduler. Creating terms does not set it, so a freshly installed
    demo has a term covering today and still behaves as though the school were
    between terms, until the scheduler next happens to run. Call the real
    writer rather than setting the flag here, so the demo cannot disagree with
    the rule the rest of the app follows.

    (`Seminary Settings.seminary_keydict` maps `current_academic_year` and
    `current_academic_term` onto fields that do not exist on that doctype, so
    those defaults are always written empty. Pre-existing, and not something to
    paper over from the demo installer.)
    """
    from frappe.utils import getdate

    from seminary.tasks import _update_term_flags

    _update_term_flags(getdate())
    current = frappe.db.get_value("Academic Term", {"iscurrent_acterm": 1}, "name")
    frappe.logger().info(f"Demo current term: {current}")


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
            as_dict=True,
        )
        if student:
            students.append(student)
        else:
            frappe.log_error(
                f"Demo student not found: {s['student_email_id']}", "Demo Data"
            )

    if not students:
        frappe.throw("No demo students found. Install students first.")

    # Look up actual program records
    programs = []
    for p in programs_json:
        print(f"Looking up program: {p['program_name']}")  # Debug log
        program_name = frappe.db.get_value(
            "Program", {"program_name": p["program_name"]}, "name"
        )
        if program_name:
            programs.append(program_name)
        else:
            print(
                f"Program not found with program_name, retrying with slug: {p['program_name']}"
            )  # Debug log
            slug = p["program_name"].lower().replace(" ", "-")
            program_name = frappe.db.get_value("Program", slug, "name")
            if program_name:
                programs.append(program_name)
            else:
                frappe.log_error(
                    f"Demo program not found: {p['program_name']} (tried: {slug})",
                    "Demo Data",
                )

    if not programs:
        frappe.throw("No demo programs found. Install programs first.")

    # Round-robin: cycle through programs, one per student
    program_cycle = cycle(programs)

    # Enrol into the term that is running now, so the demo opens on an active
    # enrollment rather than a historical one.
    term = current_demo_term()

    for student in students:
        program = next(program_cycle)

        # Skip if enrollment already exists
        existing = frappe.db.exists(
            "Program Enrollment", {"student": student.name, "program": program}
        )

        if existing:
            continue

        enrollment = insert_demo_doc(
            "Program Enrollment",
            {
                "student": student.name,  # e.g. "EDU-STU-2024-00001"
                "student_name": student.student_name,  # e.g. "Jonathan Edwards"
                "program": program,
                "enrollment_date": term["term_start_date"],
                "academic_term": demo_term_docname(term),
            },
        )

        # Program Enrollment is submittable — submit it
        enrollment.submit()

        frappe.logger().info(
            f"Enrolled {student.student_name} ({student.name}) " f"in {program}"
        )


def create_course_schedules():
    """
    Create course schedules:
    - 3 courses per term, round-robin from courses.json
    - Fixed instructor, assessment criteria, and modality
    """
    courses_json = load_json("courses.json")
    _years, terms_json = demo_calendar()
    assess_criteria = frappe.db.get_value(
        "Assessment Criteria", "Academic Paper with Online Submission", "name"
    )
    print(f"Assessment Criteria: {assess_criteria}")  # Debug log

    # Look up actual course names from DB
    courses = []
    for c in courses_json:
        course_name = frappe.db.get_value(
            "Course", {"course_name": c["course_name"]}, "name"
        )
        if course_name:
            courses.append(course_name)
        else:
            frappe.log_error(f"Demo course not found: {c['course_name']}", "Demo Data")

    if not courses:
        frappe.throw("No demo courses found. Install courses first.")

    if not terms_json:
        frappe.throw("No demo terms found. Install terms first.")

    # Look up actual term names from DB
    terms = []
    for t in terms_json:
        term = frappe.db.get_value(
            "Academic Term",
            demo_term_docname(t),
            ["name", "term_start_date", "term_end_date"],
            as_dict=True,
        )
        if not term:
            # Fallback: try slugified
            slug = t["term_name"].lower().replace(" ", "-")
            term = frappe.db.get_value(
                "Academic Term",
                slug,
                ["name", "term_start_date", "term_end_date"],
                as_dict=True,
            )
        if term:
            terms.append(term)
        else:
            frappe.log_error(f"Demo term not found: {t['term_name']}", "Demo Data")

    if not terms:
        frappe.throw("No demo terms found in database.")

    # Round-robin: cycle through courses, 3 per term
    course_cycle = cycle(courses)

    for term in terms:
        for _ in range(3):
            course = next(course_cycle)

            # Skip if already exists for this course + term
            if frappe.db.exists(
                "Course Schedule", {"course": course, "academic_term": term.name}
            ):
                continue

            insert_demo_doc(
                "Course Schedule",
                {
                    "course": course,
                    "academic_term": term.name,  # ← from DB
                    "c_datestart": term.term_start_date,  # ← from DB
                    "c_dateend": term.term_end_date,  # ← from DB
                    "section": "A",
                    "modality": "Virtual",
                    "gradesc_cs": "Default Numeric Scale",
                    "published": 1,
                    "courseassescrit_sc": [
                        {
                            "title": "Academic Paper with Online Submission",
                            "assesscriteria_scac": assess_criteria,
                            "weight_scac": 100,
                        }
                    ],
                    "instructor1": [
                        {
                            "instructor": demo_instructor(),
                            "instructor_category": "Instructor of Record",
                            "user": DEMO_INSTRUCTOR_USER,
                        }
                    ],
                },
            )

            frappe.logger().info(f"Scheduled {course} for {term.name}")


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
            as_dict=True,
        )

        if not student:
            frappe.log_error(
                f"Demo student not found: {s['student_email_id']}", "Demo Data"
            )
            continue

        # Find their program enrollment
        program_enrollment = frappe.db.get_value(
            "Program Enrollment",
            {"student": student.name, "docstatus": 1},
            ["name", "program"],
            as_dict=True,
        )

        if not program_enrollment:
            frappe.log_error(
                f"No program enrollment found for {student.student_name}", "Demo Data"
            )
            continue

        # Get courses in this program (from Program Courses child table)
        program_courses = frappe.get_all(
            "Program Course",
            filters={"parent": program_enrollment.program},
            pluck="course",
        )

        if not program_courses:
            frappe.log_error(
                f"No courses found in program {program_enrollment.program}", "Demo Data"
            )
            continue

        # Find Course Schedules that match these program courses
        course_schedules = frappe.get_all(
            "Course Schedule",
            filters={"course": ["in", program_courses]},
            fields=["name", "course"],
            order_by="c_datestart asc",
        )

        # Also check by tag to only get demo ones
        demo_schedules = []
        for cs in course_schedules:
            tags = frappe.get_all(
                "Tag Link",
                filters={
                    "document_type": "Course Schedule",
                    "document_name": cs.name,
                    "tag": DEMO_TAG,
                },
            )
            if tags:
                demo_schedules.append(cs)

        if not demo_schedules:
            # Fallback: get all demo course schedules for these courses
            demo_schedules = get_demo_course_schedules(program_courses)

        # Create one enrollment per matching course schedule
        for cs in demo_schedules:
            if frappe.db.exists(
                "Course Enrollment Individual",
                {"student_ce": student.name, "coursesc_ce": cs.name},
            ):
                continue

            cei = insert_demo_doc(
                "Course Enrollment Individual",
                {
                    "program_ce": program_enrollment.name,
                    "student_ce": student.name,
                    "coursesc_ce": cs.name,
                },
            )
            cei.submit()

        frappe.logger().info(
            f"Course enrollment created for {student.student_name}: "
            f"{len(demo_schedules)} courses"
        )


def get_demo_course_schedules(program_courses):
    """
    Helper: get all demo-tagged Course Schedules for a list of courses.
    """
    tagged_names = frappe.get_all(
        "Tag Link",
        filters={"document_type": "Course Schedule", "tag": DEMO_TAG},
        pluck="document_name",
    )

    if not tagged_names:
        return []

    return frappe.get_all(
        "Course Schedule",
        filters={"name": ["in", tagged_names], "course": ["in", program_courses]},
        fields=["name", "course"],
        order_by="c_datestart asc",
    )
