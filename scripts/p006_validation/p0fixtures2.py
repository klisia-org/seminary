"""Second fixture pass for p006 §4.2 folder/template rows. Idempotent. Writes fx.json.
Run:  cd /home/drmrmelo/lms/sites && ../env/bin/python <this file>
"""

import json
import os
import frappe
from frappe.utils.password import update_password

SCRATCH = os.path.dirname(os.path.abspath(__file__))
frappe.init(site="potestas.localhost")
frappe.connect()
frappe.set_user("Administrator")
db = frappe.db

CS = "Identity in Christ-2026-2027 (FA27)-A"
COURSE = "Identity in Christ"
INSTR1 = "INST-00013"  # mluther
OUT = (
    json.load(open(os.path.join(SCRATCH, "fx.json")))
    if os.path.exists(os.path.join(SCRATCH, "fx.json"))
    else {}
)


def ensure(doctype, filters, values):
    name = db.get_value(doctype, filters)
    if name:
        return name
    doc = frappe.get_doc({"doctype": doctype, **values})
    doc.flags.ignore_permissions = True
    doc.insert(ignore_mandatory=True)
    return doc.name


# A. source weights must total 100 for Import Course Template
for row in db.get_all(
    "Scheduled Course Assess Criteria", {"parent": CS}, ["name", "weight_scac"]
):
    if row.weight_scac != 100:
        db.set_value(
            "Scheduled Course Assess Criteria",
            row.name,
            "weight_scac",
            100,
            update_modified=False,
        )

# B. a third, pure Instructor user on CS-A (so "other instructor" negatives have a real login)
U3 = "p0.instr3@example.org"
if not db.exists("User", U3):
    u = frappe.get_doc(
        {
            "doctype": "User",
            "email": U3,
            "first_name": "P0",
            "last_name": "Instructor3",
            "send_welcome_email": 0,
            "roles": [{"role": "Instructor"}],
        }
    )
    u.flags.ignore_permissions = True
    u.insert(ignore_mandatory=True)
update_password(U3, "P0test!2026")
INSTR3 = db.get_value("Instructor", {"user": U3}, "name")
if not INSTR3:
    i = frappe.get_doc(
        {"doctype": "Instructor", "instructor_name": "P0 Instructor3", "user": U3}
    )
    i.flags.ignore_permissions = True
    i.insert(ignore_mandatory=True)
    INSTR3 = i.name
cs = frappe.get_doc("Course Schedule", CS)
if not any(r.instructor == INSTR3 for r in cs.instructor1):
    row = frappe.get_doc(
        {
            "doctype": "Course Schedule Instructors",
            "parent": CS,
            "parenttype": "Course Schedule",
            "parentfield": "instructor1",
            "instructor": INSTR3,
            "idx": len(cs.instructor1) + 1,
        }
    )
    row.flags.ignore_permissions = True
    row.insert()
OUT["INSTR3"], OUT["U3"] = INSTR3, U3

# C. CS_C: same course, taught by INSTR1 only (same-instructor template import target)
CS_C = db.get_value("Course Schedule", {"course": COURSE, "section": "P0C"}, "name")
if not CS_C:
    new = frappe.copy_doc(frappe.get_doc("Course Schedule", CS))
    new.section = "P0C"
    new.instructor1 = []
    new.append("instructor1", {"instructor": INSTR1})
    new.chapters = []
    new.published = 1
    new.workflow_state = "Draft"
    new.flags.ignore_permissions = True
    new.insert(ignore_mandatory=True)
    CS_C = new.name
OUT["CS_C"] = CS_C


# D. scoped folders with one file each
def folder(foldername, **extra):
    name = db.get_value(
        "Course Folder",
        {
            "foldername": foldername,
            **{
                k: v
                for k, v in extra.items()
                if k in ("scope", "course", "course_schedule", "instructor")
            },
        },
        "name",
    )
    if not name:
        doc = frappe.get_doc(
            {"doctype": "Course Folder", "foldername": foldername, **extra}
        )
        doc.flags.ignore_permissions = True
        doc.insert(ignore_mandatory=True)
        name = doc.name
    ref = db.get_value("Course Folder", name, "file_reference")
    if not db.get_value("File", {"folder": ref, "is_folder": 0}, "name"):
        f = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": f"{foldername.replace(' ', '_')}.txt",
                "folder": ref,
                "is_private": 1,
                "content": f"p0 file for {foldername}".encode(),
                "attached_to_doctype": "Course Folder",
                "attached_to_name": name,
            }
        )
        f.flags.ignore_permissions = True
        f.insert()
    return {"name": name, "file_reference": ref}


OUT["F_SECTION_A"] = folder(
    "P0 Section", scope="Section", course=COURSE, course_schedule=CS
)
OUT["F_INSTR1"] = folder(
    "P0 Instructor", scope="Instructor", course=COURSE, instructor=INSTR1
)
OUT["F_SCHOOL1"] = folder("P0 School v1", scope="School")
OUT["F_COURSE"] = {
    "name": db.get_value("Course Folder", {"course": COURSE, "scope": "Course"}, "name")
}
OUT["F_COURSE"]["file_reference"] = db.get_value(
    "Course Folder", OUT["F_COURSE"]["name"], "file_reference"
)

# E. lessons in CS-A's first chapter embedding each folder (EditorJS folder blocks with folder_ref)
chapter = db.get_value("Course Schedule Chapter", {"coursesc": CS}, "name")
for key, label in (
    ("F_SECTION_A", "P0 Section"),
    ("F_INSTR1", "P0 Instructor"),
    ("F_SCHOOL1", "P0 School v1"),
    ("F_COURSE", None),
):
    title = f"P0 lesson {key}"
    lesson = db.get_value(
        "Course Lesson", {"chapter": chapter, "lesson_title": title}, "name"
    )
    fref = OUT[key]["name"]
    content = json.dumps(
        {
            "time": 1,
            "blocks": [
                {"type": "paragraph", "data": {"text": f"Folder test {key}"}},
                {
                    "type": "folder",
                    "data": {
                        "folder_ref": fref,
                        "folder": label
                        or db.get_value("Course Folder", fref, "foldername"),
                    },
                },
            ],
            "version": "2.31.0",
        }
    )
    if not lesson:
        d = frappe.get_doc(
            {
                "doctype": "Course Lesson",
                "chapter": chapter,
                "lesson_title": title,
                "content": content,
            }
        )
        d.flags.ignore_permissions = True
        d.insert(ignore_mandatory=True)
        lesson = d.name
        n = db.count(
            "Course Schedule Lesson Reference",
            {"parent": chapter, "parenttype": "Course Schedule Chapter"},
        )
        ref = frappe.get_doc(
            {
                "doctype": "Course Schedule Lesson Reference",
                "parent": chapter,
                "parenttype": "Course Schedule Chapter",
                "parentfield": "lessons",
                "idx": n + 1,
                "lesson": lesson,
            }
        )
        ref.flags.ignore_permissions = True
        ref.insert()
    else:
        db.set_value("Course Lesson", lesson, "content", content, update_modified=False)
    OUT["LESSON_" + key] = lesson
OUT["CHAPTER"] = chapter

db.commit()
json.dump(OUT, open(os.path.join(SCRATCH, "fx.json"), "w"), indent=1, default=str)
print(
    json.dumps(
        {
            k: OUT[k]
            for k in (
                "INSTR3",
                "U3",
                "CS_C",
                "F_SECTION_A",
                "F_INSTR1",
                "F_SCHOOL1",
                "F_COURSE",
                "CHAPTER",
            )
        },
        indent=1,
    )
)
