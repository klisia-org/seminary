"""Clear payment-gating fields on Free programs.

`require_pay_submit` defaults to 1, which leaks into Free programs even
though the field is hidden on the form. The CEI workflow conditions for
free programs evaluate `doc.is_free or not doc.require_pay_submit`, so the
correct path is taken in normal flow — but a stray `require_pay_submit=1`
on a free Program propagates via fetch_from to CEI and can cause a
Free CEI to land at "Awaiting Payment" if the chained fetch resolves out
of order. Force the gating fields off on every existing free Program so
the source-of-truth stays consistent.

Idempotent.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        """SELECT name FROM `tabProgram`
           WHERE is_free = 1
             AND (require_pay_submit = 1 OR percent_to_pay > 0)""",
        as_dict=True,
    )
    if not rows:
        print("No free programs need payment-gate cleanup.")
        return

    for row in rows:
        frappe.db.set_value(
            "Program",
            row.name,
            {"require_pay_submit": 0, "percent_to_pay": 0},
            update_modified=False,
        )

    frappe.db.commit()
    print(f"Cleared payment-gate fields on {len(rows)} free Program(s).")
