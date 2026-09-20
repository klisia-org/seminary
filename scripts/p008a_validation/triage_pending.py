"""p008a G6: facts about each endpoint still in PENDING_CLASSIFICATION.

A static AST pass over the app. For every pending endpoint it reports the gate
calls that appear in the entry function, whether it is `allow_guest`, and the
doctypes it writes. **A worklist, not a verdict** -- the classification is made
by reading the function; this exists so the reading is targeted.

    ../../env/bin/python scripts/p008a_validation/triage_pending.py [module-prefix]
"""

import ast
import os
import sys
from collections import defaultdict

APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WALK = os.path.join(APP, "seminary", "seminary", "tests", "test_p007_whitelist_walk.py")

GATES = {
    # guards.py
    "require_grader",
    "require_outline_editor",
    "require_registrar",
    "require_course_staff",
    "require_enrolled",
    "require_own_student",
    "require_own_enrollment",
    "own_or_staff",
    "is_school_role",
    "is_grader",
    "is_course_staff",
    "may_read_course_schedule",
    "is_enrolled",
    "instructor_tier",
    "current_student",
    "current_instructor",
    "student_sections",
    "enrolled_sections",
    "own_course_schedules",
    "readable_course_schedules",
    "faculty_read_scope",
    # frappe
    "only_for",
    "has_permission",
    "check_permission",
    "get_roles",
    "throw",
    "PermissionError",
    # app-local
    "_authorize_privileged_or_instructor",
    "_require_import_role",
    "require_safe_url",
    "_user_owns_project",
    "_assert_owns_submission",
    "_assert_may_take_exam",
    "_is_messaging_staff",
}
WRITES = {
    "save",
    "insert",
    "submit",
    "cancel",
    "delete",
    "db_set",
    "set_value",
    "delete_doc",
    "rename_doc",
    "db_insert",
    "db_update",
    "bulk_insert",
}


def pending():
    tree = ast.parse(open(WALK).read())
    for n in tree.body:
        if (
            isinstance(n, ast.Assign)
            and getattr(n.targets[0], "id", "") == "PENDING_CLASSIFICATION"
        ):
            return set(ast.literal_eval(n.value))
    return set()


def module_path(mod):
    rel = mod.split(".")[1:]  # drop the leading 'seminary' package name
    p = os.path.join(APP, "seminary", *rel) + ".py"
    if os.path.exists(p):
        return p
    p = os.path.join(APP, "seminary", *rel, "__init__.py")
    return p if os.path.exists(p) else None


def _looks_like_gate(n: str) -> bool:
    """Every module grows its own gate helper (`_require_author_or_staff`,
    `require_capability`, `_require_self_service`). Recognise the shape rather
    than keeping a list that is always one module out of date."""
    low = n.lower()
    return (
        low.startswith(("require_", "_require_", "assert_", "_assert_", "ensure_can"))
        or "authoriz" in low
        or low.endswith(("_or_staff", "_owns", "_may_write", "_may_read"))
    )


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def facts(path, fname):
    try:
        tree = ast.parse(open(path).read())
    except (OSError, SyntaxError):
        return None
    methods = set()
    for cls in ast.walk(tree):
        if isinstance(cls, ast.ClassDef):
            methods.update(f.name for f in cls.body if isinstance(f, ast.FunctionDef))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != fname:
            continue
        wl = guest = False
        for d in node.decorator_list:
            if isinstance(d, ast.Call) and _name(d.func) == "whitelist":
                wl = True
                for kw in d.keywords:
                    if kw.arg == "allow_guest" and getattr(kw.value, "value", False):
                        guest = True
            elif _name(d) == "whitelist":
                wl = True
        if not wl:
            continue
        gates, writes, doctypes = set(), set(), set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                n = _name(sub.func)
                if n in GATES or _looks_like_gate(n):
                    gates.add(n)
                if n in WRITES:
                    # `ignore_permissions=False` is the opposite of a finding --
                    # it says the author looked. Only a TRUE literal counts.
                    ign = any(
                        k.arg == "ignore_permissions"
                        and not (
                            isinstance(k.value, ast.Constant) and k.value.value is False
                        )
                        for k in sub.keywords
                    )
                    writes.add(n + ("(ignore_permissions)" if ign else ""))
                if n in ("get_doc", "new_doc", "set_value", "delete_doc") and sub.args:
                    a = sub.args[0]
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        doctypes.add(a.value)
            if isinstance(sub, ast.Raise) and _name(sub.exc) == "PermissionError":
                gates.add("raise PermissionError")
        docstring = (ast.get_docstring(node) or "").strip().splitlines()
        return {
            "method": fname in methods,
            "guest": guest,
            "gates": sorted(gates),
            "writes": sorted(writes),
            "doctypes": sorted(doctypes),
            "line": node.lineno,
            "doc": docstring[0] if docstring else "",
        }
    return None


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else ""
    by_mod = defaultdict(list)
    for dotted in pending():
        mod, fn = dotted.rsplit(".", 1)
        if prefix and not mod.startswith(prefix):
            continue
        by_mod[mod].append(fn)

    for mod in sorted(by_mod):
        path = module_path(mod)
        print(f"\n## {mod}  ({len(by_mod[mod])})")
        if not path:
            print("   !! module file not found")
            continue
        for fn in sorted(by_mod[mod]):
            f = facts(path, fn)
            if f is None:
                print(f"  - {fn}: !! not found / not whitelisted in source")
                continue
            bits = []
            if f["method"]:
                bits.append("DOC-METHOD")
            if f["guest"]:
                bits.append("GUEST")
            bits.append("gates=" + (",".join(f["gates"]) or "-"))
            if f["writes"]:
                bits.append("writes=" + ",".join(f["writes"]))
            if f["doctypes"]:
                bits.append("dt=" + ",".join(f["doctypes"][:6]))
            print(f"  - {fn}:{f['line']}  {' | '.join(bits)}")
            if f["doc"]:
                print(f"      \"{f['doc'][:110]}\"")


if __name__ == "__main__":
    main()
