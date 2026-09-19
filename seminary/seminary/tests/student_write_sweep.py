# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008 student-path sweep: a student-reachable endpoint that p007 closed.

``save_progress`` recorded a student's lesson progress with a full
``Scheduled Course Roster`` save. p007 F1 took Student write off that doctype --
correctly -- so every lesson view raised PermissionError and no progress had
been recorded since. Nothing caught it: the p006/p007 matrices assert what a
student may NOT do, and the whitelist walk asserts that staff endpoints refuse a
student. Neither asserts that a student's own endpoints still work.

This module looks for the same shape everywhere else: an endpoint a student may
call (STUDENT_ALLOWED or OWN_RULE in the walk contract), holding a
permission-checked write -- ``save``, ``insert``, ``submit``, ``delete`` with no
``ignore_permissions`` -- to a doctype whose Student DocPerm does not grant it.

A worklist, not a verdict. It over-reports (a doctype named in the function need
not be the one written, and a write may sit behind a staff-only branch) and it
under-reports (it follows calls one level, and only within the same module). The
test that consumes it therefore ratchets a known list rather than demanding
zero: what matters is that the list cannot grow unnoticed.
"""

import ast
import os
from collections import defaultdict

import frappe

APP = os.path.dirname(  # .../apps/seminary
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
WALK = os.path.join(APP, "seminary", "seminary", "tests", "test_p007_whitelist_walk.py")

WRITES = {"save": "write", "insert": "create", "submit": "submit", "delete": "delete"}


def _sets():
    tree = ast.parse(open(WALK).read())
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            try:
                out[n.targets[0].id] = set(ast.literal_eval(n.value))
            except (ValueError, TypeError, SyntaxError):
                # not a literal set (`STAFF_ONLY |= ...`, a comprehension) --
                # the sets this needs are all literals
                continue
    student = out.get("STUDENT_ALLOWED", set()) | out.get("G6_STUDENT_ALLOWED", set())
    return student | out.get("OWN_RULE", set()) | out.get("G6_OWN_RULE", set())


def _module_path(mod):
    rel = mod.split(".")[1:]
    p = os.path.join(APP, "seminary", *rel) + ".py"
    if os.path.exists(p):
        return p
    p = os.path.join(APP, "seminary", *rel, "__init__.py")
    return p if os.path.exists(p) else None


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _flagged(node) -> bool:
    """``doc.flags.ignore_permissions = True`` anywhere in the body. Coarse --
    it does not track which doc -- but a function that sets it at all is one
    whose author already thought about this, so the honest default is to
    believe them and keep the sweep's output short enough to read."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Assign):
            continue
        for t in sub.targets:
            if (
                isinstance(t, ast.Attribute)
                and t.attr == "ignore_permissions"
                and isinstance(t.value, ast.Attribute)
                and t.value.attr == "flags"
            ):
                return True
    return False


def _scan(node):
    """(doctypes named, {ptype: [call]}) for one function body."""
    doctypes, writes = set(), defaultdict(list)
    if _flagged(node):
        return doctypes, writes
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        n = _name(sub.func)
        if n in ("get_doc", "new_doc") and sub.args:
            a = sub.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                doctypes.add(a.value)
        if n in WRITES:
            ignored = any(
                k.arg == "ignore_permissions"
                and not (isinstance(k.value, ast.Constant) and k.value.value is False)
                for k in sub.keywords
            )
            if not ignored:
                writes[WRITES[n]].append(n)
    return doctypes, writes


def _student_grants(doctype):
    """What the Student DocPerm row grants at permlevel 0, Custom rows included."""
    grants = set()
    for perm in frappe.get_all(
        "DocPerm",
        filters={"parent": doctype, "role": "Student", "permlevel": 0},
        fields=["read", "write", "create", "submit", "delete"],
    ) + frappe.get_all(
        "Custom DocPerm",
        filters={"parent": doctype, "role": "Student", "permlevel": 0},
        fields=["read", "write", "create", "submit", "delete"],
    ):
        grants |= {
            k for k in ("read", "write", "create", "submit", "delete") if perm[k]
        }
    return grants


def sweep():
    """Returns [(endpoint, doctype, missing ptypes, ptypes called)]."""
    hits, checked = [], 0
    cache = {}
    for dotted in sorted(_sets()):
        mod, fn = dotted.rsplit(".", 1)
        path = _module_path(mod)
        if not path:
            continue
        try:
            tree = ast.parse(open(path).read())
        except (OSError, SyntaxError):
            continue
        local = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        entry = local.get(fn)
        if entry is None:
            continue
        checked += 1
        doctypes, writes = _scan(entry)
        for sub in ast.walk(entry):  # one level of local helpers
            if isinstance(sub, ast.Call):
                helper = local.get(_name(sub.func))
                if helper is not None and helper is not entry:
                    d2, w2 = _scan(helper)
                    doctypes |= d2
                    for k, v in w2.items():
                        writes[k].extend(v)
        if not writes:
            continue
        for dt in sorted(doctypes):
            if dt not in cache:
                cache[dt] = _student_grants(dt)
            grants = cache[dt]
            missing = sorted(set(writes) - grants)
            if missing:
                hits.append((dotted, dt, missing, sorted(writes)))

    return checked, hits


def report():
    checked, hits = sweep()
    print(f"student-reachable endpoints scanned: {checked}")
    print(f"candidate (endpoint, doctype) pairs: {len(hits)}\n")
    by_ep = defaultdict(list)
    for dotted, dt, missing, w in hits:
        by_ep[dotted].append((dt, missing, w))
    for dotted in sorted(by_ep):
        print(f"  {dotted}")
        for dt, missing, w in by_ep[dotted]:
            print(
                f"      {dt}: Student lacks {','.join(missing)} (calls {','.join(w)})"
            )
    return hits
