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

    def record_graduation(self, program_enrollment, conclusion_date=None):
        """Add a completed program, unless it is already recorded.

        Returns True when the row was already there, so the caller can skip a
        pointless save. Keyed on the enrollment where there is one, because a
        person can legitimately complete the *same* program twice over a
        career — a second MA in a different emphasis is a different enrollment,
        not a duplicate row (ADR 069).
        """
        from frappe.utils import getdate

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
        self.append(
            "graduations",
            {
                "program": pe.program,
                "program_enrollment": pe.name,
                "academic_year": academic_year,
                "conclusion_date": conclusion_date,
                "class_year": class_year_for(academic_year, conclusion_date),
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
