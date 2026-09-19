# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p007 §2.10 / p008a G6: every whitelisted function **in the app** is
classified, and the classification is enforced.

p005a A06-3: this walk used to name nine modules holding 148 of the app's ~460
whitelisted functions, so its guarantee did not reach 312 endpoints — and every
finding in p005a §4.1/§4.2 but one lived in that blind spot. The walk now
discovers every module under ``seminary.`` and requires each endpoint to be
classified.

Endpoints not yet triaged sit in ``PENDING_CLASSIFICATION`` with
``MAX_PENDING`` as a ratchet: the count may only go down, so the debt is
explicit, enforced, and cannot grow. A NEW endpoint is never pending — it has to
be classified before the branch is green, which is the property that matters.

* ``STAFF_ONLY``: a Student receives ``PermissionError``; a user holding the
  school roles is not stopped by the gate (any other exception is a missing
  fixture).
* ``STUDENT_ALLOWED``: a student may call it; those that take a target are
  checked in ``test_p007_docperms`` / the potestas matrix, not here.
* ``GUEST_ALLOWED``: reachable without a session.

A whitelisted function that appears in none of the lists fails the suite, so a
new endpoint has to be classified before the branch is green.
"""

import inspect

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.tests.test_p006_api import _make_user

# Modules whose endpoints have been triaged. Everything discovered outside these
# is allowed to sit in PENDING_CLASSIFICATION until its module is reviewed.
REVIEWED_MODULES = (
    "seminary.seminary.api",
    "seminary.seminary.utils",
    "seminary.seminary.doctype.quiz.quiz",
    "seminary.seminary.doctype.exam_submission.exam_submission",
    "seminary.seminary.doctype.assignment_submission.assignment_submission",
    "seminary.seminary.doctype.withdrawal_request.withdrawal_request",
    "seminary.seminary.student_standing",
    "seminary.seminary.doctype.student_attendance_tool.student_attendance_tool",
    "seminary.seminary.doctype.culminating_project.culminating_project",
    "seminary.seminary.disciplinary",
)

GUEST_ALLOWED = {
    "seminary.seminary.api.get_translations",
    "seminary.seminary.api.get_user_info",
    "seminary.seminary.api.get_school_abbr_logo",
    "seminary.seminary.api.get_doctrinal_statement",
    "seminary.seminary.api.get_application_payment_url",
    "seminary.seminary.api.get_default_phone_country",
    "seminary.seminary.api.active_term",
    # --- found by the widened walk (p008a G6); each verified in p005a §4.2 A06-6
    # token-gated (secrets.token_hex(32), compare_digest since p008a G3b); the token is the whole control
    "seminary.seminary.calendar.course_ics",
    # inbound provider callback, shared secret under compare_digest
    "seminary.seminary.comms.webhook",
    # @rate_limit 60/60s ip_based; billable upstream
    "seminary.seminary.integrations.geocoding.suggest_addresses",
    # @rate_limit 30/60s ip_based; billable upstream
    "seminary.seminary.integrations.geocoding.resolve_address",
    # recommendation-letter token + 90-day expiry
    "seminary.seminary.recommender.get_request",
    # same token; p005a A06-6: no rate limit, creates File docs -- Phase 3
    "seminary.seminary.recommender.upload_attachment",
    # same token; only accepts an attachment upload_attachment made for that letter
    "seminary.seminary.recommender.submit_letter",
    # @rate_limit 60/60s ip_based; static rules, says nothing about records on file
    "seminary.seminary.tax_ids.get_tax_id_rule",
    # @rate_limit 30/60s ip_based; format check only
    "seminary.seminary.tax_ids.check_tax_id",
    # resolves through a readable File row; content-hash keys are not enumerable (p004)
    "seminary.storage.api.download_file",
}

STUDENT_ALLOWED = {
    # lesson discussions: whoever reads the lesson posts; own-reply rules inside
    "seminary.seminary.api.reply_to_discussion_submission",
    "seminary.seminary.utils.create_discussion_topic",
    "seminary.seminary.utils.add_discussion_reply",
    "seminary.seminary.utils.edit_discussion_reply",
    "seminary.seminary.utils.delete_discussion_reply",
    # api.py — session-scoped, no target, or scoped by p007 §2.5
    "seminary.seminary.api.get_student_group",
    "seminary.seminary.api.get_student_groups_simple",
    "seminary.seminary.api.get_discussion_submissions",
    "seminary.seminary.api.get_user_discussion_submission",
    "seminary.seminary.api.get_user_discussion_replies",
    "seminary.seminary.api.add_grading_comment",
    "seminary.seminary.api.get_grading_comments",
    "seminary.seminary.api.get_discussion_dashboard",
    "seminary.seminary.api.get_enabled_languages",
    "seminary.seminary.api.set_user_language",
    "seminary.seminary.api.get_file_info",
    "seminary.seminary.api.get_instructor_info",
    "seminary.seminary.api.save_student_profile",
    "seminary.seminary.api.save_instructor_profile",
    "seminary.seminary.api.get_student_programs",
    "seminary.seminary.api.course_enroll",
    "seminary.seminary.api.get_student_enrollments_for_term",
    "seminary.seminary.api.cancel_draft_enrollment",
    "seminary.seminary.api.cancel_unpaid_enrollment",
    "seminary.seminary.api.get_program_audit",
    "seminary.seminary.api.create_graduation_request",
    "seminary.seminary.api.get_pe_unpaid_invoices",
    "seminary.seminary.api.get_available_courses_categorized",
    "seminary.seminary.api.get_student_invoices",
    "seminary.seminary.api.courses_for_student",
    "seminary.seminary.api.get_pgmenrollments",
    "seminary.seminary.api.mark_lesson_progress",
    "seminary.seminary.api.get_student_info",
    "seminary.seminary.api.get_announcements",
    "seminary.seminary.api.GradeableDiscussion",
    "seminary.seminary.api.GradeableQuiz",
    "seminary.seminary.api.GradeableExam",
    "seminary.seminary.api.GradeableAssignment",
    "seminary.seminary.api.get_submission_comments",
    "seminary.seminary.api.update_submission_comment",
    "seminary.seminary.api.delete_submission_comment",
    "seminary.seminary.api.get_invoice_payment_url",
    "seminary.seminary.api.get_student_balance_payment_url",
    "seminary.seminary.api.get_student_partial_balance_payment_url",
    # utils.py
    "seminary.seminary.utils.get_courses_for_student",
    "seminary.seminary.utils.get_courses",
    "seminary.seminary.utils.get_instructors",
    "seminary.seminary.utils.get_instructor",
    "seminary.seminary.utils.get_course_outline",
    "seminary.seminary.utils.get_course_title",
    "seminary.seminary.utils.get_course_details",
    "seminary.seminary.utils.get_roster",
    "seminary.seminary.utils.get_lesson",
    "seminary.seminary.utils.get_question_details",
    "seminary.seminary.utils.get_all_questions_details",
    "seminary.seminary.utils.get_assessments",
    "seminary.seminary.utils.get_assessment_due_date",
    "seminary.seminary.utils.get_student_course_status",
    "seminary.seminary.utils.get_discussion_topics",
    "seminary.seminary.utils.get_discussion_replies",
    "seminary.seminary.utils.ensure_single_topic",
    "seminary.seminary.utils.get_missingassessments",
    # quiz.py (taking a quiz)
    "seminary.seminary.doctype.quiz.quiz.quiz_summary",
    "seminary.seminary.doctype.quiz.quiz.get_last_submission",
    "seminary.seminary.doctype.quiz.quiz.check_answer",
    # exam / assignment submission (own work)
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_draft",
    "seminary.seminary.doctype.exam_submission.exam_submission.submit_exam",
    "seminary.seminary.doctype.exam_submission.exam_submission.get_exam_grading_comments",
    "seminary.seminary.doctype.exam_submission.exam_submission.add_exam_grading_comment",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.upload_assignment",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.get_assignment",
}

STAFF_ONLY = {
    # --- seminary.seminary.disciplinary (p008a G6): staff or a course instructor.
    # compute_occurrence_number / preview_recommendation / suggest_actions gated
    # here (p005a A01-16); the rest were already gated.
    "seminary.seminary.disciplinary.compute_occurrence_number",
    "seminary.seminary.disciplinary.list_portal_reasons",
    "seminary.seminary.disciplinary.preview_recommendation",
    "seminary.seminary.disciplinary.record_incident_action",
    "seminary.seminary.disciplinary.report_incident",
    "seminary.seminary.disciplinary.suggest_actions",
    # api.py
    "seminary.seminary.api.get_student_groups",
    "seminary.seminary.api.get_discussion_submission_summary",
    "seminary.seminary.api.save_discussion_submission_grade",
    "seminary.seminary.api.get_quiz_dashboard",
    "seminary.seminary.api.get_exam_dashboard",
    "seminary.seminary.api.get_assignment_dashboard",
    "seminary.seminary.api.save_course",
    "seminary.seminary.api.get_virtual_meetings",
    "seminary.seminary.api.add_virtual_meeting",
    "seminary.seminary.api.remove_virtual_meeting",
    "seminary.seminary.api.roll_students",
    "seminary.seminary.api.check_schedule_conflicts",
    "seminary.seminary.api.resolve_schedule_conflict",
    "seminary.seminary.api.enroll_student",
    "seminary.seminary.api.mark_attendance",
    "seminary.seminary.api.get_course_schedule_events",
    "seminary.seminary.api.save_course_assessment",
    "seminary.seminary.api.insert_cs_assessment",
    "seminary.seminary.api.get_course_rosters",
    "seminary.seminary.api.grade_thisstudent",
    "seminary.seminary.api.fgrade_this_std",
    "seminary.seminary.api.fail_for_absence",
    "seminary.seminary.api.undo_fail_for_absence",
    "seminary.seminary.api.send_selected_grades",
    "seminary.seminary.api.send_grades",
    "seminary.seminary.api.course_event",
    "seminary.seminary.api.upsert_chapter",
    "seminary.seminary.api.delete_chapter",
    "seminary.seminary.api.delete_lesson",
    "seminary.seminary.api.delete_documents",
    "seminary.seminary.api.update_lesson_index",
    "seminary.seminary.api.update_chapter_index",
    "seminary.seminary.api.add_submission_comment",
    "seminary.seminary.api.preview_announcement_recipients",
    "seminary.seminary.api.generate_announcement_labels",
    "seminary.seminary.api.announcement_letters_pdf",
    "seminary.seminary.api.preview_announcement_letter",
    "seminary.seminary.api.room_search",
    "seminary.seminary.api.run_plagiarism_check",
    "seminary.seminary.api.get_plagiarism_result",
    "seminary.seminary.api.get_plagiarism_match_detail",
    # utils.py
    "seminary.seminary.utils.get_timezones",
    "seminary.seminary.utils.get_all_users",
    "seminary.seminary.utils.get_lesson_creation_details",
    "seminary.seminary.utils.get_gradebook",
    "seminary.seminary.utils.missing_exams",
    "seminary.seminary.utils.get_course_exams",
    "seminary.seminary.utils.get_course_meetingdates",
    "seminary.seminary.utils.get_assessments_tograde",
    "seminary.seminary.utils.get_student_groups",
    "seminary.seminary.utils.create_student_group",
    # controllers
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_grade",
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_comment",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.grade_assignment",
    "seminary.seminary.doctype.withdrawal_request.withdrawal_request.initiate_program_separation",
    "seminary.seminary.student_standing.lift_hold",
    "seminary.seminary.doctype.student_attendance_tool.student_attendance_tool.get_student_attendance_records",
    "seminary.seminary.doctype.culminating_project.culminating_project.resnapshot_milestones",
}

# Whitelisted functions in the walked modules that are neither student-facing
# nor a plain staff gate: they carry their own ownership rule (the culminating
# project's student/advisor checks) and are covered by their own test module.
OWN_RULE = {
    # disciplinary: these two carry their own rule rather than a throw -- an
    # unauthorized caller gets [] (fail-closed, no leak), so they are not
    # STAFF_ONLY in this test's "must raise PermissionError" sense.
    "seminary.seminary.disciplinary.list_course_enrollments",
    "seminary.seminary.disciplinary.list_pending_incidents",
} | {
    "seminary.seminary.doctype.culminating_project.culminating_project." + n
    for n in (
        "record_signoff",
        "add_committee_member",
        "add_submission",
        "assign_advisor",
        "create_milestone_event",
        "enroll_in_project_course",
        "get_culminating_project",
        "get_my_culminating_projects",
        "remove_committee_member",
        "review_submission",
        "save_abstract",
    )
}

# Endpoints discovered by the widened walk (p008a G6) that have not yet been
# triaged. This is debt, not an allow-list: MAX_PENDING is a ratchet, and
# test_reviewed_modules_have_no_pending stops a reviewed module regrowing it.
# Shrink this by reviewing a module, classifying its endpoints into the sets
# above, adding it to REVIEWED_MODULES and lowering MAX_PENDING.
PENDING_CLASSIFICATION = {
    # seminary.alumni.api (6)
    "seminary.alumni.api.directory_search",
    "seminary.alumni.api.get_directory_profile",
    "seminary.alumni.api.get_my_profile",
    "seminary.alumni.api.mark_as_alumni",
    "seminary.alumni.api.send_directory_message",
    "seminary.alumni.api.update_profile",
    # seminary.demo (2)
    "seminary.demo.install_demo",
    "seminary.demo.remove_demo",
    # seminary.partner.api (15)
    "seminary.partner.api.apply_to_job",
    "seminary.partner.api.create_partner_organization",
    "seminary.partner.api.discard_draft",
    "seminary.partner.api.get_apply_context",
    "seminary.partner.api.get_job_opening",
    "seminary.partner.api.get_job_openings",
    "seminary.partner.api.get_my_applications",
    "seminary.partner.api.get_my_career_profile",
    "seminary.partner.api.get_my_organizations",
    "seminary.partner.api.get_partner_directory",
    "seminary.partner.api.get_partner_organization",
    "seminary.partner.api.get_partner_types",
    "seminary.partner.api.list_skill_tags",
    "seminary.partner.api.update_my_career_profile",
    "seminary.partner.api.withdraw_application",
    # seminary.partner.doctype.internship_application.internship_application (1)
    "seminary.partner.doctype.internship_application.internship_application.enroll_in_internship_course",
    # seminary.partner.internship_api (13)
    "seminary.partner.internship_api.apply_to_internship",
    "seminary.partner.internship_api.delete_hours",
    "seminary.partner.internship_api.discard_draft",
    "seminary.partner.internship_api.get_feedback",
    "seminary.partner.internship_api.get_internship",
    "seminary.partner.internship_api.get_internships",
    "seminary.partner.internship_api.get_my_internship",
    "seminary.partner.internship_api.get_my_internships",
    "seminary.partner.internship_api.list_hours",
    "seminary.partner.internship_api.log_hours",
    "seminary.partner.internship_api.save_requirement_student",
    "seminary.partner.internship_api.submit_feedback",
    "seminary.partner.internship_api.withdraw_application",
    # seminary.partner.internship_portal (18)
    "seminary.partner.internship_portal.add_hours",
    "seminary.partner.internship_portal.get_internship_application",
    "seminary.partner.internship_portal.get_internship_posting",
    "seminary.partner.internship_portal.get_org_supervisors",
    "seminary.partner.internship_portal.get_supervisor_evaluation",
    "seminary.partner.internship_portal.list_hours",
    "seminary.partner.internship_portal.list_internship_applications",
    "seminary.partner.internship_portal.list_internship_postings",
    "seminary.partner.internship_portal.list_internship_types",
    "seminary.partner.internship_portal.list_placements",
    "seminary.partner.internship_portal.list_requirements",
    "seminary.partner.internship_portal.save_internship_posting",
    "seminary.partner.internship_portal.save_placement",
    "seminary.partner.internship_portal.save_requirement_partner",
    "seminary.partner.internship_portal.save_supervisor_evaluation",
    "seminary.partner.internship_portal.set_internship_application_status",
    "seminary.partner.internship_portal.terminate_placement",
    "seminary.partner.internship_portal.verify_hours",
    # seminary.partner.portal (16)
    "seminary.partner.portal.create_contact",
    "seminary.partner.portal.get_application",
    "seminary.partner.portal.get_job_posting",
    "seminary.partner.portal.get_my_org",
    "seminary.partner.portal.get_people",
    "seminary.partner.portal.get_skill_tags",
    "seminary.partner.portal.list_applications",
    "seminary.partner.portal.list_job_postings",
    "seminary.partner.portal.list_locations",
    "seminary.partner.portal.list_my_orgs",
    "seminary.partner.portal.save_contact_log",
    "seminary.partner.portal.save_job_posting",
    "seminary.partner.portal.save_location",
    "seminary.partner.portal.save_review",
    "seminary.partner.portal.set_application_status",
    "seminary.partner.portal.update_org",
    # seminary.partner.queries (1)
    "seminary.partner.queries.org_contact_person_query",
    # seminary.seminary.address_verification (1)
    "seminary.seminary.address_verification.request_verification",
    # seminary.seminary.attendance (1)
    "seminary.seminary.attendance.get_course_attendance_standings",
    # seminary.seminary.calendar (1)
    "seminary.seminary.calendar.get_calendar_instructions",
    # seminary.seminary.cbe (1)
    "seminary.seminary.cbe.enrollment_mentor_panel",
    # seminary.seminary.cbe_api (24)
    "seminary.seminary.cbe_api.delete_development_note",
    "seminary.seminary.cbe_api.get_activity_grading_panel",
    "seminary.seminary.cbe_api.get_cbe_gradebook",
    "seminary.seminary.cbe_api.get_competency_context",
    "seminary.seminary.cbe_api.get_competency_profile",
    "seminary.seminary.cbe_api.get_competency_roster",
    "seminary.seminary.cbe_api.get_competency_transcript",
    "seminary.seminary.cbe_api.get_competency_worklist",
    "seminary.seminary.cbe_api.get_development_arc",
    "seminary.seminary.cbe_api.get_development_notes",
    "seminary.seminary.cbe_api.get_development_plan",
    "seminary.seminary.cbe_api.get_mentees",
    "seminary.seminary.cbe_api.get_outline_competencies",
    "seminary.seminary.cbe_api.get_self_assessment",
    "seminary.seminary.cbe_api.get_student_competency_detail",
    "seminary.seminary.cbe_api.get_student_competency_overview",
    "seminary.seminary.cbe_api.review_development_plan",
    "seminary.seminary.cbe_api.save_activity_grade",
    "seminary.seminary.cbe_api.save_assessment_competency_config",
    "seminary.seminary.cbe_api.save_development_note",
    "seminary.seminary.cbe_api.save_development_plan",
    "seminary.seminary.cbe_api.save_mentor_assessment",
    "seminary.seminary.cbe_api.save_self_assessment",
    "seminary.seminary.cbe_api.set_result_override",
    # seminary.seminary.chapel (2)
    "seminary.seminary.chapel.check_in",
    "seminary.seminary.chapel.get_chapel_status",
    # seminary.seminary.comms (21)
    "seminary.seminary.comms.add_my_address",
    "seminary.seminary.comms.compose_communication",
    "seminary.seminary.comms.contact_instructor",
    "seminary.seminary.comms.delete_my_address",
    "seminary.seminary.comms.get_conversation",
    "seminary.seminary.comms.get_inbox_conversations",
    "seminary.seminary.comms.get_inbox_unread_count",
    "seminary.seminary.comms.get_my_communication_preferences",
    "seminary.seminary.comms.get_my_inbox",
    "seminary.seminary.comms.get_my_messaging_scope",
    "seminary.seminary.comms.get_my_unread_count",
    "seminary.seminary.comms.get_person_timeline",
    "seminary.seminary.comms.mark_all_inbox_read",
    "seminary.seminary.comms.mark_conversation_read",
    "seminary.seminary.comms.mark_inbox_read",
    "seminary.seminary.comms.reply_in_conversation",
    "seminary.seminary.comms.reply_portal_message",
    "seminary.seminary.comms.send_portal_message",
    "seminary.seminary.comms.set_address_sharing",
    "seminary.seminary.comms.update_my_address",
    "seminary.seminary.comms.update_my_communication_preferences",
    # seminary.seminary.course_checkin (4)
    "seminary.seminary.course_checkin.course_check_in",
    "seminary.seminary.course_checkin.ensure_meeting_checkin_code",
    "seminary.seminary.course_checkin.get_course_checkin_context",
    "seminary.seminary.course_checkin.get_open_course_checkins",
    # seminary.seminary.course_pack.export (1)
    "seminary.seminary.course_pack.export.export_course_pack",
    # seminary.seminary.course_pack.import_ (1)
    "seminary.seminary.course_pack.import_.import_course_pack",
    # seminary.seminary.dashboard_chart_source.students_per_current_courses.students_per_current_courses (1)
    "seminary.seminary.dashboard_chart_source.students_per_current_courses.students_per_current_courses.get",
    # seminary.seminary.discipleship.api (21)
    "seminary.seminary.discipleship.api.accept_invite",
    "seminary.seminary.discipleship.api.broadcast_to_leaders",
    "seminary.seminary.discipleship.api.can_broadcast",
    "seminary.seminary.discipleship.api.cohort_members",
    "seminary.seminary.discipleship.api.cohort_placement_status",
    "seminary.seminary.discipleship.api.cohort_seed_preview",
    "seminary.seminary.discipleship.api.create_cohort",
    "seminary.seminary.discipleship.api.create_cohorts_from_student_groups",
    "seminary.seminary.discipleship.api.create_my_cohort",
    "seminary.seminary.discipleship.api.decline_invite",
    "seminary.seminary.discipleship.api.invite_member",
    "seminary.seminary.discipleship.api.leave_cohort",
    "seminary.seminary.discipleship.api.my_communities",
    "seminary.seminary.discipleship.api.my_pending_invites",
    "seminary.seminary.discipleship.api.place_student_in_cohort",
    "seminary.seminary.discipleship.api.reassign_leader",
    "seminary.seminary.discipleship.api.remove_member",
    "seminary.seminary.discipleship.api.resend_invite",
    "seminary.seminary.discipleship.api.search_invitable_alumni",
    "seminary.seminary.discipleship.api.set_cohort_status",
    "seminary.seminary.discipleship.api.split_cohort",
    # seminary.seminary.discipleship.feed_api (22)
    "seminary.seminary.discipleship.feed_api.add_comment",
    "seminary.seminary.discipleship.feed_api.create_post",
    "seminary.seminary.discipleship.feed_api.delete_comment",
    "seminary.seminary.discipleship.feed_api.delete_post",
    "seminary.seminary.discipleship.feed_api.edit_comment",
    "seminary.seminary.discipleship.feed_api.edit_post",
    "seminary.seminary.discipleship.feed_api.get_thread",
    "seminary.seminary.discipleship.feed_api.link_post",
    "seminary.seminary.discipleship.feed_api.list_channels",
    "seminary.seminary.discipleship.feed_api.list_feed",
    "seminary.seminary.discipleship.feed_api.list_reaction_types",
    "seminary.seminary.discipleship.feed_api.mark_prayer_answered",
    "seminary.seminary.discipleship.feed_api.mark_seen",
    "seminary.seminary.discipleship.feed_api.my_cohorts_list",
    "seminary.seminary.discipleship.feed_api.posts_for_passage",
    "seminary.seminary.discipleship.feed_api.related_posts",
    "seminary.seminary.discipleship.feed_api.reopen_prayer",
    "seminary.seminary.discipleship.feed_api.search_posts",
    "seminary.seminary.discipleship.feed_api.toggle_reaction",
    "seminary.seminary.discipleship.feed_api.toggle_save",
    "seminary.seminary.discipleship.feed_api.unlink_post",
    "seminary.seminary.discipleship.feed_api.unread_counts",
    # seminary.seminary.discipleship.moderation (6)
    "seminary.seminary.discipleship.moderation.can_moderate",
    "seminary.seminary.discipleship.moderation.flag_content",
    "seminary.seminary.discipleship.moderation.list_flags",
    "seminary.seminary.discipleship.moderation.moderate_comment",
    "seminary.seminary.discipleship.moderation.resolve_flag",
    "seminary.seminary.discipleship.moderation.set_post_status",
    # seminary.seminary.discipleship.planner (5)
    "seminary.seminary.discipleship.planner.build_proposal",
    "seminary.seminary.discipleship.planner.create_cohorts",
    "seminary.seminary.discipleship.planner.plannable_types",
    "seminary.seminary.discipleship.planner.planner_setup",
    "seminary.seminary.discipleship.planner.readiness_detail",
    # seminary.seminary.discipleship.scripture (4)
    "seminary.seminary.discipleship.scripture.posts_in_range",
    "seminary.seminary.discipleship.scripture.scripture_books",
    "seminary.seminary.discipleship.scripture.scripture_chapters",
    "seminary.seminary.discipleship.scripture.scripture_verses",
    # seminary.seminary.doctype.academic_term.academic_term (1)
    "seminary.seminary.doctype.academic_term.academic_term.get_academic_year_context",
    # seminary.seminary.doctype.address_geocoding_settings.address_geocoding_settings (1)
    "seminary.seminary.doctype.address_geocoding_settings.address_geocoding_settings.test_connection",
    # seminary.seminary.doctype.assignment_activity.assignment_activity (1)
    "seminary.seminary.doctype.assignment_activity.assignment_activity.save_assignment",
    # seminary.seminary.doctype.course.course (3)
    "seminary.seminary.doctype.course.course.add_course_to_programs",
    "seminary.seminary.doctype.course.course.bulk_add_courses_to_program",
    "seminary.seminary.doctype.course.course.get_programs_without_course",
    # seminary.seminary.doctype.course_competency.course_competency (1)
    "seminary.seminary.doctype.course_competency.course_competency.get_course_dimensions",
    # seminary.seminary.doctype.course_enrollment_individual.course_enrollment_individual (3)
    "seminary.seminary.doctype.course_enrollment_individual.course_enrollment_individual.get_credits",
    "seminary.seminary.doctype.course_enrollment_individual.course_enrollment_individual.get_credits2",
    "seminary.seminary.doctype.course_enrollment_individual.course_enrollment_individual.get_inv_data_ce",
    # seminary.seminary.doctype.course_folder.course_folder (2)
    "seminary.seminary.doctype.course_folder.course_folder.folder_context",
    "seminary.seminary.doctype.course_folder.course_folder.list_embeddable_folders",
    # seminary.seminary.doctype.course_gradebook.course_gradebook (1)
    "seminary.seminary.doctype.course_gradebook.course_gradebook.get_student_grades",
    # seminary.seminary.doctype.course_lesson.course_lesson (2)
    "seminary.seminary.doctype.course_lesson.course_lesson.get_lesson_info",
    "seminary.seminary.doctype.course_lesson.course_lesson.save_progress",
    # seminary.seminary.doctype.course_schedule.course_schedule (7)
    "seminary.seminary.doctype.course_schedule.course_schedule.bulk_close_enrollment",
    "seminary.seminary.doctype.course_schedule.course_schedule.cancel_course",
    "seminary.seminary.doctype.course_schedule.course_schedule.change_room",
    "seminary.seminary.doctype.course_schedule.course_schedule.import_template",
    "seminary.seminary.doctype.course_schedule.course_schedule.regenerate_token",
    "seminary.seminary.doctype.course_schedule.course_schedule.schedule_dates",
    "seminary.seminary.doctype.course_schedule.course_schedule.validate",
    # seminary.seminary.doctype.exam_activity.exam_activity (1)
    "seminary.seminary.doctype.exam_activity.exam_activity.exam_summary",
    # seminary.seminary.doctype.instructor.instructor (4)
    "seminary.seminary.doctype.instructor.instructor.create_supplier",
    "seminary.seminary.doctype.instructor.instructor.pull_education_from_employee",
    "seminary.seminary.doctype.instructor.instructor.push_education_to_employee",
    "seminary.seminary.doctype.instructor.instructor.update_instructorlog",
    # seminary.seminary.doctype.partner_seminary_course_equivalence.partner_seminary_course_equivalence (1)
    "seminary.seminary.doctype.partner_seminary_course_equivalence.partner_seminary_course_equivalence.create_legacy_integration",
    # seminary.seminary.doctype.partner_transcript_import_batch.partner_transcript_import_batch (2)
    "seminary.seminary.doctype.partner_transcript_import_batch.partner_transcript_import_batch.dry_run",
    "seminary.seminary.doctype.partner_transcript_import_batch.partner_transcript_import_batch.get_import_options",
    # seminary.seminary.doctype.person_import_batch.person_import_batch (3)
    "seminary.seminary.doctype.person_import_batch.person_import_batch.download_template",
    "seminary.seminary.doctype.person_import_batch.person_import_batch.dry_run",
    "seminary.seminary.doctype.person_import_batch.person_import_batch.load_from_csv",
    # seminary.seminary.doctype.program.program (3)
    "seminary.seminary.doctype.program.program.apply_required_on_enroll",
    "seminary.seminary.doctype.program.program.get_competency_courses",
    "seminary.seminary.doctype.program.program.get_program_tracks",
    # seminary.seminary.doctype.program_enrollment.program_enrollment (3)
    "seminary.seminary.doctype.program_enrollment.program_enrollment.get_emphasis",
    "seminary.seminary.doctype.program_enrollment.program_enrollment.get_payers",
    "seminary.seminary.doctype.program_enrollment.program_enrollment.get_program_courses",
    # seminary.seminary.doctype.question.question (2)
    "seminary.seminary.doctype.question.question.refresh_scripture_text",
    "seminary.seminary.doctype.question.question.replace_matching_items",
    # seminary.seminary.doctype.recommendation_letter.recommendation_letter (1)
    "seminary.seminary.doctype.recommendation_letter.recommendation_letter.regenerate_token",
    # seminary.seminary.doctype.scheduled_course_roster.scheduled_course_roster (2)
    "seminary.seminary.doctype.scheduled_course_roster.scheduled_course_roster.validate",
    "seminary.seminary.doctype.scheduled_course_roster.scheduled_course_roster.validate_score",
    # seminary.seminary.doctype.seminary_help_entry.seminary_help_entry (1)
    "seminary.seminary.doctype.seminary_help_entry.seminary_help_entry.get_help_entry",
    # seminary.seminary.doctype.seminary_lesson_note.seminary_lesson_note (1)
    "seminary.seminary.doctype.seminary_lesson_note.seminary_lesson_note.get_note",
    # seminary.seminary.doctype.seminary_settings.seminary_settings (1)
    "seminary.seminary.doctype.seminary_settings.seminary_settings.check_payments_app",
    # seminary.seminary.doctype.student.student (1)
    "seminary.seminary.doctype.student.student.get_pgmenrollments",
    # seminary.seminary.doctype.term_admission.term_admission (1)
    "seminary.seminary.doctype.term_admission.term_admission.refresh_programs",
    # seminary.seminary.events (4)
    "seminary.seminary.events.create_cohort_event",
    "seminary.seminary.events.create_requirement_event",
    "seminary.seminary.events.get_cohort_candidates",
    "seminary.seminary.events.get_per_student_event_requirements",
    # seminary.seminary.faculty (5)
    "seminary.seminary.faculty.capability_holders",
    "seminary.seminary.faculty.get_my_faculty_worklist",
    "seminary.seminary.faculty.get_unit_roster",
    "seminary.seminary.faculty.instructors_in_unit",
    "seminary.seminary.faculty.person_org_footprint",
    # seminary.seminary.graduation (12)
    "seminary.seminary.graduation.cancel_orphan_requirement",
    "seminary.seminary.graduation.choose_project_type",
    "seminary.seminary.graduation.choose_requirement_option",
    "seminary.seminary.graduation.get_allowed_culm_types",
    "seminary.seminary.graduation.get_choose_option_items",
    "seminary.seminary.graduation.mark_sgr_verified",
    "seminary.seminary.graduation.resnapshot",
    "seminary.seminary.graduation.start_culminating_project",
    "seminary.seminary.graduation.start_recommendation_letter",
    "seminary.seminary.graduation.submit_student_evidence",
    "seminary.seminary.graduation.waive_sgr",
    "seminary.seminary.graduation.withdraw_orphan_requirement",
    # seminary.seminary.instructor_load (1)
    "seminary.seminary.instructor_load.instructor_commitments",
    # seminary.seminary.integrations.bible (7)
    "seminary.seminary.integrations.bible.get_available_bibles_for_user",
    "seminary.seminary.integrations.bible.get_bible_name",
    "seminary.seminary.integrations.bible.list_bibles",
    "seminary.seminary.integrations.bible.lookup",
    "seminary.seminary.integrations.bible.passage_text",
    "seminary.seminary.integrations.bible.set_user_bible",
    "seminary.seminary.integrations.bible.test_connection",
    # seminary.seminary.integrations.geocoding (1)
    "seminary.seminary.integrations.geocoding.geocode_now",
    # seminary.seminary.integrations.pexels (3)
    "seminary.seminary.integrations.pexels.download_photo",
    "seminary.seminary.integrations.pexels.search_photos",
    "seminary.seminary.integrations.pexels.test_connection",
    # seminary.seminary.lesson_media (1)
    "seminary.seminary.lesson_media.get_upload_limits",
    # seminary.seminary.leveling (3)
    "seminary.seminary.leveling.apply_leveling_profile",
    "seminary.seminary.leveling.mark_placement_scored",
    "seminary.seminary.leveling.resolve_leveling_plan",
    # seminary.seminary.program_status (2)
    "seminary.seminary.program_status.place_on_leave",
    "seminary.seminary.program_status.return_from_leave_action",
    # seminary.seminary.scholarship (3)
    "seminary.seminary.scholarship.apply_for_scholarship",
    "seminary.seminary.scholarship.get_available_scholarships",
    "seminary.seminary.scholarship.get_student_scholarship",
    # seminary.seminary.telegram_adapter (2)
    "seminary.seminary.telegram_adapter.get_my_telegram_link",
    "seminary.seminary.telegram_adapter.register_webhook",
    # seminary.seminary.telemetry (1)
    "seminary.seminary.telemetry.get_posthog_settings",
    # seminary.seminary.web_form.student_applicant.student_applicant (1)
    "seminary.seminary.web_form.student_applicant.student_applicant.get_context",
    # seminary.seminary.withdrawal (2)
    "seminary.seminary.withdrawal.calculate_dynamic_date",
    "seminary.seminary.withdrawal.get_withdrawal_rule_for_date",
    # seminary.storage.api (1)
    "seminary.storage.api.selftest",
    # seminary.storage.direct (2)
    "seminary.storage.direct.presign_upload",
    "seminary.storage.direct.register_upload",
    # seminary.utils (1)
    "seminary.utils.create_student_groups",
    # seminary.workspace_i18n (2)
    "seminary.workspace_i18n.get_desktop_page",
    "seminary.workspace_i18n.get_workspace_sidebar_items",
    # seminary.workspace_save_fix (1)
    "seminary.workspace_save_fix.save_page",
}

MAX_PENDING = 292

# Modules that do not import cleanly outside a request context. Their endpoints
# are therefore invisible to the walk; keep the list at zero-growth.
KNOWN_IMPORT_FAILURES = {
    # builds a report column map at import time from a doc that may not exist
    "seminary.seminary.report.gradebook_course_schedule.gradebook_course_schedule",
}

# Arguments that must not be a bare string for the call to reach the gate.
KWARG_OVERRIDES = {
    "seminary.seminary.api.mark_attendance": {
        "students_present": "[]",
        "students_absent": "[]",
        "course_schedule": "ZZT-no-such-cs",
    },
    "seminary.seminary.api.send_grades": {"doc": '{"name": "ZZT-no-such-cs"}'},
    "seminary.seminary.api.save_discussion_submission_grade": {"grade": 1.0},
    "seminary.seminary.api.add_submission_comment": {"comment": "x"},
    "seminary.seminary.doctype.exam_submission.exam_submission.add_exam_grading_comment": {
        "comment": "x"
    },
    "seminary.seminary.api.insert_cs_assessment": {"criteria": {"parent": "ZZT-x"}},
    "seminary.seminary.api.save_course_assessment": {"assessment_data": "[]"},
    "seminary.seminary.api.room_search": {
        "doctype": "Room",
        "txt": "",
        "searchfield": "name",
        "start": 0,
        "page_len": 5,
        "filters": {},
    },
}


def _import_every_seminary_module():
    """A function is only in ``frappe.whitelisted`` once its module is imported,
    so discovery means importing the app. Test modules are skipped (they import
    this one). Import failures are returned rather than raised: a module that
    cannot be imported registers nothing, and the caller asserts the list is the
    one we know about."""
    import importlib
    import pkgutil

    import seminary

    failures = []
    for info in pkgutil.walk_packages(seminary.__path__, prefix="seminary."):
        name = info.name
        leaf = name.rsplit(".", 1)[-1]
        if ".tests" in name or leaf.startswith("test_"):
            continue
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001
            failures.append((name, type(e).__name__))
    return failures


def _walk():
    _import_every_seminary_module()
    found = {}
    for fn in frappe.whitelisted:
        mod = getattr(fn, "__module__", "") or ""
        if mod.startswith("seminary."):
            found[f"{mod}.{fn.__name__}"] = fn
    return found


def _dummy_kwargs(fn, dotted):
    kwargs = {}
    sig = inspect.signature(fn)
    for name, param in sig.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        if param.default is inspect.Parameter.empty:
            kwargs[name] = "ZZT-no-such"
    kwargs.update(KWARG_OVERRIDES.get(dotted, {}))
    return kwargs


class TestP007WhitelistWalk(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "walk-student")
        # The positive half runs as a user holding every school role, so a
        # registrar-only gate (term roll, separation) is not what stops them.
        cls.chair = _make_user("Program Chair", "walk-chair")
        frappe.get_doc("User", cls.chair).add_roles("Registrar", "Seminary Manager")
        cls.found = _walk()

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_every_endpoint_is_classified(self):
        classified = GUEST_ALLOWED | STUDENT_ALLOWED | STAFF_ONLY | OWN_RULE
        missing = sorted(set(self.found) - classified - PENDING_CLASSIFICATION)
        self.assertEqual(
            missing,
            [],
            "unclassified whitelisted functions (classify them, or add the "
            "module to PENDING_CLASSIFICATION with MAX_PENDING raised — which "
            "the ratchet below forbids): %s" % missing,
        )
        stale = sorted(classified - set(self.found))
        self.assertEqual(stale, [], "classified but not whitelisted: %s" % stale)

    def test_pending_only_shrinks(self):
        """The triage debt is a ratchet. MAX_PENDING may be lowered as modules
        are reviewed; raising it is the thing this test exists to prevent."""
        live = PENDING_CLASSIFICATION & set(self.found)
        self.assertLessEqual(
            len(live),
            MAX_PENDING,
            "PENDING_CLASSIFICATION grew to %d (max %d). A new endpoint must be "
            "classified, not parked." % (len(live), MAX_PENDING),
        )
        gone = sorted(PENDING_CLASSIFICATION - set(self.found))
        self.assertEqual(
            gone, [], "pending entries that are no longer whitelisted: %s" % gone
        )

    def test_reviewed_modules_have_no_pending(self):
        """A module counts as reviewed only when none of its endpoints is
        parked. This is what stops a reviewed module quietly regrowing debt."""
        leaked = sorted(
            d for d in PENDING_CLASSIFICATION if d.rsplit(".", 1)[0] in REVIEWED_MODULES
        )
        self.assertEqual(leaked, [], "pending in a reviewed module: %s" % leaked)

    def test_module_import_failures_are_known(self):
        """Discovery is only as good as the import sweep. A module that stops
        importing would silently drop its endpoints out of the contract."""
        failures = _import_every_seminary_module()
        self.assertEqual(
            sorted(n for n, _ in failures),
            sorted(KNOWN_IMPORT_FAILURES),
            "seminary modules that no longer import: %s" % (failures,),
        )
        overlap = (
            (GUEST_ALLOWED & STUDENT_ALLOWED)
            | (GUEST_ALLOWED & STAFF_ONLY)
            | (STUDENT_ALLOWED & STAFF_ONLY)
        )
        self.assertEqual(overlap, set())

    def test_guest_list_matches_allow_guest(self):
        guest = {
            dotted for dotted, fn in self.found.items() if fn in frappe.guest_methods
        }
        self.assertEqual(guest, GUEST_ALLOWED)

    def test_staff_only_refuses_student_and_admits_chair(self):
        for dotted in sorted(STAFF_ONLY):
            fn = self.found[dotted]
            kwargs = _dummy_kwargs(fn, dotted)
            frappe.set_user(self.student)
            with self.subTest(fn=dotted, who="student"):
                with self.assertRaises(frappe.PermissionError):
                    fn(**kwargs)
            frappe.set_user(self.chair)
            with self.subTest(fn=dotted, who="chair"):
                try:
                    fn(**kwargs)
                except frappe.PermissionError as e:
                    self.fail("Program Chair refused by the gate: %s" % e)
                except Exception as e:
                    # A missing fixture is expected; only the gate is under test.
                    self.assertNotIsInstance(e, frappe.PermissionError)
            frappe.set_user("Administrator")

    def test_guest_is_refused_everywhere_else(self):
        frappe.set_user("Guest")
        for dotted in sorted(set(self.found) - GUEST_ALLOWED):
            self.assertNotIn(self.found[dotted], frappe.guest_methods, dotted)
