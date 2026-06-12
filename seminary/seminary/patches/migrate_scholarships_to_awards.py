"""Post-sync: turn legacy scholarships into first-class Scholarship Awards.

Two parts (ADR 047), both idempotent:

  (a) For each stashed Payers Fee Category PE → Scholarships link (see
      stash_scholarship_links), create one active Scholarship Award for the
      enrollment, snapshotting the template's discount terms.

  (b) Undo the old payer-row mechanism: every pgm_enroll_payers row whose payer is
      the configured scholarship customer had its percentage carved out of the
      student's share. Add it back to the student row and delete the scholarship
      row, so the student again owns 100% of their share and the discount is
      applied at invoice time instead.

Submitted Sales Invoices are never touched — only future billing uses the new path.
"""

import frappe

STASH = "__scholarship_link_stash"


def execute():
    _create_awards_from_stash()
    _restore_student_payer_rows()
    _drop_legacy_column()
    frappe.db.commit()


def _drop_legacy_column():
    """Frappe leaves a removed field's column as an orphan; drop it explicitly so
    the legacy `scholarship` link is fully gone (ADR 047)."""
    has_col = frappe.db.sql(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tabPayers Fee Category PE'
          AND column_name = 'scholarship' AND table_schema = DATABASE()
        """
    )
    if has_col:
        frappe.db.sql_ddl(
            "ALTER TABLE `tabPayers Fee Category PE` DROP COLUMN `scholarship`"
        )
        print("Dropped legacy scholarship column.")


def _stash_rows():
    exists = frappe.db.sql(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = %s AND table_schema = DATABASE()
        """,
        (STASH,),
    )
    if not exists:
        return []
    return frappe.db.sql(f"SELECT pfc, pf_pe, scholarship FROM `{STASH}`", as_dict=True)


def _create_awards_from_stash():
    rows = _stash_rows()
    created = 0
    for r in rows:
        if not r.pf_pe or not r.scholarship:
            continue
        if not frappe.db.exists("Scholarships", r.scholarship):
            continue
        # One award per enrollment; skip if one already exists (idempotent).
        if frappe.db.exists("Scholarship Award", {"program_enrollment": r.pf_pe}):
            continue
        award = frappe.new_doc("Scholarship Award")
        award.scholarship = r.scholarship
        award.program_enrollment = r.pf_pe
        award.effective_from = frappe.utils.today()
        award.workflow_state = "Active"
        award.flags.ignore_permissions = True
        award.insert()  # _snapshot_terms runs in validate()
        created += 1
    if rows:
        frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `{STASH}`")
    print(f"Created {created} Scholarship Award(s) from legacy links.")


def _restore_student_payer_rows():
    sch_customer = frappe.db.get_single_value("Seminary Settings", "scholarship_cust")
    if not sch_customer:
        print("No scholarship customer configured; skipping payer-row restore.")
        return

    sch_rows = frappe.db.sql(
        """
        SELECT name, parent, fee_category, pay_percent
        FROM `tabpgm_enroll_payers`
        WHERE payer = %s
        """,
        (sch_customer,),
        as_dict=True,
    )
    if not sch_rows:
        print("No scholarship payer rows to restore.")
        return

    restored = 0
    for row in sch_rows:
        pe = frappe.db.get_value("Payers Fee Category PE", row.parent, "pf_pe")
        student = pe and frappe.db.get_value("Program Enrollment", pe, "student")
        student_customer = (
            frappe.db.get_value("Student", student, "customer") if student else None
        ) or student
        if student_customer:
            student_row = frappe.db.get_value(
                "pgm_enroll_payers",
                {
                    "parent": row.parent,
                    "fee_category": row.fee_category,
                    "payer": student_customer,
                },
                ["name", "pay_percent"],
                as_dict=True,
            )
            if student_row:
                new_pct = (student_row.pay_percent or 0) + (row.pay_percent or 0)
                frappe.db.set_value(
                    "pgm_enroll_payers",
                    student_row.name,
                    "pay_percent",
                    new_pct,
                    update_modified=False,
                )
        frappe.delete_doc(
            "pgm_enroll_payers", row.name, force=1, ignore_permissions=True
        )
        restored += 1

    # Flag any enrollment whose per-fee split no longer sums to 100 for manual review.
    bad = frappe.db.sql(
        """
        SELECT parent, fee_category, SUM(pay_percent) pct
        FROM `tabpgm_enroll_payers`
        GROUP BY parent, fee_category
        HAVING pct != 100
        """,
        as_dict=True,
    )
    for b in bad:
        frappe.log_error(
            f"Payer split != 100 after scholarship migration: {b.parent} / "
            f"{b.fee_category} = {b.pct}",
            "migrate_scholarships_to_awards",
        )
    print(
        f"Restored {restored} student payer row(s); "
        f"{len(bad)} split(s) need manual review."
    )
