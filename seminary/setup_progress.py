# Copyright (c) 2026, Murilo R. Melo and contributors
# For license information, please see license.txt

"""Setup progress: what a school still has to set up, checked against its records (privatedocs p024).

Each app registers one `setup_steps` hook that returns its group:

    {"name": "Seminary", "label": _("Seminary"), "page": "seminary-setup",
     "roles": ["Seminary Manager", ...], "steps": [step, ...]}

An app that adds steps to another app's group returns the same `name` with only `steps`. A step is

    {"key": ..., "title": ..., "tier": one of TIERS, "check": callable, "route": "/desk/...",
     "description": ..., "manual": "<docs page>#<heading>", "roles": [...],
     "flag": optional badge text, "rank": optional sort key within its tier}

`check()` returns a bool, or `(done, total)` for a step that covers several records. Nothing is
stored: a step is done when the records say so.
"""

import frappe
from frappe import _

TIERS = (
    "Go-live",
    "Before the first term",
    "Before the first evaluation or self-study cycle",
    "Before the first publication",
    "Optional",
)
ALWAYS = "System Manager"


def groups() -> list[dict]:
    """Every registered group, its steps merged, in hook order."""
    merged = {}
    for path in frappe.get_hooks("setup_steps"):
        group = frappe.get_attr(path)()
        if not group:
            continue
        into = merged.setdefault(
            group["name"], {"name": group["name"], "steps": [], "roles": []}
        )
        for key in ("label", "page"):
            if group.get(key):
                into[key] = group[key]
        into["roles"] += [r for r in group.get("roles") or [] if r not in into["roles"]]
        into["steps"] += group.get("steps") or []
    return [g for g in merged.values() if g.get("page") and g["steps"]]


def can_open(group) -> bool:
    roles = set(frappe.get_roles())
    return ALWAYS in roles or bool(roles & set(group["roles"]))


def evaluate(step) -> dict:
    """The step's state. A check that fails shows as not done, with the error logged once."""
    try:
        result = step["check"]()
    except Exception:
        frappe.log_error(title=f"Setup step {step['key']} failed")
        return {"done": False, "failed": True}
    if isinstance(result, (tuple, list)):
        done, total = result
        return {"done": bool(total) and done >= total, "count": [done, total]}
    return {"done": bool(result)}


def manual_route(section):
    hooks = frappe.get_hooks("setup_manual_route")
    return frappe.get_attr(hooks[-1])(section) if hooks and section else None


@frappe.whitelist()
def get_progress(group: str) -> dict:
    everything = groups()
    mine = next((g for g in everything if g["name"] == group), None)
    if not mine:
        frappe.throw(_("No setup steps are registered for {0}.").format(group))
    if not can_open(mine):
        frappe.throw(
            _("You cannot open the setup progress of {0}.").format(group),
            frappe.PermissionError,
        )

    states = {
        g["name"]: {s["key"]: evaluate(s) for s in g["steps"]} for g in everything
    }
    tiers = []
    for tier in TIERS:
        steps = [s for s in mine["steps"] if s["tier"] == tier]
        if not steps and not any(
            s["tier"] == tier for g in everything for s in g["steps"]
        ):
            continue
        tiers.append(
            {
                "tier": tier,
                "label": tier_label(tier),
                "tiles": [
                    _tile(g, tier, states[g["name"]])
                    for g in everything
                    if _in_tier(g, tier)
                ],
                "steps": [
                    _row(s, states[group][s["key"]])
                    for s in sorted(steps, key=lambda s: s.get("rank", 0))
                ],
            }
        )
    return {"group": group, "label": mine.get("label") or group, "tiers": tiers}


def tier_label(tier):
    return {
        "Go-live": _("Go-live"),
        "Before the first term": _("Before the first term"),
        "Before the first evaluation or self-study cycle": _(
            "Before the first evaluation or self-study cycle"
        ),
        "Before the first publication": _("Before the first publication"),
        "Optional": _("Optional"),
    }[tier]


def _in_tier(group, tier):
    return any(s["tier"] == tier for s in group["steps"])


def _tile(group, tier, states):
    keys = [s["key"] for s in group["steps"] if s["tier"] == tier]
    return {
        "group": group["name"],
        "label": group.get("label") or group["name"],
        "done": sum(1 for k in keys if states[k]["done"]),
        "total": len(keys),
        "page": group["page"] if can_open(group) else None,
    }


def _row(step, state):
    return {
        "key": step["key"],
        "title": step["title"],
        "description": step.get("description"),
        "route": step.get("route"),
        "manual": manual_route(step.get("manual")),
        "roles": [_(r) for r in step.get("roles") or []],
        "flag": step.get("flag"),
        **state,
    }
