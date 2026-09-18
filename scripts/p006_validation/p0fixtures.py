"""Create the potestas fixtures the p006 §4 matrix needs. Idempotent (marker 'P0').
Run:  cd /home/drmrmelo/lms/sites && ../env/bin/python <this file>
"""

import json
import frappe

frappe.init(site="potestas.localhost")
frappe.connect()
frappe.set_user("Administrator")
db = frappe.db

STU_A_USER = "demo.jedwards@seminary.edu"
STU_B_USER = "demo.jcalvin@seminary.edu"
INSTR2 = "INST-00003"  # gwetherby@example.net
INSTR1 = "INST-00013"  # demo.mluther@seminary.edu
CS = "Identity in Christ-2026-2027 (FA27)-A"
COURSE = "Identity in Christ"
OUT = {}


def student(u):
    return db.get_value("Student", {"user": u}, "name") or db.get_value(
        "Student", {"student_email_id": u}, "name"
    )


STU_A, STU_B = student(STU_A_USER), student(STU_B_USER)
OUT["STU_A"], OUT["STU_B"] = STU_A, STU_B


def ensure(doctype, filters, values, submit=False):
    name = db.get_value(doctype, filters)
    if name:
        return name
    doc = frappe.get_doc({"doctype": doctype, **values})
    doc.flags.ignore_permissions = True
    doc.insert(ignore_mandatory=True)
    if submit:
        doc.submit()
    return doc.name


# 1. instructor of CS: make sure mluther (INSTR1) teaches CS so "instr" jar is instructor-of-section
cs = frappe.get_doc("Course Schedule", CS)
if not any(r.instructor == INSTR1 for r in cs.instructor1):
    row = frappe.get_doc(
        {
            "doctype": "Course Schedule Instructors",
            "parent": CS,
            "parenttype": "Course Schedule",
            "parentfield": "instructor1",
            "instructor": INSTR1,
            "idx": len(cs.instructor1) + 1,
        }
    )
    row.flags.ignore_permissions = True
    row.insert()
OUT["CS_instructors"] = [
    r.instructor for r in frappe.get_doc("Course Schedule", CS).instructor1
]

# 2. second section of the same course taught by INSTR2, with STU_B on the roster
CS_B = db.get_value("Course Schedule", {"course": COURSE, "section": "P0B"}, "name")
if not CS_B:
    new = frappe.copy_doc(cs)
    new.section = "P0B"
    new.instructor1 = []
    new.append("instructor1", {"instructor": INSTR2})
    new.chapters = []
    new.published = 1
    new.workflow_state = "Draft"
    new.flags.ignore_permissions = True
    new.insert(ignore_mandatory=True)
    CS_B = new.name
OUT["CS_B"] = CS_B
ensure(
    "Scheduled Course Roster",
    {"course_sc": CS_B, "student": STU_B},
    {"course_sc": CS_B, "student": STU_B, "active": 1},
)
OUT["roster_B_in_CS_B"] = db.get_value(
    "Scheduled Course Roster", {"course_sc": CS_B, "student": STU_B}, "name"
)

# 3. Student Hold on A
stu_a = frappe.get_doc("Student", STU_A)
hold_field = next(
    f.fieldname
    for f in frappe.get_meta("Student").get_table_fields()
    if f.options == "Student Hold"
)
hold = next(
    (
        h
        for h in stu_a.get(hold_field) or []
        if h.is_active and h.hold_type == "Academic"
    ),
    None,
)
if not hold:
    stu_a.append(
        hold_field, {"hold_type": "Academic", "is_active": 1, "reason": "P0 fixture"}
    )
    stu_a.flags.ignore_permissions = True
    stu_a.save()
    hold = [h for h in stu_a.get(hold_field) if h.is_active][-1]
OUT["hold_row"], OUT["hold_field"] = hold.name, hold_field

# 4. Discussion activity + submissions
DA = ensure(
    "Discussion Activity",
    {"discussion_name": "P0 Discussion", "course": COURSE},
    {"discussion_name": "P0 Discussion", "course": COURSE, "title": "P0 Discussion"},
)
OUT["DA"] = DA
OUT["DS_A"] = ensure(
    "Discussion Submission",
    {"disc_activity": DA, "member": STU_A_USER},
    {
        "disc_activity": DA,
        "member": STU_A_USER,
        "original_post": "<p>P0 post A</p>",
        "coursesc": CS,
    },
)
OUT["DS_B"] = ensure(
    "Discussion Submission",
    {"disc_activity": DA, "member": STU_B_USER},
    {
        "disc_activity": DA,
        "member": STU_B_USER,
        "original_post": "<p>P0 post B</p>",
        "coursesc": CS_B,
    },
)

# 5. Assignment activity + submissions
AA = ensure(
    "Assignment Activity",
    {"title": "P0 Assignment", "course": COURSE},
    {"title": "P0 Assignment", "type": "Text", "course": COURSE},
)
OUT["AA"] = AA
OUT["AS_A"] = ensure(
    "Assignment Submission",
    {"assignment": AA, "member": STU_A_USER},
    {
        "assignment": AA,
        "member": STU_A_USER,
        "answer": "<p>P0 answer A</p>",
        "course": CS,
        "status": "Not Graded",
    },
)
OUT["AS_B"] = ensure(
    "Assignment Submission",
    {"assignment": AA, "member": STU_B_USER},
    {
        "assignment": AA,
        "member": STU_B_USER,
        "answer": "<p>P0 answer B</p>",
        "course": CS_B,
        "status": "Not Graded",
    },
)

# 6. Exam activity + draft submissions (with one result row if the child field exists)
EA = ensure(
    "Exam Activity", {"title": "P0 Exam"}, {"title": "P0 Exam", "course": COURSE}
)
OUT["EA"] = EA
meta = frappe.get_meta("Exam Submission")
result_field = next(
    (
        f.fieldname
        for f in meta.get_table_fields()
        if f.options == "Exam Question Result"
    ),
    None,
)
for key, user, sec in (("ES_A", STU_A_USER, CS), ("ES_B", STU_B_USER, CS_B)):
    name = db.get_value("Exam Submission", {"exam": EA, "member": user})
    if not name:
        doc = frappe.get_doc(
            {
                "doctype": "Exam Submission",
                "exam": EA,
                "member": user,
                "course": sec,
                "status": "Not Submitted",
            }
        )
        if result_field:
            doc.append(
                result_field, {"question_name": "P0 Q", "answer": "x", "points": 0}
            )
        doc.flags.ignore_permissions = True
        doc.insert(ignore_mandatory=True)
        name = doc.name
    OUT[key] = name
    if result_field:
        OUT[key + "_row"] = db.get_value(
            "Exam Question Result", {"parent": name}, "name"
        )

# 7. User Input question on the ST quiz
QUIZ = "theological-method-quiz"
Q = db.get_value("Question", {"question": "P0 user input", "type": "User Input"})
if not Q:
    q = frappe.get_doc(
        {
            "doctype": "Question",
            "question": "P0 user input",
            "type": "User Input",
            "course": "DEMO-Systematic Theology I",
            "possibility_1": "alpha",
        }
    )
    q.flags.ignore_permissions = True
    q.insert(ignore_mandatory=True)
    Q = q.name
quiz = frappe.get_doc("Quiz", QUIZ)
qq = next((r for r in quiz.questions if r.question == Q), None)
if not qq:
    quiz.append("questions", {"question": Q, "points": 1})
    quiz.flags.ignore_permissions = True
    quiz.save()
    qq = next(r for r in quiz.questions if r.question == Q)
OUT["QUIZ"], OUT["Q_USER_INPUT"], OUT["QQ_ROW"] = QUIZ, Q, qq.name
OUT["ST_CS_A"] = "DEMO-Systematic Theology I-DEMO-2025-26 (DEMO-Spring26)-A"

# 8. Recommendation letter for A
PE_A = db.get_value("Program Enrollment", {"student": STU_A}, "name")
OUT["PE_A"] = PE_A
OUT["PE_B"] = db.get_value("Program Enrollment", {"student": STU_B}, "name")
OUT["RL_A"] = ensure(
    "Recommendation Letter",
    {"program_enrollment": PE_A, "recommender_email": "p0.rec@example.org"},
    {
        "program_enrollment": PE_A,
        "recommender_name": "P0 Recommender",
        "recommender_email": "p0.rec@example.org",
    },
)

# 9. applicant with access key
app = db.get_value(
    "Student Applicant",
    {"access_key": ["!=", ""]},
    ["name", "access_key"],
    as_dict=True,
)
OUT["APP"], OUT["APP_KEY"] = app.name, app.access_key

# 10. chapter/lesson of CS
OUT["CHAPTER"] = db.get_value("Course Schedule Chapter", {"coursesc": CS}, "name")
OUT["LESSON"] = db.get_value("Course Lesson", {"course_sc": CS}, "name")
OUT["ROSTER_A"] = db.get_value(
    "Scheduled Course Roster", {"course_sc": CS, "student": STU_A}, "name"
)
OUT["CF"] = db.get_value(
    "Course Folder", {"course": COURSE}, ["name", "file_reference"], as_dict=True
)
OUT["CS"], OUT["COURSE"], OUT["CS2_notA"] = (
    CS,
    COURSE,
    "DEMO-Old Testament Survey-DEMO-2024-25 (DEMO-Summer25)-A",
)
OUT["OPEN_CS"] = db.get_value(
    "Course Schedule",
    {"workflow_state": "Open for Enrollment", "name": ["not in", [CS, CS_B]]},
    "name",
)

db.commit()
print(json.dumps(OUT, indent=1, default=str))
