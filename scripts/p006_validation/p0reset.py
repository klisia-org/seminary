"""Return potestas fixtures to the pre-matrix state so p0matrix.py is repeatable."""

import json
import os
import frappe

S = os.path.dirname(os.path.abspath(__file__))
frappe.init(site="potestas.localhost")
frappe.connect()
frappe.set_user("Administrator")
db = frappe.db
FX = json.load(open(os.path.join(S, "fx.json")))


def drop_folder(name):
    ref = db.get_value("Course Folder", name, "file_reference")
    if ref:
        for f in db.get_all("File", {"folder": ref}, pluck="name"):
            db.delete("File", f)
        db.delete("File", ref)
    db.delete("Course Folder Activity", {"parent": name})
    db.delete("Course Folder Share", {"parent": name})
    db.delete("Course Folder Instructor Share", {"parent": name})
    db.delete("Course Folder", name)


# folders touched by the matrix
db.delete("Course Folder Instructor Share", {"parent": FX["F_INSTR1"]["name"]})
for n in db.get_all(
    "Course Folder", {"foldername": ["like", "P0 School v2%"]}, pluck="name"
):
    drop_folder(n)
for n in db.get_all(
    "Course Folder",
    {"scope": "Instructor", "instructor": "INST-00003", "course": FX["COURSE"]},
    pluck="name",
):
    drop_folder(n)
sec = FX["F_SECTION_A"]
db.set_value(
    "Course Folder",
    sec["name"],
    {
        "scope": "Section",
        "course_schedule": FX["CS"],
        "instructor": None,
        "parent_folder": db.get_value("File", sec["file_reference"], "folder"),
    },
    update_modified=False,
)
db.delete(
    "Course Folder Activity",
    {"parent": sec["name"], "action": ["in", ["re-scoped", "referenced", "added"]]},
)
for fname in (
    "p0_sec_instr3.txt",
    "p0_sec_instr2.txt",
    "p0_ins_instr2.txt",
    "p0_ins_instr2b.txt",
    "x.txt",
):
    for f in db.get_all(
        "File",
        {
            "file_name": ["like", fname.split(".")[0] + "%"],
            "folder": ["like", "Home/Course Folders/%"],
        },
        pluck="name",
    ):
        db.delete("File", f)

# template-import artefacts on CS_B / CS_C
for cs in (FX["CS_B"], FX["CS_C"]):
    for ch in db.get_all("Course Schedule Chapter", {"coursesc": cs}, pluck="name"):
        for l in db.get_all("Course Lesson", {"chapter": ch}, pluck="name"):
            db.delete("Course Lesson", l)
        db.delete("Course Schedule Lesson Reference", {"parent": ch})
        db.delete("Course Schedule Chapter", ch)
    db.delete("Course Schedule Chapter Reference", {"parent": cs})
    db.delete("Scheduled Course Assess Criteria", {"parent": cs})
    db.set_value(
        "Course Schedule", cs, "workflow_state", "Draft", update_modified=False
    )
db.delete(
    "Comment",
    {
        "reference_doctype": "Course Schedule",
        "reference_name": ["in", [FX["CS_B"], FX["CS_C"]]],
        "comment_type": "Info",
    },
)
for ch in db.get_all(
    "Course Schedule Chapter",
    {"coursesc": FX["CS"], "chapter_title": "P0 throwaway"},
    pluck="name",
):
    db.delete("Course Schedule Chapter Reference", {"chapter": ch})
    db.delete("Course Schedule Chapter", ch)
db.set_value(
    "Course Schedule Chapter",
    FX["CHAPTER"],
    # p009 S1 dropped `scorm_package_path`; `scorm_package_ref` is the
    # permlevel-1 field the 4.1 row probes now.
    "scorm_package_ref",
    None,
    update_modified=False,
)

# grades / holds / exams / assignments / enrollment / announcements / messages
db.set_value(
    "Student Hold",
    FX["hold_row"],
    {"is_active": 1, "lifted_on": None, "lifted_by": None},
    update_modified=False,
)
for k in ("ES_A", "ES_B"):
    db.delete("Exam Question Result", {"parent": FX[k]})
    db.set_value(
        "Exam Submission",
        FX[k],
        {"status": "Not Submitted", "score": 0, "percentage": 0},
        update_modified=False,
    )
for es in db.get_all(
    "Exam Submission",
    {"exam": FX["EA"], "name": ["not in", [FX["ES_A"], FX["ES_B"]]]},
    pluck="name",
):
    db.delete("Exam Submission", es)
db.set_value(
    "Discussion Submission",
    FX["DS_B"],
    {"grade": 0, "status": "Not Graded"},
    update_modified=False,
)
for k in ("AS_A", "AS_B"):
    db.set_value(
        "Assignment Submission",
        FX[k],
        {"status": "Not Graded", "comments": None},
        update_modified=False,
    )
for a in db.get_all(
    "Assignment Submission",
    {"assignment": FX["AA"], "name": ["not in", [FX["AS_A"], FX["AS_B"]]]},
    pluck="name",
):
    db.delete("Assignment Submission", a)
for cei in db.get_all(
    "Course Enrollment Individual",
    {"program_ce": FX["PE_A"], "coursesc_ce": FX["OPEN_CS"]},
    ["name", "docstatus"],
):
    db.set_value(
        "Course Enrollment Individual", cei.name, "docstatus", 2, update_modified=False
    )
    db.delete("Course Enrollment Individual", cei.name)
db.delete(
    "Scheduled Course Roster", {"course_sc": FX["OPEN_CS"], "student": FX["STU_A"]}
)
for a in db.get_all(
    "Seminary Announcement",
    {"subject": ["like", "%recipient.first_name%"]},
    pluck="name",
):
    db.delete("Seminary Announcement", a)
db.delete("Communication Log", {"subject": "P0"})
for wr in db.get_all(
    "Withdrawal Request",
    {"program_enrollment": FX["PE_B"], "withdrawal_reason": FX.get("WREASON")},
    ["name", "docstatus"],
):
    if wr.docstatus == 1:
        frappe.get_doc("Withdrawal Request", wr.name).cancel()
    db.delete("Withdrawal Request", wr.name)
for qs in db.get_all(
    "Quiz Submission",
    {"quiz": FX["QUIZ"], "member": "demo.jedwards@seminary.edu"},
    pluck="name",
):
    db.delete("Quiz Submission", qs)
db.set_single_value("Seminary Settings", "registrar_academic_records", 1)
db.set_single_value("Seminary Settings", "allow_portal_enroll", 1)
db.commit()
print("reset done")
