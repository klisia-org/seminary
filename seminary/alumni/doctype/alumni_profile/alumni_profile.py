import frappe
from frappe import _
from frappe.model.document import Document


def class_year_for(academic_year=None, conclusion_date=None):
    """The year alumni put after "Class of".

    Schools name a class by the academic year it finished, not by the calendar
    year on the certificate — so an autumn graduate of 2017-2018 is Class of
    2018. Taking `.year` off their December conclusion date, which is what this
    used to do, called them Class of 2017.

    `Academic Year.name` is free-form Data (`2017-2018`, or `DEMO-2025-26` on a
    demo site), so the number comes from that year's `year_end_date` rather
    than from parsing its name. The conclusion date is the fallback for an
    alumnus imported without an academic year at all.
    """
    from frappe.utils import getdate

    if academic_year:
        end = frappe.db.get_value("Academic Year", academic_year, "year_end_date")
        if end:
            return getdate(end).year
    if conclusion_date:
        return getdate(conclusion_date).year
    return None


class AlumniProfile(Document):
    def validate(self):
        self._resolve_person()
        self._set_class_years()

    def _set_class_years(self):
        """Derive `class_year` on every graduation row, however it got there.

        It used to be computed only in `record_graduation`, the path from a
        completed Program Enrollment. A registrar adding a row by hand — an
        alumnus of another institution, or one whose enrollment predates this
        system — got nothing, and `class_year` is an `Int`, which Frappe stores
        `NOT NULL DEFAULT 0`. So the field did not read as empty; it read as
        **Class of 0**, a plausible-looking number that no screen would flag.
        (The same shape as the geocoded `0.0, 0.0` in ADR 068 §7: an integer
        column has no way to say "not known".)

        Recomputed whenever it *can* be, rather than filled-if-blank, because
        the row's academic year is editable and the class year is derived from
        it — a stale derived value is the same defect wearing a different face.

        But a row with nothing to derive from is not necessarily a broken row:
        an alumnus imported from before this system may have a class year and
        no academic year or conclusion date at all, which is exactly what the
        old flat `class_year` column held and what the ADR 069 migration
        carried across. Those keep what they have. Only a row that can neither
        derive a year nor show a stored one is refused — that is the one that
        would display Class of 0.
        """
        for row in self.graduations:
            derived = class_year_for(row.academic_year, row.conclusion_date)
            if derived:
                row.class_year = derived
            elif not row.class_year:
                frappe.throw(
                    _(
                        "Row {0}: a graduation needs an academic year or a "
                        "conclusion date — the class year is derived from one "
                        "of them, and without either it would read as Class of 0."
                    ).format(row.idx)
                )

    def record_graduation(self, program_enrollment, conclusion_date=None):
        """Add a completed program, unless it is already recorded.

        Returns True when the row was already there, so the caller can skip a
        pointless save. Keyed on the enrollment where there is one, because a
        person can legitimately complete the *same* program twice over a
        career — a second MA in a different emphasis is a different enrollment,
        not a duplicate row (ADR 069).
        """
        pe = program_enrollment
        if isinstance(pe, str):
            pe = frappe.get_doc("Program Enrollment", pe)

        for row in self.graduations:
            if pe.name and row.program_enrollment == pe.name:
                return True

        conclusion_date = conclusion_date or pe.date_of_conclusion
        academic_year = (
            frappe.db.get_value("Academic Term", pe.academic_term, "academic_year")
            if pe.academic_term
            else None
        )
        # `class_year` is deliberately not set here: `_set_class_years` derives
        # it for every row on save, so this path and a hand-added row get the
        # same answer from the same code. Computing it in both places is how
        # the Desk path came to have no answer at all.
        self.append(
            "graduations",
            {
                "program": pe.program,
                "program_enrollment": pe.name,
                "academic_year": academic_year,
                "conclusion_date": conclusion_date,
            },
        )
        return False

    def _resolve_person(self):
        """Person spine seam (ADR 042). The same human's Student record (if
        any) already created the Person and linked the same User, so
        ensure_person resolves to it; non-student alumni (honorary, transfer,
        board) get one created from their User."""
        from seminary.seminary import person_fields

        # Created against an existing Person (`intake.make_alumni_profile`),
        # and `person` is reqd, so there is nothing to resolve. `full_name`,
        # `email` and `image` are `fetch_from person.*` mirrors since ADR 068
        # phase 4 — `image` used to come from the Student record, so an alumnus
        # who was never a student here had no photo at all.
        if self.person:
            person_fields.assert_reachable(frappe.get_doc("Person", self.person))

    # `_sync_email_from_user` and `_sync_full_name_from_student` are gone.
    #
    # The first threw when `email` differed from the linked User's login,
    # which directly contradicts ADR 042: an email change deliberately does
    # *not* rename the User, so drift between the two is expected and the
    # throw would have made a perfectly valid profile unsaveable. The second
    # copied the name off the Student — a mirror of a mirror, and empty for an
    # alumnus who was never a student here. Both are now one `fetch_from
    # person.*` (ADR 068 phase 4).
