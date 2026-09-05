"""ADR 068 §7 — push every captured attribute from applicants onto their Person.

`_promote_to_person` passed seven hand-written arguments while the registry
declared fourteen, so gender, date of birth, nationality and the whole address
block never left the applicant record. Nothing errored: the arguments were
simply not there to be passed, which is why the gap survived a whole phase of
work aimed at it.

Phase 2's `backfill_person_shared_attributes` filled the spine from the
applicants that existed *then*. Everyone who applied between that patch and
this one has the same holes again, so fill blanks once more now that the
promotion is registry-derived and the leak is closed.

Fill-blanks, never overwrite: a Registrar may have corrected something on the
Person since, and the application is the older document.
"""

import frappe

from seminary.seminary import person as person_spine
from seminary.seminary import person_fields


def execute():
    applicants = frappe.get_all(
        "Student Applicant",
        filters={"person": ["is", "set"]},
        fields=["name"],
        order_by="creation asc",
    )
    filled = 0
    for row in applicants:
        doc = frappe.get_doc("Student Applicant", row.name)
        if not frappe.db.exists("Person", doc.person):
            continue
        before = frappe.db.get_value(
            "Person", doc.person, "modified", as_dict=False, cache=False
        )
        person_spine.update_person(
            doc.person,
            email=doc.student_email_id,
            overwrite=False,
            **person_fields.spine_kwargs(doc),
        )
        after = frappe.db.get_value(
            "Person", doc.person, "modified", as_dict=False, cache=False
        )
        if before != after:
            filled += 1
    if filled:
        print("  filled shared attributes on %d Person record(s)" % filled)
