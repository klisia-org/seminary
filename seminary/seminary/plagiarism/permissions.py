"""Defense-in-depth permissions for Plagiarism Check Result.

The doctype JSON already withholds the Student role, but plagiarism findings are
sensitive enough to gate a second way: only graders/managers may read a result,
regardless of any share or owner path. Mirrors the staff-role check style used
across api.py.

## p010 H16 (p005a A06-5): this was the only unpaired registration of the 41

Two defects, both of them the kind that make a control look present and do
nothing:

1. **The signature was `(doc, user=None, permission_type=None)`** while every
   other hook in the app is `(doc, ptype=None, user=None)`. Frappe passes the
   permission type as `ptype` and `frappe.call` drops keyword arguments the
   function does not declare, so this hook **never saw the ptype** and could not
   tell a read from a delete. Any future tightening written into it would have
   been silently inert.

2. **There was no `permission_query_conditions`.** Frappe calls
   `has_permission` per document; a *list* query is filtered only by the query
   condition. So the second gate applied to opening a result and not to listing
   them, and list and doc could disagree -- which is the whole failure mode a
   paired registration exists to prevent.

Recorded, not fixed here: this is still school-wide. An Instructor sees results
for students they do not teach. Narrowing it to the instructor's own sections
needs a route from the result to a Course Schedule, which this doctype does not
carry (it links `student` and `assignment`, not the section) -- the same
designed work p008a deferred for the activity doctypes.
"""

import frappe

STAFF_ROLES = {
    "Instructor",
    "Program Chair",
    "Seminary Manager",
    "System Manager",
}


def _is_staff(user=None) -> bool:
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    return bool(STAFF_ROLES & set(frappe.get_roles(user)))


def has_permission(doc, ptype=None, user=None):
    """Staff only, for every permission type.

    A controller `has_permission` can only *restrict* -- frappe checks it in
    addition to the DocPerms, never instead of them -- so this does not widen
    anything the JSON withholds. It now receives `ptype`, which is what makes
    the restriction expressible at all.
    """
    return _is_staff(user)


def get_permission_query_conditions(user=None):
    """The other half of the pair: the same rule, applied to list queries.

    `1 = 0` rather than `None`, because `None` reads as *no restriction* --
    the exact fail-open shape p005a flagged elsewhere as A01-20.
    """
    if _is_staff(user):
        return ""
    return "1 = 0"
