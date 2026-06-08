#!/usr/bin/env python3
"""One-shot maintenance script: re-grant Seminary doctype permissions.

Applies the role cleanup from ADR 030 to the doctype JSON source of truth:

  1. Universal rename  "Academics User" -> "Program Chair"  (every permlevel).
  2. Fix forgotten System-Manager-only doctypes.
  3. Records-lifecycle: add the forgotten Registrar role and trim the conflated
     Program Chair role to read-only.
  4. Disciplinary incidents: let Instructors report (add Instructor C/R/W).
  5. Seminary Manager parity: wherever Program Chair can create but Seminary
     Manager has no permlevel-0 row, mirror it (Seminary Manager was forgotten).

Only permlevel-0 rows of the managed staff roles are rewritten. permlevel>0
field-level perms, and every other role (Student, Alumni, Student Applicant,
Accounts*, HR*, Guest, All, Administrator, System Manager), are preserved as-is
apart from the rename. Run from the app root; re-runnable (idempotent).
"""

import glob
import json
import os

DOCTYPE_DIRS = ("seminary/seminary/doctype", "seminary/alumni/doctype")

# flag letter -> DocPerm boolean key
FLAG = {
    "C": "create",
    "R": "read",
    "W": "write",
    "D": "delete",
    "S": "submit",
    "X": "cancel",
    "A": "amend",
}
# Frappe writes these on every perm row regardless of access level.
BASE_KEYS = ("email", "export", "print", "report", "share")


def perm(role, flags):
    p = {"role": role}
    for k in BASE_KEYS:
        p[k] = 1
    for ch in flags:
        p[FLAG[ch]] = 1
    return p


# doctype -> {role: flags}. These replace/add the role's permlevel-0 row.
CURATED = {
    # --- (2) forgotten System-Manager-only doctypes -----------------------
    "buildings": {
        "Seminary Manager": "CRWD",
        "Program Chair": "R",
        "Registrar": "R",
        "Instructor": "R",
    },
    "course_gradebook": {
        "Seminary Manager": "CRWD",
        "Program Chair": "CRWD",
        "Instructor": "CRW",
        "Registrar": "R",
    },
    "course_result_tool": {
        "Seminary Manager": "CRWD",
        "Program Chair": "CRWD",
        "Instructor": "CRW",
        "Registrar": "R",
    },
    "payers_fee_category_pe": {
        "Seminary Manager": "CRWD",
    },
    # --- (3) records-lifecycle: add Registrar, trim Program Chair ----------
    "student": {
        "Seminary Manager": "CRWD",
        "Registrar": "CRWD",
        "Program Chair": "R",
        "Instructor": "R",
    },
    "academic_term": {
        "Seminary Manager": "CRWD",
        "Registrar": "CRWD",
        "Program Chair": "R",
        "Instructor": "R",
    },
    "academic_year": {
        "Seminary Manager": "CRWD",
        "Registrar": "CRWD",
        "Program Chair": "R",
        "Instructor": "R",
    },
    "program_enrollment": {
        "Seminary Manager": "CRWDSXA",
        "Registrar": "CRWDSXA",
        "Program Chair": "R",
        "Instructor": "R",
    },
    "course_enrollment_individual": {
        "Seminary Manager": "CRWDSXA",
        "Registrar": "CRWDSXA",
        "Program Chair": "R",
        "Instructor": "R",
    },
    "term_admission": {
        "Seminary Manager": "CRWDSXA",
        "Registrar": "CRWDSXA",
        "Program Chair": "R",
    },
    "student_log": {
        "Seminary Manager": "CRWD",
        "Registrar": "CRWD",
        "Program Chair": "R",
        "Instructor": "R",
    },
    "withdrawal_request": {
        "Registrar": "CRWDSXA",
        "Program Chair": "R",
    },
    "student_applicant": {
        "Seminary Manager": "CRWD",
        "Registrar": "CRWD",
        "Program Chair": "R",
    },
    "diploma": {
        "Seminary Manager": "CRWD",
        "Registrar": "CRWD",
        "Program Chair": "R",
    },
    "graduation_request": {
        "Registrar": "CRWDSXA",
    },
    "alumni_profile": {
        "Registrar": "CRWD",
    },
    # --- (4) disciplinary incidents: instructors may report ---------------
    "disciplinary_incident": {
        "Instructor": "CRW",
        "Program Chair": "CRW",
    },
    # --- (6) course authoring: instructors build their own chapters --------
    # (Course Lesson already grants Instructor CRWD; the chapter/lesson
    # reference child tables inherit Course Schedule, which also does.)
    "course_schedule_chapter": {
        "Instructor": "CRWD",
    },
}

MANAGED_PARITY_SRC = "Program Chair"
PARITY_TARGET = "Seminary Manager"


def load(path):
    return json.loads(open(path).read())


def dump(path, d):
    open(path, "w").write(json.dumps(d, indent=1, sort_keys=True))


def summarize(perms):
    out = []
    for p in perms:
        fl = "".join(ch for ch, k in FLAG.items() if p.get(k))
        lvl = p.get("permlevel", 0)
        tag = f"{p.get('role')}" + (f"@{lvl}" if lvl else "")
        out.append(f"{tag}={fl or '-'}" + ("(O)" if p.get("if_owner") else ""))
    return "; ".join(out)


def main():
    changed = []
    files = []
    for dd in DOCTYPE_DIRS:
        files.extend(glob.glob(f"{dd}/*/*.json"))
    for jf in sorted(files):
        name = os.path.basename(jf)[:-5]
        if name != os.path.basename(os.path.dirname(jf)):
            continue
        d = load(jf)
        if d.get("doctype") != "DocType":
            continue
        perms = d.get("permissions", []) or []
        before = summarize(perms)

        # (1) universal rename, all permlevels
        for p in perms:
            if p.get("role") == "Academics User":
                p["role"] = "Program Chair"

        # (2-4) curated permlevel-0 overrides
        overrides = CURATED.get(name)
        if overrides:
            for role, flags in overrides.items():
                # drop existing permlevel-0 row for this role
                perms = [
                    p
                    for p in perms
                    if not (p.get("role") == role and not p.get("permlevel"))
                ]
                perms.append(perm(role, flags))

        # (5) Seminary Manager parity
        pc0 = next(
            (
                p
                for p in perms
                if p.get("role") == MANAGED_PARITY_SRC
                and not p.get("permlevel")
                and p.get("create")
            ),
            None,
        )
        has_sm0 = any(
            p.get("role") == PARITY_TARGET and not p.get("permlevel") for p in perms
        )
        if pc0 and not has_sm0:
            flags = "".join(ch for ch, k in FLAG.items() if pc0.get(k))
            perms.append(perm(PARITY_TARGET, flags))

        d["permissions"] = perms
        after = summarize(perms)
        if before != after:
            dump(jf, d)
            changed.append((name, before, after))

    print(f"# {len(changed)} doctypes changed\n")
    for name, b, a in changed:
        print(f"## {name}")
        print(f"   - {b}")
        print(f"   + {a}\n")


if __name__ == "__main__":
    main()
