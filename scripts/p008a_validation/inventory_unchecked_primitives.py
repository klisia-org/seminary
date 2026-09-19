"""p008a G10: which whitelisted endpoints reach a primitive the permission model
cannot see?

p005a §5: DocPerms, permlevels and the has_permission / permission_query_conditions
hooks never fire on ``Document.db_set``, ``frappe.db.set_value``, ``db_insert``,
``frappe.db.delete``, a save/insert with ``ignore_permissions=True``, or a read
through ``frappe.get_all`` (= ``get_list(ignore_permissions=True)``). For an
endpoint that reaches one of those, its own gate is the ONLY control.

Pure static analysis -- imports nothing from the app, touches no site:

    python scripts/p008a_validation/inventory_unchecked_primitives.py > scripts/p008a_validation/inventory.md

Reachability is transitive through calls to functions of the same module and to
names imported from other ``seminary.`` modules (depth-limited). It is an
over-approximation in places (a call guarded by a branch still counts) and an
under-approximation in others (dynamic dispatch, doc_events, methods on
documents). It is a worklist, not a verdict: "no gate seen" means no authority
assertion was recognised in the ENTRY function's own body.
"""

import ast
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "seminary")
ROOT = os.path.normpath(ROOT)
SKIP_DIRS = {
    ".history",
    "tests",
    "patches",
    "demo",
    "node_modules",
    "public",
    "__pycache__",
}
MAX_DEPTH = 4

GATE = re.compile(
    r"require_[a-z_]+\(|only_for\(|has_permission\(|check_permission\(|_privileged\("
    r"|_require_[a-z_]+\(|_assert[a-z_]*\(|_authorize[a-z_]*\(|PermissionError"
    r"|_my_person\(|current_student\(|own_or_staff\(|is_course_staff\(|is_grader\("
    r"|_is_messaging_staff\(|frappe\.session\.user|_current_person\(|_audience\("
    r"|visible_cohorts\(|assert_can_[a-z_]*\(|check_write_permission\("
    r"|_ensure_[a-z_]+\(|_validate_token\(|compare_digest|user_may_(read|write)\("
    r"|quiz_question_access\(|_may_take_quiz\(|user_is_enrolled_in_course\("
    r"|has_course_(moderator|instructor)_role\(|is_school_role\(|instructor_tier\("
    r"|_check_[a-z_]*permission\(|_validate_(export|pack|target_for_import)\("
)

WRITE = "write"
READ = "read"


def classify_call(node):
    """Return (kind, label) for a call the permission model cannot see."""
    f = node.func
    text = ast.unparse(f)
    kw = {k.arg: k.value for k in node.keywords if k.arg}
    ign = kw.get("ignore_permissions")
    ignored = isinstance(ign, ast.Constant) and ign.value is True
    if text.endswith(".db_set"):
        return WRITE, "db_set"
    if text == "frappe.db.set_value":
        return WRITE, "frappe.db.set_value"
    if text.endswith(".db_insert"):
        return WRITE, "db_insert"
    if text == "frappe.db.delete":
        return WRITE, "frappe.db.delete"
    if text == "frappe.delete_doc" and ignored:
        return WRITE, "delete_doc(ignore_permissions)"
    if (
        text.endswith(".save") or text.endswith(".insert") or text.endswith(".submit")
    ) and ignored:
        return WRITE, text.rsplit(".", 1)[-1] + "(ignore_permissions)"
    if text in ("frappe.get_all", "frappe.db.get_all"):
        return READ, "frappe.get_all"
    return None, None


class Fn:
    __slots__ = (
        "module",
        "name",
        "lineno",
        "whitelisted",
        "guest",
        "gate",
        "prims",
        "calls",
    )

    def __init__(self, module, name, lineno):
        self.module, self.name, self.lineno = module, name, lineno
        self.whitelisted = self.guest = self.gate = False
        self.prims, self.calls = [], set()


def walk_module(path, module):
    src = open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {}, {}
    imports = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("seminary")
        ):
            for a in node.names:
                imports[a.asname or a.name] = (node.module, a.name)
    fns = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fn = Fn(module, node.name, node.lineno)
        for d in node.decorator_list:
            dt = ast.unparse(d)
            if "whitelist" in dt:
                fn.whitelisted = True
                fn.guest = "allow_guest=True" in dt.replace(" ", "")
        body_src = ast.get_source_segment(src, node) or ""
        fn.gate = bool(GATE.search(body_src))
        if any(
            isinstance(n, ast.Attribute)
            and ast.unparse(n).endswith("flags.ignore_permissions")
            for n in ast.walk(node)
        ):
            fn.prims.append((WRITE, "flags.ignore_permissions", node.lineno))
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                kind, label = classify_call(n)
                if kind:
                    fn.prims.append((kind, label, n.lineno))
                if isinstance(n.func, ast.Name):
                    fn.calls.add(n.func.id)
        fns.setdefault(node.name, fn)
    return fns, imports


def main():
    modules, imports_of = {}, {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if not fname.endswith(".py") or fname.startswith("test_"):
                continue
            path = os.path.join(dirpath, fname)
            rel = os.path.relpath(path, os.path.dirname(ROOT))[:-3]
            module = rel.replace(os.sep, ".")
            if module.endswith(".__init__"):
                module = module[: -len(".__init__")]
            modules[module], imports_of[module] = walk_module(path, module)

    def reach(fn, depth, seen):
        """All (kind, label, module, line, via) reachable from fn."""
        out = [(k, l, fn.module, ln, fn.name) for k, l, ln in fn.prims]
        if depth >= MAX_DEPTH:
            return out
        for callee in fn.calls:
            target = None
            if callee in modules[fn.module] and callee != fn.name:
                target = modules[fn.module][callee]
            elif callee in imports_of[fn.module]:
                mod, real = imports_of[fn.module][callee]
                target = modules.get(mod, {}).get(real)
            if target and (target.module, target.name) not in seen:
                seen.add((target.module, target.name))
                out += reach(target, depth + 1, seen)
        return out

    rows = []
    for module, fns in modules.items():
        for fn in fns.values():
            if not fn.whitelisted:
                continue
            found = reach(fn, 0, {(fn.module, fn.name)})
            writes = sorted({(l, m, ln) for k, l, m, ln, _ in found if k == WRITE})
            reads = sorted({(l, m, ln) for k, l, m, ln, _ in found if k == READ})
            rows.append((fn, writes, reads))

    total = len(rows)
    w_nogate = [r for r in rows if r[1] and not r[0].gate]
    r_nogate = [r for r in rows if not r[1] and r[2] and not r[0].gate]
    w_gate = [r for r in rows if r[1] and r[0].gate]

    def short(m):
        return m.replace("seminary.seminary.", "s.s.").replace("seminary.", "s.")

    def fmt(sites, n=3):
        s = "; ".join(f"`{l}` {short(m)}:{ln}" for l, m, ln in sites[:n])
        return s + (f" … +{len(sites) - n}" if len(sites) > n else "")

    p = print
    p("# p008a G10 — endpoints that reach a primitive the permission model cannot see")
    p()
    p(
        "Generated by `scripts/p008a_validation/inventory_unchecked_primitives.py` (static AST walk;"
    )
    p(
        "see its docstring for what it over- and under-approximates). **A worklist, not a verdict.**"
    )
    p()
    p("| | count |")
    p("|---|---|")
    p(f"| whitelisted endpoints analysed | {total} |")
    p(
        f"| reach an unchecked **write**, gate recognised in the entry function | {len(w_gate)} |"
    )
    p(f"| reach an unchecked **write**, **no gate recognised** | **{len(w_nogate)}** |")
    p(
        f"| reach only an unchecked **read** (`frappe.get_all`), no gate recognised | {len(r_nogate)} |"
    )
    p()
    p("## 1. Unchecked write, no gate recognised in the entry function — review first")
    p()
    p("| endpoint | guest | write primitives reached |")
    p("|---|---|---|")
    for fn, writes, _ in sorted(w_nogate, key=lambda r: (r[0].module, r[0].name)):
        p(
            f"| `{short(fn.module)}.{fn.name}`:{fn.lineno} | {'**yes**' if fn.guest else ''} | {fmt(writes)} |"
        )
    p()
    p("## 2. Unchecked read only (`frappe.get_all`), no gate recognised")
    p()
    p(
        "The row hooks never run on these reads (p005a A01-18 was one). Many are reference data."
    )
    p()
    p("| endpoint | guest | reads reached |")
    p("|---|---|---|")
    for fn, _, reads in sorted(r_nogate, key=lambda r: (r[0].module, r[0].name)):
        p(
            f"| `{short(fn.module)}.{fn.name}`:{fn.lineno} | {'**yes**' if fn.guest else ''} | {fmt(reads)} |"
        )
    p()
    p("## 3. Unchecked write behind a recognised gate — by module")
    p()
    p("The gate is the only control on these. Counted, not listed: the whitelist walk")
    p(
        "(`test_p007_whitelist_walk`) is where each gets classified and, for STAFF_ONLY, executed."
    )
    p()
    by = defaultdict(int)
    for fn, _, _ in w_gate:
        by[fn.module] += 1
    p("| module | endpoints |")
    p("|---|---|")
    for m, n in sorted(by.items(), key=lambda kv: -kv[1]):
        p(f"| `{short(m)}` | {n} |")


if __name__ == "__main__":
    sys.exit(main())
