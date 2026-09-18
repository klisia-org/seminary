# p007 whitelist survey (2026-09-18, branch p006-phase0)

Every `@frappe.whitelist` function in `seminary/seminary/api.py` (104) and
`seminary/seminary/utils.py` (38), with its gate at survey time, its SPA/Desk callers,
and the verdict that drives privatedocs/p007 §2.5–2.7 and the walk test (§2.10).

Verdicts: OK = student-safe as is (session-scoped or no target); NEEDS = student
calls it legitimately but the target is not verified; GATED = staff-only and gated;
UNGATED = staff-only with no server gate; DEAD = hook-only, internal, or no caller.

Totals: OK 28 · NEEDS 31 · GATED 34 · UNGATED 22 · DEAD 27 (plus
`quiz.get_all_question_results`, DEAD, outside these two files).

## api.py

| name | line | gate | writes | callers (persona) | verdict |
|---|---|---|---|---|---|
| sanitize_html | 97 | none | N | cohort_post.py:15 (server) | DEAD |
| sanitize_submission | 106 | none | N | hooks.py:424 | DEAD (hook) |
| sanitize_reply | 112 | none | N | hooks.py:429 | DEAD (hook) |
| get_student_group | 118 | none; `user` verbatim | N | DiscussionActivity.vue:645 (student) | NEEDS |
| get_student_groups_simple | 132 | none | N | DiscussionActivity.vue:1109 (student) | NEEDS |
| get_student_groups | 145 | none | N | DiscussionActivitySubmissionCS.vue:160 (instructor) | UNGATED |
| get_discussion_submissions | 176 | none | N | DiscussionActivity.vue:622 (student) | NEEDS |
| get_user_discussion_submission | 227 | none; `owner` verbatim | N | DiscussionActivity.vue:662; DiscussionActivitySubmission.vue:242 | NEEDS |
| get_user_discussion_replies | 260 | none; `member` verbatim | N | DiscussionActivitySubmission.vue:257 | NEEDS |
| get_discussion_submission_summary | 278 | none | N | DiscussionActivitySubmissionCS.vue:198 (instructor) | UNGATED |
| save_discussion_submission_grade | 387 | require_grader | Y | DiscussionActivitySubmission.vue:376 | GATED |
| add_grading_comment | 413 | owner-or-staff inline | Y ignore_permissions | DiscussionActivity.vue:917; DiscussionActivitySubmission.vue:317 | OK |
| get_grading_comments | 446 | none | N | DiscussionActivity.vue:905; DiscussionActivitySubmission.vue:296 | NEEDS |
| get_discussion_dashboard | 461 | none | N | DiscussionActivity.vue:548 (both) | NEEDS |
| get_quiz_dashboard | 517 | none | N | Quiz.vue:573 (instructor) | UNGATED |
| get_exam_dashboard | 560 | none | N | Exam.vue:302 (instructor) | UNGATED |
| get_assignment_dashboard | 595 | none | N | Assignment.vue:1019 (instructor) | UNGATED |
| get_translations | 634 | allow_guest, no target | N | translation.js:33 | OK |
| get_enabled_languages | 643 | session | N | ProfileModal.vue:357 | OK |
| set_user_language | 656 | session | Y own User | ProfileModal.vue:367 | OK |
| get_file_info | 663 | none | N | Assignment.vue:728,758; DiscussionActivity.vue:852; CourseForm.vue:494 | NEEDS |
| save_course | 676 | **none** | Y cs.save + 5× db.set_value | CourseForm.vue:523 (instructor) | UNGATED |
| get_virtual_meetings | 766 | none | N | CourseForm.vue:351 | UNGATED |
| add_virtual_meeting | 788 | _can_manage_virtual_meetings | Y | CourseForm.vue:373 | GATED |
| remove_virtual_meeting | 818 | _can_manage_virtual_meetings | Y | CourseForm.vue:392 | GATED |
| get_user_info | 849 | allow_guest, session only | N | stores/user.js:7 | OK |
| get_instructor_info | 946 | session Instructor | N | ProfileModal.vue:574 | OK |
| save_student_profile | 992 | session Student | Y | ProfileModal.vue:445 | OK |
| save_instructor_profile | 1068 | session Instructor | Y | ProfileModal.vue:498 | OK |
| get_school_abbr_logo | 1126 | allow_guest | N | main.js:21 and sidebars | OK |
| get_course | 1155 | none | N | none | DEAD |
| get_student_programs | 1169 | none | N | Grades.vue:138 (student) | NEEDS |
| roll_students | 1240 | only_for Registrar/SM/SysM | Y | workspaces_bootstrap.py:162 | GATED |
| course_enroll | 1419 | _assert_may_course_enroll | Y | Enrollment.vue:314 | OK |
| get_student_enrollments_for_term | 1582 | none | N | Enrollment.vue:257 | NEEDS |
| cancel_draft_enrollment | 1673 | owner check | Y delete | Enrollment.vue:365 | OK |
| cancel_unpaid_enrollment | 1687 | owner-or-staff | Y cancel | Enrollment.vue:380 | OK |
| check_schedule_conflicts | 1759 | _is_conflict_staff else own | N | course_enrollment_individual.js:167 | GATED |
| resolve_schedule_conflict | 1777 | _is_conflict_staff | Y | student_schedule_conflicts.js:63 | GATED |
| credits_pe_track | 1811 | **none** | Y every active PE | none | DEAD (ungated mass write) |
| get_program_audit | 1915 | **none** | Y grad_candidate | ProgramAudit.vue:492; program_enrollment.js:129,273; graduation_request.js:54 | NEEDS |
| create_graduation_request | 2313 | owner-or-staff | Y insert+submit | ProgramAudit.vue:650 | OK |
| get_pe_unpaid_invoices | 2415 | none (backend) | N | ProgramAudit.vue:500; graduation_request.js:63 | NEEDS |
| get_available_courses_categorized | 2476 | none | N | Enrollment.vue:249 | NEEDS |
| enroll_student | 2689 | **none** | Y Student + PE | student_applicant.js:70 (desk) | UNGATED |
| check_attendance_records_exist | 2747 | none (get_list) | N | none | DEAD |
| mark_attendance | 2761 | require_grader(include_registrar) | Y | StudentAttendanceCS.vue:466; student_attendance_tool.js:129 | GATED |
| get_student_contacts | 2889 | none | N | none | DEAD |
| get_course_schedule_events | 2903 | none | N | course_schedule_calendar.js:7; classes_and_assessments_calendar | UNGATED |
| get_assessment_criteria | 2949 | none | N | none | DEAD |
| get_grade | 2998 | none | N | internal | DEAD |
| quizresult_to_card | 3008 | none | Y ignore_permissions | hooks.py:407-421 | DEAD (hook) |
| save_course_assessment | 3055 | require_outline_editor | Y | CourseAssessment.vue:650 | GATED |
| get_scholarship | 3144 | none | N | none | DEAD |
| get_student_invoices | 3152 | backend forces own Student | N | Fees.vue:310 | OK |
| courses_for_student | 3160 | none | N | course_enrollment_individual.js:12 (desk); internal | UNGATED |
| copy_data_to_scheduled_course_roster | 3247 | none | Y | cei_lifecycle.py:69 | DEAD (server) |
| copy_data_to_program_enrollment_course | 3313 | none | Y | cei_lifecycle.py:72 | DEAD (server) |
| update_card | 3334 | none | Y | hooks.py:401 | DEAD (hook) |
| insert_cs_assessment | 3397 | require_outline_editor | Y | CourseAssessmentModal.vue:263 | GATED |
| get_pgmenrollments | 3433 | none | N | Enrollment.vue:224; ProgramAudit.vue:479; student.js:57 | NEEDS |
| get_course_rosters | 3450 | none | N | course_schedule.js:389 (desk) | UNGATED |
| grade_thisstudent | 3474 | require_grader(include_registrar) | Y | scheduled_course_roster.js:14,52 | GATED |
| get_gradepass | 3527 | none | N | internal | DEAD |
| fgrade_this_std | 3537 | require_grader(include_registrar) | Y | scheduled_course_roster.js:17,55 | GATED |
| fail_for_absence | 3662 | _assert_fa_roles | Y | scheduled_course_roster.js:35; report | GATED |
| undo_fail_for_absence | 3723 | _assert_fa_roles | Y | scheduled_course_roster.js:41 | GATED |
| send_selected_grades | 4003 | _assert_may_send_grades | Y | Gradebook.vue:282; CompetencyGradebook.vue:563 | GATED |
| send_grades | 4091 | _assert_may_send_grades | Y | Gradebook.vue:326; course_schedule.js:160 | GATED |
| course_event | 4437 | **none** | Y Event with roster emails | course_schedule.js:119,298 (desk) | UNGATED |
| get_doctrinal_statement | 4534 | allow_guest (public) | N | student_applicant_webform.js:20 | OK |
| get_application_payment_url | 4559 | access_key compare_digest / super | N | www/applicant_payment.py:23 | GATED |
| get_default_phone_country | 4588 | allow_guest, no target | N | student_applicant.js:2 | OK |
| active_term | 4604 | allow_guest, no target | N | student_applicant.js:10 | OK |
| upsert_chapter | 4637 | _assert_may_edit_outline (roles) | Y | ChapterModal.vue:185 | GATED |
| delete_chapter | 4789 | require_outline_editor | Y | CourseOutline.vue:430 | GATED |
| mark_lesson_progress | 4863 | save_progress requires own roster | Y | Assignment.vue:906; DiscussionActivity.vue:1026; Quiz.vue:992 | OK |
| get_student_info | 4878 | session | N | ProfileModal.vue:553; stores/student.js:13 | OK |
| get_fields | 4957 | none | N | none | DEAD |
| delete_lesson | 4970 | require_outline_editor | Y | CourseOutline.vue:343 | GATED |
| delete_documents | 4985 | only_for SM/PC/Instructor | Y | CourseAssessment.vue:590; ExamForm.vue:375; QuizForm.vue:446 | GATED |
| get_announcements | 4992 | none | N | Announcements.vue:41 (student) | NEEDS |
| update_lesson_index | 5020 | require_outline_editor | Y | CourseOutline.vue:357 | GATED |
| update_chapter_index | 5093 | _assert_can_edit_outline(course) | Y | CourseOutline.vue:373 | GATED |
| GradeableDiscussion | 5136 | none | N | DiscussionActivity.vue:435 | NEEDS (boolean) |
| GradeableQuiz | 5150 | none | N | Quiz.vue:583 | NEEDS (boolean) |
| GradeableExam | 5165 | none | N | Exam.vue:312 | NEEDS (boolean) |
| GradeableAssignment | 5180 | none | N | Assignment.vue:1029 | NEEDS (boolean) |
| get_submission_comments | 5215 | check_permission read | N | SubmissionViewer.vue:98 | GATED |
| add_submission_comment | 5262 | _can_grade_submission (roles) | Y | SubmissionViewer.vue:130 | GATED |
| update_submission_comment | 5313 | author or grader | Y | CommentSidebar.vue:173,187 | GATED |
| delete_submission_comment | 5336 | author or grader | Y | CommentSidebar.vue:200 | GATED |
| get_invoice_payment_url | 5348 | backend checks custom_student | Y Payment Request | Fees.vue:375 | OK |
| get_student_balance_payment_url | 5356 | backend, session | Y | Fees.vue:398 | OK |
| get_student_partial_balance_payment_url | 5364 | backend; `invoices` client-supplied | Y | Fees.vue:421 | OK (re-check in oikonomos) |
| get_my_announcements | 5372 | session in SQL | N | none | DEAD |
| preview_announcement_recipients | 5403 | **none** | N | seminary_announcement.js:173 (desk) | UNGATED |
| generate_announcement_labels | 5491 | check_permission write | Y | seminary_announcement.js:126 | GATED |
| announcement_letters_pdf | 5530 | check_permission read | Y | seminary_announcement.js:107 | GATED |
| preview_announcement_letter | 5547 | check_permission read (writes File) | Y | seminary_announcement.js:95 | GATED |
| room_search | 5628 | validate_and_sanitize_search_inputs only | N | course_schedule.js:7,34 (desk) | UNGATED |
| run_plagiarism_check | 5783 | _require_grader | Y | Assignment.vue:625 | GATED |
| get_plagiarism_result | 5799 | _require_grader | N | Assignment.vue:616 | GATED |
| get_plagiarism_match_detail | 5846 | _require_grader | N | Assignment.vue:654 | GATED |

## utils.py

| name | line | gate | writes | callers (persona) | verdict |
|---|---|---|---|---|---|
| get_timezones | 63 | none | N | campus.js:9 (desk) | UNGATED (harmless) |
| get_user_info | 351 | allow_guest, session | N | none (SPA uses api.get_user_info) | DEAD (duplicate) |
| get_all_users | 382 | only_for PC/Instructor/SM | N | stores/user.js:24 via DiscussionReplies.vue:172 (student gets 403) | GATED |
| has_course_moderator_role | 403 | _role_subject | N | assignment_activity.py:15; question.py:252 (server) | DEAD (internal) |
| has_course_instructor_role | 412 | _role_subject | N | server only | DEAD (internal) |
| has_course_evaluator_role | 421 | _role_subject | N | none | DEAD |
| has_student_role | 430 | _role_subject | N | p0matrix only | DEAD |
| get_courses_for_student | 439 | session unless super | N | Courses.vue:197 | OK |
| get_courses | 495 | published unless super; Instructor own | N | Courses.vue:191 | OK |
| get_instructors | 544 | none | N | Exam.vue:259; StudentGroup.vue:304 | NEEDS (low) |
| get_instructor | 574 | none | N | InstructorProfile.vue:60 | OK (public profile) |
| get_course_outline | 701 | none | N | CourseOutline.vue:324 | NEEDS |
| get_course_title | 746 | none | N | CourseOutline.vue:334 | NEEDS (trivial) |
| get_course_details | 795 | token/meeting stripped unless enrolled | N | 16 sites | OK |
| get_roster | 934 | **none** | N | CourseDetail.vue:191 (student, auto); StudentGroup.vue:324 | NEEDS (PII) |
| get_lesson | 1042 | staff or own roster row | N | Lesson.vue:186 | OK |
| get_lesson_due_date | 1280 | none | N | internal | DEAD |
| get_lesson_creation_details | 1459 | **none** | N | LessonForm.vue:160 (instructor) | UNGATED (instructor notes) |
| get_question_details | 1508 | none | N | Quiz.vue:642 | NEEDS (no key fields) |
| get_all_questions_details | 1539 | none | N | Quiz.vue:668 | NEEDS |
| get_open_question_details | 1589 | none | N | none | DEAD |
| get_all_open_questions_details | 1596 | none | N | none | DEAD |
| get_assessments | 1614 | none; ignore_permissions read | N | CourseAssessment.vue:422; useCourseToDo.js:18 | NEEDS |
| get_assessment_due_date | 1634 | none | N | DiscussionActivitySubmissionCS.vue:154 | NEEDS (low) |
| get_gradebook | 1952 | require_grader(include_registrar) | N | Gradebook.vue:340 | GATED |
| get_student_course_status | 1982 | own roster row | N | CourseStatus.vue:299 | OK |
| enroll_in_program | 2143 | super no-op; allow_self_enroll | Y | none | DEAD (ungated writer) |
| get_discussion_topics | 2221 | none | Y may create topic | Discussions.vue:195 | NEEDS |
| get_discussion_replies | 2265 | none | N | DiscussionReplies.vue:145 | NEEDS |
| ensure_single_topic | 2286 | none | Y ignore_permissions | Discussions.vue:172 | NEEDS |
| missing_exams | 2314 | **none** | N | ExamSubmissionCS.vue:168 | UNGATED |
| get_course_exams | 2335 | none; ignore_permissions | N | ExamSubmissionCS.vue:186 | UNGATED |
| get_course_meetingdates | 2361 | **none** | N | StudentAttendanceCS.vue:277 | UNGATED (checkin_code) |
| get_missingassessments | 2400 | `member` verbatim | N | useCourseToDo.js:25 | NEEDS |
| get_assessments_tograde | 2470 | **none** | N | useCourseToDo.js:34 (auto, all personas) | UNGATED |
| insert_discussion_reply | 2494 | none | Y ignore_permissions | none | DEAD (ungated writer) |
| get_student_groups | 2511 | **none** | N | StudentGroup.vue:317 | UNGATED |
| create_student_group | 2525 | **none** | Y ignore_permissions ×N | StudentGroup.vue:719 | UNGATED |

## Frontend calls to endpoints that do not exist

- `seminary.seminary.utils.delete_student_groups` — StudentGroup.vue:651
- `seminary.seminary.utils.update_student_groups` — StudentGroup.vue:620
- `seminary.seminary.utils.is_onboarding_complete` — stores/settings.js:16
- `seminary.seminary.api.course_schedule_calendar` — utils/coursecalendar.js:9
