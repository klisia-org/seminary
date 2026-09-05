# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, getdate

from seminary.seminary import person_fields


class StudentApplicant(Document):
    """The one doctype that captures personal data before a Person exists.

    ADR 068 is Person-first everywhere else: a role record links to a Person
    that already exists and mirrors it read-only. This doctype is the single,
    named exception, and it is an exception on purpose — the public
    application form is served to guests, a guest has no User, and requiring
    one would put a signup wall in front of admissions (ADR 042 §4).

    So the personal fields here are *capture*, not a second home for the data:

    - `after_insert` promotes every registry attribute onto a Person;
    - `on_update` re-promotes while the applicant is still the only role
      attached, so staff fix typos where they see them;
    - admission freezes them, and the Person becomes the place to edit.

    What crosses to the Person is `person_fields.spine_kwargs`, derived from
    the registry. It used to be a hand-written argument list, which is exactly
    how the address and gender an applicant typed never reached the spine.
    """

    def before_insert(self):
        if self.ds2 and self.ds_body:
            return
        ds = frappe.db.get_value(
            "Doctrinal Statement",
            {"active": 1, "use_in_student_admission": 1, "docstatus": 1},
            ["name", "doctrinal_statement"],
            as_dict=True,
            order_by="creation desc",
        )
        if not ds:
            return
        if not self.ds2:
            self.ds2 = ds.name
        if not self.ds_body:
            self.ds_body = ds.doctrinal_statement

    def autoname(self):
        from frappe.model.naming import set_name_by_naming_series

        if self.program:
            program_naming_series = frappe.db.get_value(
                "Program", self.program, "applicant_naming_series"
            )
            if program_naming_series:
                self.naming_series = program_naming_series

        set_name_by_naming_series(self)

    def validate(self):
        self.set_title()
        self.validate_dates()
        self.validate_term()
        self.set_access_key()
        person_fields.assert_capture_complete(self)
        self.freeze_captured_fields()

    def freeze_captured_fields(self):
        """Once admitted, the Person owns the personal data — not this record.

        The JSON carries `read_only_depends_on` for the same set, but
        `read_only` is a UI hint that Frappe does not enforce server-side, so
        on its own it would give a test something to assert and an API client
        nothing to trip over. After admission `_repromote_to_person` stops
        pushing, so an edit here would not diverge loudly — it would sit on the
        applicant looking authoritative while the Person said otherwise.
        """
        if self.is_new() or self.application_status != "Admitted":
            return
        before = self.get_doc_before_save()
        if not before or before.application_status != "Admitted":
            # The save that *performs* the admission may legitimately carry
            # last-minute corrections; it is the ones afterwards that are late.
            return
        # `cstr` on both sides, not a bare `!=`: a Date read back from the
        # database is a `datetime.date` while the same field on the document in
        # hand is still the string the form sent, so comparing them directly
        # reports every admitted applicant as edited and refuses saves that
        # changed nothing.
        changed = [
            fieldname
            for fieldname in person_fields.capture_fields(self.doctype)
            if cstr(self.get(fieldname)) != cstr(before.get(fieldname))
        ]
        if changed:
            meta = frappe.get_meta(self.doctype)
            labels = [
                _(meta.get_field(f).label or f) for f in changed if meta.get_field(f)
            ]
            frappe.throw(
                _(
                    "{0} cannot be changed on an admitted application. "
                    "Edit the Person record ({1}) instead — this application is "
                    "the record of what was submitted."
                ).format(", ".join(labels), self.person or _("not yet linked")),
                title=_("Application is admitted"),
            )

    def set_access_key(self):
        """An unguessable handle for the public payment page.

        `/applicant-payment` and the guest-callable
        `api.get_application_payment_url` used to take a bare docname, so
        anyone could walk applicants and pull their payment link. That was
        already true of `{academic_term}-{first_name}-{###}`; ADR 068 phase 3's
        sequential `APP-.#####` makes it trivial. Generated in `validate` so it
        is present on the document the web form returns to the browser, which
        is the only moment the applicant can be handed it.
        """
        if not self.access_key:
            self.access_key = frappe.generate_hash(length=32)

    def set_title(self):
        self.title = " ".join(
            filter(None, [self.first_name, self.middle_name, self.last_name])
        )

    def validate_dates(self):
        if self.date_of_birth and getdate(self.date_of_birth) >= getdate():
            frappe.throw(_("Date of Birth cannot be greater than today."))

    def validate_term(self):
        if self.academic_year and self.academic_term:
            actual_academic_year = frappe.db.get_value(
                "Academic Term", self.academic_term, "academic_year"
            )
            if actual_academic_year != self.academic_year:
                frappe.throw(
                    _("Academic Term {0} does not belong to Academic Year {1}").format(
                        self.academic_term, self.academic_year
                    )
                )

    def after_insert(self):
        # Person spine seam (ADR 042): public intake captures contact fields
        # here (a guest can't write Person directly) and promotes them on
        # insert — no User exists yet.
        self._promote_to_person()

        # Application-fee Sales Invoice(s) are raised on insert (not on submit:
        # web-form applicants stay at docstatus=0, so on_submit never fires) by
        # the oikonomos bridge, which subscribes to this doctype's after_insert.
        # With no bridge installed, applying is free.

    def on_update(self):
        self._repromote_to_person()
        self._flag_requirement_review()

    def _flag_requirement_review(self):
        """ADR 058: when an applicant self-reports a circumstance needing
        leveling / advanced-standing review, raise an open ToDo per Registrar so
        they build the leveling plan on the new enrollment. Idempotent."""
        choice = self.get("requests_requirement_review")
        if not choice or choice == "None":
            return
        from seminary.seminary.cei_lifecycle import _registrar_emails

        for user in _registrar_emails():
            if frappe.db.exists(
                "ToDo",
                {
                    "allocated_to": user,
                    "reference_type": "Student Applicant",
                    "reference_name": self.name,
                    "status": "Open",
                },
            ):
                continue
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "owner": user,
                    "allocated_to": user,
                    "reference_type": "Student Applicant",
                    "reference_name": self.name,
                    "description": _(
                        "Applicant {0} requested requirement review ({1}). "
                        "Plan leveling / advanced standing on their enrollment."
                    ).format(self.name, choice),
                }
            ).insert(ignore_permissions=True)

    def _promote_to_person(self):
        from seminary.seminary import person as person_spine

        person = person_spine.ensure_person(
            email=self.student_email_id,
            **person_fields.spine_kwargs(self),
        )
        self.db_set("person", person, update_modified=False)

    def _repromote_to_person(self):
        """While the applicant is the sole role attached (no User yet, not
        Admitted), the intake form stays the authoritative editor: staff fix
        typos where they see them and the edit re-promotes last-write-wins
        (ADR 042). From admission on, edits happen on the Person."""
        from seminary.seminary import person as person_spine

        if not self.person or self.application_status == "Admitted":
            return
        if frappe.db.get_value("Person", self.person, "user"):
            return
        person_spine.update_person(
            self.person,
            email=self.student_email_id,
            overwrite=True,
            **person_fields.spine_kwargs(self),
        )

    def on_payment_authorized(self, *args, **kwargs):
        self.db_set("paid", 1)
