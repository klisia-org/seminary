#!/usr/bin/env python3
"""Re-grant roles in non-permission Seminary config JSON (ADR 030).

Covers role references that live outside doctype `permissions` blocks: workflow
fixtures (transition `allowed` / state `allow_edit`), Report `roles`, Page
`roles`, Dashboard Chart and Module Onboarding `roles`.

Default action is the universal rename "Academics User" -> "Program Chair".
By-function overrides move records-lifecycle items to Registrar instead, and
add Registrar to records-oriented reports it was forgotten on. Idempotent.
"""

import glob
import json
import os

PC = "Program Chair"
REG = "Registrar"


def load(p):
    return json.loads(open(p).read())


def dump(p, d):
    open(p, "w").write(json.dumps(d, indent=1, sort_keys=True))


# --- Workflows: doctype -> role the former "Academics User" should become ----
# Records-lifecycle workflows are driven by the Registrar; academic ones by the
# Program Chair.
WORKFLOW_TARGET = {
    "Course Withdrawal Request": REG,
    "Course Enrollment Individual": REG,
    "Graduation Request": REG,
    "Recommendation Letter": PC,
    "Culminating Project": PC,
    "Course Schedule": PC,
    "Program Graduation Requirement": PC,
    "Graduation Requirement Item": PC,
}


def fix_workflows(path="seminary/fixtures/workflow.json"):
    wf = load(path)
    for w in wf:
        tgt = WORKFLOW_TARGET.get(w.get("document_type"), PC)
        for t in w.get("transitions", []):
            if t.get("allowed") == "Academics User":
                t["allowed"] = tgt
        for s in w.get("states", []):
            if s.get("allow_edit") == "Academics User":
                s["allow_edit"] = tgt
    dump(path, wf)
    print(
        f"workflow.json: mapped per-doctype -> {sorted(set(WORKFLOW_TARGET.values()))}"
    )


# --- Reports: rename + add Registrar where records-oriented & forgotten -------
REPORT_ADD_REGISTRAR = {
    "Absent Student Report",
    "Active students that passed each course",
    "Credits passed per student",
    "Student Monthly Attendance Sheet",
    "Student PE total balance",
    "Student Program Progress",
    "Time-to-Graduate Risk",
}


def fix_reports():
    for jf in sorted(glob.glob("seminary/seminary/report/*/*.json")):
        d = load(jf)
        if d.get("doctype") != "Report":
            continue
        roles = d.get("roles", [])
        if not any(r.get("role") == "Academics User" for r in roles):
            continue
        for r in roles:
            if r.get("role") == "Academics User":
                r["role"] = PC
        if d.get("name") in REPORT_ADD_REGISTRAR and not any(
            r.get("role") == REG for r in roles
        ):
            roles.append({"role": REG})
        d["roles"] = roles
        dump(jf, d)
        print(f"report {d.get('name')}: {[r.get('role') for r in roles]}")


# --- Pages / dashboards / onboarding: rename, with registrar_hub -> Registrar -
PAGE_TARGET = {"registrar_hub": REG}


def fix_simple(pattern, doctype, target_by_name=None):
    target_by_name = target_by_name or {}
    for jf in sorted(glob.glob(pattern)):
        d = load(jf)
        if d.get("doctype") != doctype:
            continue
        roles = d.get("roles", [])
        if not any(r.get("role") == "Academics User" for r in roles):
            continue
        name = os.path.basename(jf)[:-5]
        tgt = target_by_name.get(name, PC)
        for r in roles:
            if r.get("role") == "Academics User":
                r["role"] = tgt
        dump(jf, d)
        print(f"{doctype} {name}: {[r.get('role') for r in roles]}")


def main():
    fix_workflows()
    fix_reports()
    fix_simple("seminary/seminary/page/*/*.json", "Page", PAGE_TARGET)
    fix_simple("seminary/seminary/dashboard_chart/*/*.json", "Dashboard Chart")
    fix_simple("seminary/seminary/module_onboarding/*/*.json", "Module Onboarding")


if __name__ == "__main__":
    main()
