"""Backfill the Person identity spine (ADR 042) for existing stakeholders.

Creates one Person per distinct human across Student, Student Applicant,
Instructor, and Alumni Profile, matching by normalized email / User, and links
each role row's ``person`` field. Students run first (richest identity data),
so applicants/instructors/alumni of the same human attach to the same Person.

Hard-fails listing ALL collisions (same email but conflicting names, or two
different Users claiming one Person) instead of auto-merging — pre-production
dataset, resolve by hand and re-run. Idempotent (rows with ``person`` set are
skipped; ensure_person only fills blanks).
"""

import frappe

from seminary.seminary import person as spine
from seminary.install import seed_communication_channels


def execute():
    seed_communication_channels()

    conflicts = []

    def link(doctype, row_name, person_name):
        frappe.db.set_value(
            doctype, row_name, "person", person_name, update_modified=False
        )

    def names_conflict(person_name, first, last):
        stored = frappe.db.get_value(
            "Person", person_name, ["first_name", "last_name"], as_dict=True
        )
        for have, incoming in ((stored.first_name, first), (stored.last_name, last)):
            if (
                have
                and incoming
                and have.strip().casefold() != incoming.strip().casefold()
            ):
                return True
        return False

    def resolve(doctype, row_name, label, ensure_kwargs, first=None, last=None):
        email = spine.normalize_email(ensure_kwargs.get("email"))
        existing = spine.find_person(email=email, user=ensure_kwargs.get("user"))
        if existing and names_conflict(existing, first, last):
            conflicts.append(
                f"{doctype} {row_name} ({label}) collides with Person {existing}"
            )
            return None
        try:
            person_name = spine.ensure_person(**ensure_kwargs)
        except frappe.ValidationError as exc:
            conflicts.append(f"{doctype} {row_name} ({label}): {exc}")
            return None
        link(doctype, row_name, person_name)
        return person_name

    # 1) Students — authoritative names, and they carry user + customer.
    for s in frappe.get_all(
        "Student",
        filters={"person": ("is", "not set")},
        fields=[
            "name",
            "first_name",
            "middle_name",
            "last_name",
            "student_email_id",
            "student_mobile_number",
            "user",
            "customer",
            "country",
            "image",
        ],
    ):
        person_name = resolve(
            "Student",
            s.name,
            s.student_email_id,
            dict(
                email=s.student_email_id,
                user=s.user,
                first_name=s.first_name,
                middle_name=s.middle_name,
                last_name=s.last_name,
                mobile=s.student_mobile_number,
                country=s.country,
                image=s.image,
            ),
            first=s.first_name,
            last=s.last_name,
        )
        if person_name:
            spine.link_customer(person_name, s.customer)

    # 2) Applicants — admitted ones resolve to their Student's Person by email.
    for a in frappe.get_all(
        "Student Applicant",
        filters={"person": ("is", "not set")},
        fields=[
            "name",
            "first_name",
            "middle_name",
            "last_name",
            "student_email_id",
            "student_mobile_number",
            "country",
            "image",
        ],
    ):
        resolve(
            "Student Applicant",
            a.name,
            a.student_email_id,
            dict(
                email=a.student_email_id,
                first_name=a.first_name,
                middle_name=a.middle_name,
                last_name=a.last_name,
                mobile=a.student_mobile_number,
                country=a.country,
                image=a.image,
            ),
            first=a.first_name,
            last=a.last_name,
        )

    # 3) Instructors — staff direction: identity lifts from the User.
    for i in frappe.get_all(
        "Instructor",
        filters={"person": ("is", "not set")},
        fields=["name", "user", "prof_email", "phone_message", "profileimage"],
    ):
        resolve(
            "Instructor",
            i.name,
            i.user or i.prof_email,
            dict(
                email=i.prof_email,
                user=i.user,
                mobile=i.phone_message,
                image=i.profileimage,
            ),
        )

    # 4) Alumni — usually the Student's Person via the shared User/email.
    for al in frappe.get_all(
        "Alumni Profile",
        filters={"person": ("is", "not set")},
        fields=["name", "email", "user"],
    ):
        resolve(
            "Alumni Profile",
            al.name,
            al.email,
            dict(email=al.email, user=al.user),
        )

    if conflicts:
        frappe.throw(
            "Person backfill found identity collisions — resolve by hand and re-run "
            "(bench migrate). Nothing was auto-merged:\n- " + "\n- ".join(conflicts)
        )

    frappe.db.commit()
    total = frappe.db.count("Person")
    print(f"Person spine backfilled; {total} Person record(s) on site.")
