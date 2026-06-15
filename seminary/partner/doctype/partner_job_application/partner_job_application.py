# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, strip_html, today

FULL_AGREEMENT = "I agree completely, without reservations"


class PartnerJobApplication(Document):
    def before_validate(self):
        self._resolve_applicant_from_session()
        self._set_contact_from_person()

    def validate(self):
        self._default_resume_from_person()
        self._prevent_duplicate()
        self._check_eligibility()
        self._validate_submission()
        self._stamp_submission_date()
        self._compute_average_rating()

    def _stamp_submission_date(self):
        """Record when the application left Draft (was submitted); drives the
        partner's applicant list ordering."""
        if self.status != "Draft" and not self.submission_date:
            self.submission_date = now_datetime()

    def _validate_submission(self):
        """Completeness rules enforced only when the application is actually
        submitted — a Draft may be incomplete while the applicant is still
        discerning."""
        if self.status == "Draft":
            return
        if not self.cover_letter or not strip_html(self.cover_letter).strip():
            frappe.throw(
                _("Please write a cover letter before submitting your application.")
            )

        requires = frappe.db.get_value(
            "Partner Job Opening", self.job_opening, "require_doctrinal_alignment"
        )
        if requires and not self.doctrinal_alignment:
            frappe.throw(
                _(
                    "Please share your response to the organization's doctrinal statement "
                    "before submitting."
                )
            )
        if (
            self.doctrinal_alignment
            and self.doctrinal_alignment != FULL_AGREEMENT
            and not (self.alignment_explanation or "").strip()
        ):
            frappe.throw(
                _("Please explain your points of disagreement or reservation.")
            )

    def _set_contact_from_person(self):
        """Snapshot the applicant's contact onto the application, preferring their
        application-specific email/phone and falling back to their primary ones,
        so the partner reaches them on the right channel."""
        if not self.applicant:
            return
        p = frappe.db.get_value(
            "Person",
            self.applicant,
            [
                "full_name",
                "primary_email",
                "primary_mobile",
                "preferred_application_email",
                "preferred_application_phone",
            ],
            as_dict=True,
        )
        if not p:
            return
        self.primary_email = p.preferred_application_email or p.primary_email
        self.primary_mobile = p.preferred_application_phone or p.primary_mobile

    def _resolve_applicant_from_session(self):
        """Safety net for portal-created applications that omit the applicant —
        resolve it from the logged-in user's Person spine (ADR 042). The portal
        apply endpoint sets it explicitly; this covers any other caller."""
        if self.applicant:
            return
        person = frappe.db.get_value("Person", {"user": frappe.session.user}, "name")
        if person:
            self.applicant = person

    def on_update(self):
        self._sync_opening_vacancies()
        self._ensure_resume_accessible()

    def on_trash(self):
        self._sync_opening_vacancies()

    def _ensure_resume_accessible(self):
        """Partners read the résumé through their application's read permission, so
        a File row for it must hang off this application (ADR 043). A fresh upload
        (unattached) is re-pointed here; a résumé inherited from the Person gets an
        additional File row — the physical file is shared, never copied."""
        if self.status == "Draft" or not self.resume:
            return
        if frappe.db.exists(
            "File",
            {
                "file_url": self.resume,
                "attached_to_doctype": "Partner Job Application",
                "attached_to_name": self.name,
            },
        ):
            return
        src = frappe.db.get_value(
            "File",
            {"file_url": self.resume},
            ["name", "file_name", "is_private", "attached_to_name"],
            as_dict=True,
        )
        if not src:
            return
        if not src.attached_to_name:
            frappe.db.set_value(
                "File",
                src.name,
                {
                    "attached_to_doctype": "Partner Job Application",
                    "attached_to_name": self.name,
                    "attached_to_field": "resume",
                },
            )
        else:
            frappe.get_doc(
                {
                    "doctype": "File",
                    "file_url": self.resume,
                    "file_name": src.file_name,
                    "is_private": src.is_private,
                    "attached_to_doctype": "Partner Job Application",
                    "attached_to_name": self.name,
                    "attached_to_field": "resume",
                }
            ).insert(ignore_permissions=True)

    def _default_resume_from_person(self):
        """Reuse the applicant's stored resume so people don't re-upload it for
        every application. The field stays editable for a per-application override."""
        if not self.resume and self.applicant:
            self.resume = frappe.db.get_value("Person", self.applicant, "resume")

    def _prevent_duplicate(self):
        """One application per person per opening."""
        duplicate = frappe.db.exists(
            "Partner Job Application",
            {
                "job_opening": self.job_opening,
                "applicant": self.applicant,
                "name": ("!=", self.name),
            },
        )
        if duplicate:
            frappe.throw(
                _("{0} has already applied to this job opening ({1}).").format(
                    frappe.bold(self.full_name or self.applicant), duplicate
                )
            )

    def _check_eligibility(self):
        """Respect the opening's audience flags. An opening with no audience flag
        is unrestricted; one that sets open_students and/or open_alumni only
        accepts applicants who hold that role. New applications to a closed
        opening are rejected."""
        opening = frappe.db.get_value(
            "Partner Job Opening",
            self.job_opening,
            ["open_students", "open_alumni", "status"],
            as_dict=True,
        )
        if not opening:
            return

        # Block only when *entering* submission on a closed opening — editing an
        # already-submitted application (e.g. a partner adding a review or moving
        # the status) must not trip the closed guard.
        before = self.get_doc_before_save()
        status_before = before.status if before else None
        entering_submission = self.status != "Draft" and (
            self.is_new() or status_before == "Draft"
        )
        if opening.status == "Closed" and entering_submission:
            frappe.throw(
                _("This job opening is closed and no longer accepting applications.")
            )

        if not (opening.open_students or opening.open_alumni):
            return

        is_student = bool(frappe.db.exists("Student", {"person": self.applicant}))
        is_alumni = bool(frappe.db.exists("Alumni Profile", {"person": self.applicant}))
        allowed = (opening.open_students and is_student) or (
            opening.open_alumni and is_alumni
        )
        if not allowed:
            audiences = []
            if opening.open_students:
                audiences.append(_("students"))
            if opening.open_alumni:
                audiences.append(_("alumni"))
            frappe.throw(
                _(
                    "This opening is limited to {0}; {1} is not eligible to apply."
                ).format(
                    _(" and ").join(audiences),
                    frappe.bold(self.full_name or self.applicant),
                )
            )

    def _compute_average_rating(self):
        ratings = [r.rating for r in self.reviews if r.rating]
        self.average_rating = sum(ratings) / len(ratings) if ratings else 0

    def _sync_opening_vacancies(self):
        """Keep the opening's read-only `vacancies` (remaining positions) in sync
        with the count of Accepted applications, and auto-close when full. We only
        auto-close — never auto-reopen — so a manually closed opening stays closed."""
        if not self.job_opening:
            return
        opening = frappe.db.get_value(
            "Partner Job Opening",
            self.job_opening,
            ["planned_vacancies", "status"],
            as_dict=True,
        )
        if not opening:
            return

        accepted = frappe.db.count(
            "Partner Job Application",
            {"job_opening": self.job_opening, "status": "Accepted"},
        )
        remaining = max((opening.planned_vacancies or 0) - accepted, 0)
        updates = {"vacancies": remaining}
        if remaining == 0 and opening.status == "Open":
            updates["status"] = "Closed"
            updates["closed_on"] = today()
        frappe.db.set_value("Partner Job Opening", self.job_opening, updates)
