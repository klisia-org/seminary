"""§4.2 inter-school rows: export a pack on potestas (chair), import it on testable.
Run: cd <scratchpad> && /home/drmrmelo/lms/env/bin/python p0pack.py
"""

import io
import json
import os
import sys
import zipfile

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
from p0check import call, jar, H  # noqa: E402

FX = json.load(open(os.path.join(S, "fx.json")))
CS = FX["CS"]

# --- export on potestas as a Program Chair (not the folder owner)
import requests  # noqa: E402

ZIP = os.path.join(S, "p0pack.zip")
if os.path.exists(ZIP) and os.path.getsize(ZIP) > 1000:

    class _R:  # reuse the pack exported a moment ago
        status_code, headers = 200, {"content-type": "application/zip"}
        content = open(ZIP, "rb").read()
        text = ""

    r = _R()
else:
    r = jar("chair").get(
        f"{H}/api/method/seminary.seminary.course_pack.export.export_course_pack",
        params={"course_schedule": CS},
        allow_redirects=False,
    )
hops = 0
while (
    isinstance(r, requests.Response)
    and r.status_code in (301, 302, 303, 307, 308)
    and hops < 5
):
    loc = r.headers["Location"]
    print("redirect ->", loc[:120])
    if loc.startswith("http") and "localhost" not in loc:
        r = requests.get(
            loc
        )  # presigned object-storage URL: no session, no Host header
    else:
        r = jar("chair").get(
            loc if loc.startswith("http") else f"{H}{loc}", allow_redirects=False
        )
    hops += 1
print(
    "export status:",
    r.status_code,
    "bytes:",
    len(r.content),
    "type:",
    r.headers.get("content-type"),
)
assert r.status_code == 200 and r.content[:2] == b"PK", r.text[:300]
zf = zipfile.ZipFile(io.BytesIO(r.content))
manifest = json.loads(zf.read("manifest.json"))
folders = manifest.get("folders") or {}
print(
    "manifest folders:",
    {
        k: {"scope": v.get("scope"), "files": len(v.get("files") or [])}
        for k, v in folders.items()
    },
)
print(
    "includes_instructor_material:",
    manifest.get("includes_instructor_material"),
    "| warnings:",
    manifest.get("warnings"),
)
scopes = {v.get("scope") for v in folders.values()}
ok_export = (
    ("School" not in scopes)
    and ("Course" in scopes)
    and ("Instructor" in scopes)
    and bool(manifest.get("includes_instructor_material"))
)
print("EXPORT CHECK:", "PASS" if ok_export else "FAIL")
# notice to the owning professor (mluther) on potestas
logs = (
    call(
        "admin",
        "frappe.client.get_list",
        {
            "doctype": "Communication Log",
            "filters": {"to_address": "demo.mluther@seminary.edu"},
            "fields": ["subject", "creation"],
            "order_by": "creation desc",
            "limit_page_length": 2,
        },
    )
    .json()
    .get("message")
    or []
)
print("owner notice:", logs[:1])
open(os.path.join(S, "p0pack.zip"), "wb").write(r.content)

# --- import on testable
import frappe  # noqa: E402

frappe.init(site="testable.localhost", sites_path="/home/drmrmelo/lms/sites")
frappe.connect()
frappe.set_user("Administrator")
db = frappe.db
from seminary.seminary.course_pack.import_ import import_pack_from_bytes  # noqa: E402

term = db.get_value("Academic Term", {}, "name") or db.get_all(
    "Academic Term", pluck="name", limit=1
)
term = term[0] if isinstance(term, list) else term
inst = db.get_all("Instructor", pluck="name", limit=1)
if not inst:
    u = "p0.import.instr@example.org"
    if not db.exists("User", u):
        frappe.get_doc(
            {
                "doctype": "User",
                "email": u,
                "first_name": "P0",
                "roles": [{"role": "Instructor"}],
            }
        ).insert(ignore_permissions=True, ignore_mandatory=True)
    i = frappe.get_doc(
        {"doctype": "Instructor", "instructor_name": "P0 Import Instructor", "user": u}
    )
    i.insert(ignore_permissions=True, ignore_mandatory=True)
    inst = [i.name]
inst = inst[0]
print("testable term:", term, "instructor:", inst)
content = open(os.path.join(S, "p0pack.zip"), "rb").read()


def clean(course_name):
    for cs in db.get_all(
        "Course Schedule", {"course": ["like", course_name + "%"]}, pluck="name"
    ):
        for ch in db.get_all("Course Schedule Chapter", {"coursesc": cs}, pluck="name"):
            db.delete("Course Lesson", {"chapter": ch})
            db.delete("Course Schedule Chapter", ch)
        db.delete("Course Schedule", cs)
    for cf in db.get_all(
        "Course Folder", {"course": ["like", course_name + "%"]}, pluck="name"
    ):
        db.delete("Course Folder", cf)
    course = db.get_value(
        "Course", {"course_name": ["like", course_name + "%"]}, "name"
    )
    if course and db.exists("DocType", "Course Competency"):
        db.delete("Course Competency", {"course": course})
    db.delete("Course", {"course_name": ["like", course_name + "%"]})
    db.commit()


results = {}
for label, kwargs in (("no instructor", {}), ("with instructor", {"instructor": inst})):
    cname = "P0 Imported " + label
    clean(cname)
    try:
        res = import_pack_from_bytes(
            content, "new", course_name=cname, academic_term=term, section="A", **kwargs
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print(label, "IMPORT ERROR:", type(e).__name__, str(e)[:300])
        results[label] = False
        continue
    course = res.get("course") or db.get_value("Course", {"course_name": cname}, "name")
    cfs = db.get_all(
        "Course Folder",
        {"course": course},
        ["name", "foldername", "scope", "instructor"],
    )
    files = db.sql(
        """select f.is_private from tabFile f join `tabCourse Folder` c on f.folder = c.file_reference where c.course = %s and f.is_folder = 0""",
        (course,),
    )
    acts = db.sql(
        """select a.action, a.note from `tabCourse Folder Activity` a join `tabCourse Folder` c on a.parent = c.name where c.course = %s""",
        (course,),
    )
    print(label, "→ warnings:", res.get("warnings"))
    print(label, "→ folders:", [(c.foldername, c.scope, c.instructor) for c in cfs])
    print(
        label,
        "→ files private:",
        [x[0] for x in files],
        "| activity:",
        [a[0] for a in acts],
    )
    expected_scopes = {"Instructor"} if kwargs else {"Course"}
    non_course = [c for c in cfs if c.foldername != "IDX"]
    ok = (
        bool(cfs)
        and all(x[0] == 1 for x in files)
        and all(a[0] == "imported" for a in acts)
        and len(acts) == len(cfs)
        and all(c.scope == "Course" for c in cfs if c.foldername == "IDX")
        and all(c.scope in expected_scopes for c in non_course)
    )
    results[label] = ok
    print(label, "IMPORT CHECK:", "PASS" if ok else "FAIL")

print("\nSUMMARY:", {"export": ok_export, **results})
