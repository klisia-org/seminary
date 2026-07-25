# Copyright (c) 2026, Seminary and contributors
# For license information, please see license.txt

"""Person Import Batch — bulk people onboarding (ADR 042 identity spine).

Frappe's built-in Data Import is awkward for people because one human fans out
into several linked records that must be created in a specific order (Person,
User, Student -> Customer via the oikonomos bridge, Instructor, Alumni, Donor,
plus permission roles). This tool absorbs that ordering: staff stage a CSV of
contact fields + role checkboxes, validate with Dry-Run, then submit to commit.

Every Person is created through seminary.seminary.person.ensure_person (the one
mutation point), never frappe.new_doc("Person"). Role records are created in
dependency order and are idempotent, so a re-run never duplicates them.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, now_datetime, today, validate_email_address

from seminary.seminary.integrations.giving import link_donor
from seminary.seminary.person import ensure_person, find_person, normalize_email

# CSV column contract — also the template header order.
CSV_COLUMNS = [
    "primary_email",
    "first_name",
    "middle_name",
    "last_name",
    "primary_mobile",
    "gender",
    "country",
    "language",
    "image_filename",
    "address_line_1",
    "address_line_2",
    "city",
    "state",
    "pincode",
    "date_of_birth",
    "program_completed",
    "class_year",
    "is_student",
    "is_instructor",
    "is_alumni",
    "is_donor",
    "is_registrar",
    "is_programchair",
    "is_seminarymanager",
]
CHECK_COLUMNS = [c for c in CSV_COLUMNS if c.startswith("is_")]

# Permission-role checkboxes -> Frappe Role granted to the person's User.
# is_programchair maps to "Program Chair" (there is no "Academic User" role —
# it was replaced by Program Chair in seminary/install.py).
PERMISSION_ROLE_MAP = {
    "is_registrar": "Registrar",
    "is_programchair": "Program Chair",
    "is_seminarymanager": "Seminary Manager",
}

TRUTHY = {"1", "true", "yes", "y", "x", "on", "checked", "t"}

# Above this row count the commit runs in a background job.
ENQUEUE_THRESHOLD = 50


class PersonImportBatch(Document):
    # -- lifecycle ---------------------------------------------------------
    def validate(self):
        # Any edit to a draft invalidates a prior clean dry-run, forcing a
        # re-validation before submit. The dry_run save sets in_dry_run so it
        # doesn't clobber its own result; submit runs at docstatus 1 (guarded).
        if self.docstatus == 0 and not self.flags.get("in_dry_run"):
            if self.batch_status != "Draft":
                self.batch_status = "Draft"

    def before_submit(self):
        if not self.rows:
            frappe.throw(_("Nothing to import — add rows first."))
        if self.batch_status != "Dry-Run Clean":
            frappe.throw(
                _("Run a clean Dry-Run before submitting. Current status: {0}.").format(
                    self.batch_status
                )
            )
        errored = [r for r in self.rows if r.row_status == "Error"]
        if errored:
            frappe.throw(
                _(
                    "{0} row(s) still have errors. Fix the data and re-run Dry-Run."
                ).format(len(errored))
            )
        unresolved = [
            r for r in self.rows if r.row_status == "Warning" and not r.override_note
        ]
        if unresolved:
            frappe.throw(
                _(
                    "{0} row(s) have unresolved warnings. Add an Override Note or "
                    "correct the data and re-run Dry-Run."
                ).format(len(unresolved))
            )

    def on_submit(self):
        if len(self.rows) <= ENQUEUE_THRESHOLD:
            self._commit_rows()
            summary = self._store_summary()
            self._mark_committed()
            frappe.msgprint(summary, title=_("Import Complete"), indicator="green")
        else:
            self.db_set("batch_status", "Committing", update_modified=False)
            frappe.msgprint(
                _(
                    "Importing {0} rows in the background — you'll get a summary "
                    "when it finishes."
                ).format(len(self.rows)),
                indicator="blue",
                alert=True,
            )
            frappe.enqueue(
                "seminary.seminary.doctype.person_import_batch."
                "person_import_batch.commit_batch_async",
                queue="long",
                timeout=1500,
                enqueue_after_commit=True,
                batch_name=self.name,
            )

    def before_cancel(self):
        # Creation is not automatically reversible; cancelling only voids the
        # batch record. Warn loudly rather than block, so amend still works.
        frappe.msgprint(
            _(
                "Cancelling does NOT delete the Persons, Users, Students, or other "
                "records this batch created — it only voids the batch. Remove those "
                "manually if needed (supervised operation)."
            ),
            indicator="orange",
            alert=True,
        )

    def _mark_committed(self):
        self.db_set("batch_status", "Committed", update_modified=False)
        self.db_set("committed_on", now_datetime(), update_modified=False)
        self.db_set("committed_by", frappe.session.user, update_modified=False)

    def _store_summary(self):
        text = self._build_summary()
        self.db_set("import_summary", text, update_modified=False)
        return text

    def _build_summary(self):
        failed = [r for r in self.rows if r.row_status != "Committed"]
        persons = sum(1 for r in self.rows if r.created_person)
        students = sum(1 for r in self.rows if r.created_student)
        instructors = sum(1 for r in self.rows if r.created_instructor)
        alumni = sum(1 for r in self.rows if r.created_alumni)
        donors = sum(1 for r in self.rows if r.created_donor)
        parts = [
            _("{0} persons imported").format(persons),
            _("{0} students").format(students),
            _("{0} instructors").format(instructors),
            _("{0} alumni").format(alumni),
        ]
        if donors:
            parts.append(_("{0} donors").format(donors))
        parts.append(_("{0} errors").format(len(failed)))
        return " · ".join(parts)

    # -- helpers -----------------------------------------------------------
    def attached_image_map(self):
        """{lower(file_name): file_url} for images dragged onto this batch."""
        files = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name,
            },
            fields=["file_name", "file_url"],
        )
        return {f.file_name.lower(): f.file_url for f in files if f.file_name}

    # -- whitelisted -------------------------------------------------------
    @frappe.whitelist()
    def download_template(self):
        """Return the canonical CSV header line for the import template."""
        return ",".join(CSV_COLUMNS) + "\n"

    @frappe.whitelist()
    def load_from_csv(self):
        """Parse the attached Source CSV into rows, replacing any existing ones."""
        from frappe.utils.csvutils import read_csv_content
        from frappe.utils.file_manager import get_file

        if not self.source_file:
            frappe.throw(_("Attach a Source CSV first."))

        _fname, content = get_file(self.source_file)
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig", errors="replace")
        data = read_csv_content(content)
        if not data:
            frappe.throw(_("The CSV appears to be empty."))

        header = [(h or "").strip().lower() for h in data[0]]
        known = {col: header.index(col) for col in CSV_COLUMNS if col in header}
        unknown = [h for h in header if h and h not in CSV_COLUMNS]

        self.set("rows", [])
        added = 0
        for raw in data[1:]:
            if not any((cell or "").strip() for cell in raw):
                continue  # skip blank lines
            values = {}
            for col, idx in known.items():
                cell = raw[idx] if idx < len(raw) else ""
                if col in CHECK_COLUMNS:
                    values[col] = _truthy(cell)
                else:
                    values[col] = (cell or "").strip() or None
            values["row_status"] = "Pending"
            self.append("rows", values)
            added += 1

        self.batch_status = "Draft"
        self.save()
        if unknown:
            frappe.msgprint(
                _("Ignored unrecognised column(s): {0}").format(", ".join(unknown))
            )
        return {"rows": added, "ignored_columns": unknown}

    @frappe.whitelist()
    def dry_run(self):
        """Validate every row without writing anything. Sets per-row status and
        the batch gate. Returns a summary the form uses for its alert."""
        if not self.rows:
            frappe.throw(_("Add rows before running a Dry-Run."))

        batch_errors = []
        if self.send_welcome_emails and not frappe.db.exists(
            "Email Account", {"enable_outgoing": 1}
        ):
            batch_errors.append("no_outgoing_email")

        img_map = self.attached_image_map()
        seen_emails = set()
        errors_total = 0
        warnings_total = 0

        for row in self.rows:
            errs = []
            warns = []
            email = normalize_email(row.primary_email)

            if not email:
                errs.append("missing_email")
            elif not validate_email_address(email, throw=False):
                errs.append("bad_email:%s" % row.primary_email)

            if email:
                if email in seen_emails:
                    warns.append("duplicate_in_file")
                else:
                    seen_emails.add(email)

            needs_user = _needs_user(row)
            if email and not errs:
                conflict = _detect_user_conflict(email, needs_user)
                if conflict:
                    errs.append(conflict)

            if not any(row.get(k) for k in CHECK_COLUMNS):
                warns.append("no_role_selected")

            if (row.is_instructor or row.is_alumni) and not _full_name(row):
                # Not fatal — we fall back to the email local part — but flag it
                # so an ugly auto-name (e.g. the instructor named "jdoe") is a
                # deliberate choice.
                warns.append("name_missing_using_email")

            if row.is_donor and not frappe.db.exists("DocType", "Donor"):
                warns.append("giving_not_installed")
            if row.is_student and not frappe.db.exists("DocType", "Customer"):
                warns.append("student_academic_only")

            for fld, dt in (
                ("gender", "Gender"),
                ("country", "Country"),
                ("language", "Language"),
            ):
                val = row.get(fld)
                if val and not frappe.db.exists(dt, val):
                    warns.append("unknown_%s:%s" % (fld, val))

            for key, role in PERMISSION_ROLE_MAP.items():
                if row.get(key) and not frappe.db.exists("Role", role):
                    errs.append("role_missing:%s" % role)

            filename = (row.image_filename or "").strip()
            if filename and filename.lower() not in img_map:
                errs.append("image_missing:%s" % filename)

            if row.date_of_birth:
                try:
                    dob = getdate(row.date_of_birth)
                except Exception:
                    errs.append("bad_dob:%s" % row.date_of_birth)
                else:
                    if dob >= getdate(today()):
                        # Student.validate_dates would reject this at commit.
                        errs.append("dob_not_in_past:%s" % row.date_of_birth)
                    elif not row.is_student:
                        # DOB lives on the Student record; nowhere to store it
                        # for a non-student row.
                        warns.append("dob_needs_student")

            if row.program_completed:
                if not frappe.db.exists("Program", row.program_completed):
                    errs.append("unknown_program:%s" % row.program_completed)
                if not row.is_alumni:
                    warns.append("program_completed_needs_alumni")

            if row.class_year:
                if not str(row.class_year).strip().isdigit():
                    warns.append("bad_class_year:%s" % row.class_year)
                if not row.is_alumni:
                    warns.append("class_year_needs_alumni")

            if errs:
                row.row_status = "Error"
            elif warns:
                row.row_status = "Warning"
            else:
                row.row_status = "Valid"
            row.messages = "; ".join(errs + warns)
            errors_total += len(errs)
            warnings_total += len(warns)

        clean = (
            errors_total == 0
            and not batch_errors
            and all(
                not (r.row_status == "Warning" and not r.override_note)
                for r in self.rows
            )
        )
        self.batch_status = "Dry-Run Clean" if clean else "Draft"
        self.flags.in_dry_run = True
        self.save()

        if batch_errors:
            frappe.msgprint(
                _("Batch-level issue(s): {0}").format(", ".join(batch_errors)),
                indicator="red",
            )
        return {
            "clean": clean,
            "errors": errors_total,
            "warnings": warnings_total,
            "batch_errors": batch_errors,
        }

    # -- commit ------------------------------------------------------------
    def _commit_rows(self):
        img_map = self.attached_image_map()
        for row in self.rows:
            if row.row_status == "Committed":
                continue  # idempotent re-run safety
            self._commit_row(row, img_map)

    def _commit_row(self, row, img_map):
        email = normalize_email(row.primary_email)
        first, mid, last = row.first_name, row.middle_name, row.last_name
        full = _full_name(row) or (email.split("@")[0] if email else None)
        granted = []

        # 1. User first — needed by Instructor, Alumni, and all permission roles.
        #    Pre-creating it (welcome suppressed unless opted in) before the
        #    Student also stops Student.validate_user sending its own welcome.
        needs_desk = _needs_desk(row)
        user = None
        if _needs_user(row):
            user = _ensure_user(
                email,
                first,
                last,
                row.gender,
                "System User" if needs_desk else "Website User",
                bool(self.send_welcome_emails),
            )
            row.db_set("created_user", user, update_modified=False)

        # 2. Person — the single mutation point (ADR 042).
        image_url = (
            img_map.get((row.image_filename or "").strip().lower())
            if row.image_filename
            else None
        )
        person = ensure_person(
            email,
            user=user,
            first_name=first,
            middle_name=mid,
            last_name=last,
            mobile=row.primary_mobile,
            language=row.language or self.default_language,
            country=row.country or self.default_country,
            image=image_url,
            gender=row.gender,
        )
        row.db_set("created_person", person, update_modified=False)
        _apply_person_address(person, row)

        # 3. Student — its on_update fires the oikonomos Customer bridge.
        if row.is_student:
            student = _get_or_create_student(
                person, email, first, mid, last, row, image_url
            )
            row.db_set("created_student", student, update_modified=False)
            granted.append("Student")
            if frappe.db.has_column("Student", "customer"):
                customer = frappe.db.get_value("Student", student, "customer")
                if customer:
                    row.db_set("created_customer", customer, update_modified=False)

        # 4. Instructor — requires the User from step 1.
        if row.is_instructor:
            instructor = _get_or_create_instructor(
                person, user, email, full, row.gender
            )
            row.db_set("created_instructor", instructor, update_modified=False)
            if user and frappe.db.exists("Role", "Instructor"):
                _add_role(user, "Instructor")
                granted.append("Instructor")

        # 5. Alumni Profile — requires User + full_name.
        if row.is_alumni:
            alumni = _get_or_create_alumni(person, user, email, full, row)
            row.db_set("created_alumni", alumni, update_modified=False)

        # 6. Donor — optional frappe_giving.
        if row.is_donor and frappe.db.exists("DocType", "Donor"):
            donor = _get_or_create_donor(email, full)
            link_donor(person, donor)
            row.db_set("created_donor", donor, update_modified=False)

        # 7. Permission roles.
        if user:
            for key, role in PERMISSION_ROLE_MAP.items():
                if row.get(key) and frappe.db.exists("Role", role):
                    _add_role(user, role)
                    granted.append(role)

        row.db_set(
            "assigned_roles", ", ".join(dict.fromkeys(granted)), update_modified=False
        )
        row.db_set("row_status", "Committed", update_modified=False)


# -- module-level helpers --------------------------------------------------
def _truthy(value):
    return 1 if str(value or "").strip().lower() in TRUTHY else 0


def _full_name(row):
    return (
        " ".join(filter(None, [row.first_name, row.middle_name, row.last_name])).strip()
        or None
    )


def _needs_desk(row):
    return bool(
        row.is_instructor
        or row.is_registrar
        or row.is_programchair
        or row.is_seminarymanager
    )


def _needs_user(row):
    # Everyone with a role except a pure Donor (and a bare Person) needs a User.
    return bool(_needs_desk(row) or row.is_student or row.is_alumni)


def _detect_user_conflict(email, needs_user):
    """Surface the identity conflict ensure_person would throw on: an existing
    Person for this email already linked to a *different* User."""
    if not needs_user:
        return None
    existing_person = find_person(email=email)
    if not existing_person:
        return None
    person_user = frappe.db.get_value("Person", existing_person, "user")
    if person_user and person_user != email:
        return "person_user_conflict:%s->%s" % (existing_person, person_user)
    return None


def _add_role(user, role):
    frappe.get_doc("User", user).add_roles(role)  # idempotent, saves internally


def _ensure_user(email, first_name, last_name, gender, user_type, send_welcome):
    if frappe.db.exists("User", email):
        return email
    user = frappe.new_doc("User")
    user.email = email
    user.first_name = first_name or email.split("@")[0]
    user.last_name = last_name
    if gender and frappe.db.exists("Gender", gender):
        user.gender = gender
    user.user_type = user_type
    user.send_welcome_email = 1 if send_welcome else 0
    # Bypass the per-hour user-creation throttle (frappe.core...user.
    # throttle_user_creation) — this is a bulk importer, exactly the case that
    # flag is meant for, matching Frappe's own Data Import.
    prev_in_import = frappe.flags.in_import
    frappe.flags.in_import = True
    try:
        user.insert(ignore_permissions=True)
    finally:
        frappe.flags.in_import = prev_in_import
    return user.name


def _apply_person_address(person_name, row):
    """Fill blank mailing-address fields on the Person from the row (never
    clobbers existing values, matching the spine's fill-only convention)."""
    fields = {
        "address_line_1": row.address_line_1,
        "address_line_2": row.address_line_2,
        "city": row.city,
        "state": row.state,
        "pincode": row.pincode,
    }
    current = (
        frappe.db.get_value("Person", person_name, list(fields), as_dict=True) or {}
    )
    updates = {f: v for f, v in fields.items() if v and not current.get(f)}
    if updates:
        frappe.db.set_value("Person", person_name, updates, update_modified=False)


def _get_or_create_student(person, email, first, mid, last, row, image):
    existing = frappe.db.get_value("Student", {"person": person}) or (
        frappe.db.get_value("Student", {"student_email_id": email}) if email else None
    )
    if existing:
        return existing
    student = frappe.new_doc("Student")
    student.person = person
    student.first_name = first or (email.split("@")[0] if email else "Student")
    student.middle_name = mid
    student.last_name = last
    student.student_email_id = email
    student.student_mobile_number = row.primary_mobile
    if row.gender and frappe.db.exists("Gender", row.gender):
        student.gender = row.gender
    if row.country and frappe.db.exists("Country", row.country):
        student.country = row.country
    student.image = image
    if row.date_of_birth:
        student.date_of_birth = getdate(row.date_of_birth)
    for f in ("address_line_1", "address_line_2", "city", "state", "pincode"):
        val = row.get(f)
        if val:
            student.set(f, val)
    student.joining_date = today()
    student.insert(ignore_permissions=True)
    return student.name


def _get_or_create_instructor(person, user, email, full_name, gender):
    existing = frappe.db.get_value("Instructor", {"person": person}) or (
        frappe.db.get_value("Instructor", {"user": user}) if user else None
    )
    if existing:
        return existing
    instructor = frappe.new_doc("Instructor")
    instructor.instructor_name = full_name or email
    instructor.user = user
    instructor.prof_email = email
    instructor.person = person
    if gender and frappe.db.exists("Gender", gender):
        instructor.gender = gender
    # instructor_type left blank on purpose — setting a non-Volunteer type
    # without an Employee throws (validate_payroll_link).
    instructor.insert(ignore_permissions=True)
    return instructor.name


def _get_or_create_alumni(person, user, email, full_name, row):
    if email and frappe.db.exists("Alumni Profile", email):
        return email  # autoname is the email
    existing = frappe.db.get_value("Alumni Profile", {"person": person})
    if existing:
        return existing
    alumni = frappe.new_doc("Alumni Profile")
    alumni.user = user
    alumni.email = email
    alumni.full_name = full_name or (email.split("@")[0] if email else None)
    alumni.person = person
    if row.program_completed and frappe.db.exists("Program", row.program_completed):
        alumni.program_completed = row.program_completed
    if row.class_year:
        alumni.class_year = cint(row.class_year)
    alumni.insert(ignore_permissions=True)
    return alumni.name


def _get_or_create_donor(email, donor_name):
    existing = frappe.db.get_value("Donor", {"email": email}) if email else None
    if existing:
        return existing
    donor = frappe.new_doc("Donor")
    donor.donor_name = donor_name or (email.split("@")[0] if email else "Donor")
    donor.email = email
    donor.donor_type = "Individual"
    donor.status = "Active"
    donor.insert(ignore_permissions=True)
    return donor.name


def commit_batch_async(batch_name):
    """Background commit for large batches (see on_submit)."""
    batch = frappe.get_doc("Person Import Batch", batch_name)
    batch._commit_rows()
    summary = batch._store_summary()
    batch._mark_committed()
    frappe.db.commit()
    frappe.publish_realtime(
        "person_import_complete",
        {"batch": batch.name, "summary": summary},
        user=batch.committed_by or batch.owner,
    )
