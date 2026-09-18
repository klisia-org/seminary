"""Create the potestas fixtures the p007 §4 matrix needs, on top of the p006
ones (run p0fixtures.py and p0fixtures2.py first; reads their fx.json).
Idempotent (marker 'P1'). Writes fx1.json next to this file.

Run:  cd /home/drmrmelo/lms/sites && ../env/bin/python <this file>
"""

import json
import os

import frappe
from frappe.utils.password import update_password

S = os.path.dirname(os.path.abspath(__file__))
FX = json.load(open(os.path.join(S, "..", "p006_validation", "fx.json")))

frappe.init(site="potestas.localhost")
frappe.connect()
frappe.set_user("Administrator")
db = frappe.db
PW = "P0test!2026"
OUT = dict(FX)

CS, CS_B, COURSE = FX["CS"], FX["CS_B"], FX["COURSE"]
ST_CS = FX["ST_CS_A"]
STU_A, STU_B = FX["STU_A"], FX["STU_B"]
OF_RECORD, GRADER = "Instructor of Record", "Grader"


def ensure(doctype, filters, values, submit=False):
    name = db.get_value(doctype, filters)
    if name:
        return name
    doc = frappe.get_doc({"doctype": doctype, **values})
    doc.flags.ignore_permissions = True
    doc.flags.ignore_links = True
    doc.insert(ignore_mandatory=True)
    if submit:
        doc.submit()
    return doc.name


def user(email, first, roles):
    if not db.exists("User", email):
        u = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": first,
                "last_name": "P1",
                "send_welcome_email": 0,
            }
        )
        u.flags.no_welcome_mail = True
        u.insert(ignore_permissions=True)
    u = frappe.get_doc("User", email)
    have = {r.role for r in u.roles}
    for r in roles:
        if r not in have:
            u.add_roles(r)
    update_password(email, PW)
    return email


def instructor(email, name, category):
    inst = db.get_value("Instructor", {"user": email}, "name")
    if not inst:
        doc = frappe.get_doc(
            {
                "doctype": "Instructor",
                "instructor_name": name,
                "user": email,
                "status": "Active",
                "default_inst_category": category,
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert(ignore_mandatory=True)
        inst = doc.name
    else:
        db.set_value("Instructor", inst, "default_inst_category", category)
    return inst


def list_on(cs_name, inst, category):
    cs = frappe.get_doc("Course Schedule", cs_name)
    for r in cs.instructor1:
        if r.instructor == inst:
            if r.instructor_category != category:
                db.set_value(
                    "Course Schedule Instructors",
                    r.name,
                    "instructor_category",
                    category,
                )
            return
    row = frappe.get_doc(
        {
            "doctype": "Course Schedule Instructors",
            "parent": cs_name,
            "parenttype": "Course Schedule",
            "parentfield": "instructor1",
            "instructor": inst,
            "instructor_category": category,
            "idx": len(cs.instructor1) + 1,
        }
    )
    row.flags.ignore_permissions = True
    row.insert()


def unlist(cs_name, inst):
    for r in db.get_all(
        "Course Schedule Instructors",
        {"parent": cs_name, "parenttype": "Course Schedule", "instructor": inst},
        pluck="name",
    ):
        db.delete("Course Schedule Instructors", r)


# 1. Existing instructors become instructors of record by default.
for email in ("demo.mluther@seminary.edu", "gwetherby@example.net", FX["U3"]):
    inst = db.get_value("Instructor", {"user": email}, "name")
    if inst:
        db.set_value("Instructor", inst, "default_inst_category", OF_RECORD)
INSTR3 = FX["INSTR3"]
list_on(CS, INSTR3, OF_RECORD)
INSTR2 = db.get_value("Instructor", {"user": "gwetherby@example.net"}, "name")
list_on(CS_B, INSTR2, OF_RECORD)
OUT["INSTR2"] = INSTR2

# 2. gta: Student + Instructor (Grader), listed on CS, enrolled in CS_B.
GTA_USER = user("p1.gta@example.org", "Gta", ["Student", "Instructor"])
GTA_STU = db.get_value("Student", {"user": GTA_USER}, "name") or db.get_value(
    "Student", {"student_email_id": GTA_USER}, "name"
)
if not GTA_STU:
    doc = frappe.get_doc(
        {
            "doctype": "Student",
            "first_name": "Gta",
            "last_name": "P1",
            "student_email_id": GTA_USER,
            "user": GTA_USER,
            "enabled": 1,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert(ignore_mandatory=True)
    GTA_STU = doc.name
GTA = instructor(GTA_USER, "Gta P1", GRADER)
db.set_value(
    "Instructor", GTA, "owner", GTA_USER, update_modified=False
)  # if_owner row
if not db.get_value("Instructor", GTA, "person"):
    from seminary.seminary import person as person_spine

    db.set_value(
        "Instructor",
        GTA,
        "person",
        person_spine.ensure_person(email=GTA_USER, first_name="Gta", last_name="P1"),
    )
list_on(CS, GTA, GRADER)
unlist(CS_B, GTA)
ensure(
    "Scheduled Course Roster",
    {"course_sc": CS_B, "student": GTA_STU},
    {
        "course_sc": CS_B,
        "student": GTA_STU,
        "stuemail_rc": GTA_USER,
        "stuname_roster": "Gta P1",
        "active": 1,
    },
)
OUT["GTA_USER"], OUT["GTA"], OUT["GTA_STU"] = GTA_USER, GTA, GTA_STU

# 3. instrU: instructor of record, member of the Systematic Theology unit.
#    CS's course sits in Biblical Studies, ST_CS's course in Systematic Theology.
U_USER = user("p1.instru@example.org", "Unit", ["Instructor"])
INSTRU = instructor(U_USER, "Unit P1", OF_RECORD)
person = db.get_value("Instructor", INSTRU, "person")
if not person:
    from seminary.seminary import person as person_spine

    person = person_spine.ensure_person(email=U_USER, first_name="Unit", last_name="P1")
    db.set_value("Instructor", INSTRU, "person", person)
UNIT_A, UNIT_B = "Biblical Studies", "Systematic Theology"
db.set_value("Course", COURSE, "academic_unit", UNIT_A)
ST_COURSE = db.get_value("Course Schedule", ST_CS, "course")
db.set_value("Course", ST_COURSE, "academic_unit", UNIT_B)
ensure(
    "Academic Unit Membership",
    {"person": person, "unit": UNIT_B},
    {"person": person, "unit": UNIT_B, "is_active": 1},
)
unlist(CS, INSTRU)
unlist(ST_CS, INSTRU)
OUT["U_USER"], OUT["INSTRU"], OUT["ST_COURSE"] = U_USER, INSTRU, ST_COURSE
OUT["CS_NO_UNIT"] = db.get_value(
    "Course Schedule",
    {"course": ["not in", [COURSE, ST_COURSE]], "workflow_state": ["!=", "Cancelled"]},
    "name",
)
if OUT["CS_NO_UNIT"]:
    db.set_value(
        "Course",
        db.get_value("Course Schedule", OUT["CS_NO_UNIT"], "course"),
        "academic_unit",
        None,
    )

# 4. A withdrawal request draft for stuA on their CS enrolment; one for stuB.
STU_A_USER, STU_B_USER = "demo.jedwards@seminary.edu", "demo.jcalvin@seminary.edu"


def cei_for(student, cs_name):
    return db.get_value(
        "Course Enrollment Individual",
        {"student_ce": student, "coursesc_ce": cs_name, "docstatus": ["!=", 2]},
        "name",
    )


REASON = db.get_value("Withdrawal Reasons", {}, "name")
for tag, stu, pe in (("A", STU_A, FX["PE_A"]), ("B", STU_B, FX["PE_B"])):
    cei = cei_for(stu, CS if tag == "A" else CS_B)
    OUT["WDR_" + tag] = ensure(
        "Withdrawal Request",
        {"student": stu, "docstatus": 0, "student_comment": "P1 draft"},
        {
            "student": stu,
            "program_enrollment": pe,
            "course_enrollment_individual": cei,
            "withdrawal_scope": "Single Course",
            "withdrawal_reason": REASON,
            "student_comment": "P1 draft",
        },
    )
OUT["CEI_A"] = cei_for(STU_A, CS)
OUT["CEI_B"] = cei_for(STU_B, CS_B) or db.get_value(
    "Course Enrollment Individual",
    {"student_ce": STU_B, "docstatus": ["!=", 2]},
    "name",
)

# 5. Recommendation letter body for stuA's letter; chapel attendance rows.
if FX.get("RL_A"):
    db.set_value(
        "Recommendation Letter",
        FX["RL_A"],
        "letter_body",
        "<p>P1 confidential body</p>",
    )
for tag, stu, pe in (("A", STU_A, FX["PE_A"]), ("B", STU_B, FX["PE_B"])):
    OUT["CHAPEL_" + tag] = ensure(
        "Chapel Attendance",
        {"student": stu, "program_enrollment": pe},
        {"student": stu, "program_enrollment": pe, "status": "Present"},
    )

# 5b. The p006 submissions were inserted by Administrator; a real submission
# is inserted by its student, and the Student write row is `if_owner` (p007
# §2.1), so hand them to their students. Give the exam draft a result row
# so save_exam_comment has a row to comment on.
for key, owner in (
    ("AS_A", STU_A_USER),
    ("DS_A", STU_A_USER),
    ("ES_A", STU_A_USER),
    ("AS_B", STU_B_USER),
    ("DS_B", STU_B_USER),
    ("ES_B", STU_B_USER),
):
    dt = {
        "AS": "Assignment Submission",
        "DS": "Discussion Submission",
        "ES": "Exam Submission",
    }[key[:2]]
    if FX.get(key) and db.exists(dt, FX[key]):
        db.set_value(dt, FX[key], "owner", owner, update_modified=False)
for key in ("ES_A", "ES_B"):
    name = FX.get(key)
    if (
        name
        and db.exists("Exam Submission", name)
        and not db.get_value("Exam Question Result", {"parent": name}, "name")
    ):
        row = frappe.get_doc(
            {
                "doctype": "Exam Question Result",
                "parent": name,
                "parenttype": "Exam Submission",
                "parentfield": "result",
                "question": db.get_value("Exam Question", {"parent": FX["EA"]}, "name"),
                "question_name": "P0 Q",
                "answer": "x",
                "points": 0,
            }
        )
        row.flags.ignore_permissions = True
        row.insert(ignore_mandatory=True)
    # A row created before the question was mandatory cannot be saved: fix it.
    # The p006 exam has no questions at all, so give it one first.
    if name and not db.get_value("Exam Question", {"parent": FX["EA"]}, "name"):
        oq = ensure(
            "Open Question",
            {"question": "<p>P1 open question</p>"},
            {"question": "<p>P1 open question</p>", "question_short": "P1 open"},
        )
        row = frappe.get_doc(
            {
                "doctype": "Exam Question",
                "parent": FX["EA"],
                "parenttype": "Exam Activity",
                "parentfield": "questions",
                "question": oq,
                "question_detail": "<p>P1 open question</p>",
                "points": 1,
            }
        )
        row.flags.ignore_permissions = True
        row.insert(ignore_mandatory=True)
    if name:
        for r in db.get_all(
            "Exam Question Result",
            {"parent": name, "question": ["is", "not set"]},
            pluck="name",
        ):
            db.set_value(
                "Exam Question Result",
                r,
                "question",
                db.get_value("Exam Question", {"parent": FX["EA"]}, "name"),
                update_modified=False,
            )
    OUT[key + "_row"] = (
        db.get_value("Exam Question Result", {"parent": name}, "name") if name else None
    )

# 5c. A private File owned by stuB, attached to nothing: the file-info probe.
PRIV = db.get_value(
    "File",
    {"owner": STU_B_USER, "is_private": 1, "file_name": "p1_private.txt"},
    "file_url",
)
if not PRIV:
    frappe.set_user(STU_B_USER)
    f = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": "p1_private.txt",
            "is_private": 1,
            "content": b"p1 private",
        }
    )
    f.flags.ignore_permissions = True
    f.insert()
    frappe.set_user("Administrator")
    PRIV = f.file_url
OUT["PRIVATE_FILE_B"] = PRIV

# 6. Session users the p006 harness lacks.
for email in (
    STU_A_USER,
    STU_B_USER,
    "enascimento@example.com",
    "tcholmondeley@example.net",
    FX["U3"],
    "gwetherby@example.net",
):
    if db.exists("User", email):
        update_password(email, PW)

# 7. Faculty read scope starts at School.
db.set_single_value("Seminary Settings", "faculty_read_scope", "School")

db.commit()
json.dump(OUT, open(os.path.join(S, "fx1.json"), "w"), indent=1, default=str)
FX.update({k: OUT[k] for k in ("ES_A_row", "ES_B_row") if k in OUT})
json.dump(
    FX,
    open(os.path.join(S, "..", "p006_validation", "fx.json"), "w"),
    indent=1,
    default=str,
)
print(
    json.dumps(
        {
            k: OUT[k]
            for k in (
                "GTA_USER",
                "GTA",
                "U_USER",
                "INSTRU",
                "WDR_A",
                "WDR_B",
                "CEI_A",
                "CHAPEL_A",
                "CS_NO_UNIT",
            )
        },
        indent=1,
        default=str,
    )
)
