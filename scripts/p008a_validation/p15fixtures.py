"""p008a fixtures: one section-tier instructor whose Instructor.default_inst_category
is BLANK -- the precondition p005a A01-13 requires. Idempotent.

Run:  cd /home/drmrmelo/lms/sites && ../env/bin/python \
      ../apps/seminary/scripts/p008a_validation/p15fixtures.py
"""

import json
import os
import frappe
from frappe.utils.password import update_password

SITE, PW, EMAIL = "potestas.localhost", "P0test!2026", "p15.sec@example.org"
S = os.path.dirname(os.path.abspath(__file__))
CS = json.load(open(os.path.join(S, "..", "p007_validation", "fx1.json")))["CS"]

frappe.init(site=SITE)
frappe.connect()
frappe.set_user("Administrator")
db = frappe.db
OUT = {"CS": CS, "USER": EMAIL}

if not db.exists("User", EMAIL):
    u = frappe.get_doc(
        {
            "doctype": "User",
            "email": EMAIL,
            "first_name": "Sec",
            "last_name": "Tier",
            "send_welcome_email": 0,
            "user_type": "System User",
        }
    )
    u.flags.ignore_permissions = True
    u.insert()
    u.add_roles("Instructor")
update_password(EMAIL, PW)

INST = db.get_value("Instructor", {"user": EMAIL}, "name")
if not INST:
    d = frappe.get_doc(
        {
            "doctype": "Instructor",
            "instructor_name": "Sec Tier",
            "user": EMAIL,
            "status": "Active",
        }
    )
    d.flags.ignore_permissions = True
    d.insert(ignore_mandatory=True)
    INST = d.name
if not db.get_value("Instructor", INST, "person"):
    from seminary.seminary import person as person_spine

    db.set_value(
        "Instructor",
        INST,
        "person",
        person_spine.ensure_person(email=EMAIL, first_name="Sec", last_name="Tier"),
    )
# The precondition: blank default. Reset every run in case a repro promoted it.
db.set_value("Instructor", INST, "default_inst_category", None)
OUT["INSTRUCTOR"] = INST

cs = frappe.get_doc("Course Schedule", CS)
row = next((r for r in cs.instructor1 if r.instructor == INST), None)
if not row:
    row = frappe.get_doc(
        {
            "doctype": "Course Schedule Instructors",
            "parent": CS,
            "parenttype": "Course Schedule",
            "parentfield": "instructor1",
            "instructor": INST,
            "instructor_category": "Grader",
            "idx": len(cs.instructor1) + 1,
        }
    )
    row.flags.ignore_permissions = True
    row.insert()
else:
    db.set_value(
        "Course Schedule Instructors", row.name, "instructor_category", "Grader"
    )
OUT["ROW"] = row.name

db.commit()
json.dump(OUT, open(os.path.join(S, "fx15.json"), "w"), indent=2)
print(json.dumps(OUT, indent=2))
frappe.destroy()
