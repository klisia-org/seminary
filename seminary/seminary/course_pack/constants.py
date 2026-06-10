"""Constants and field allow-lists for Course Pack export/import.

We carry CONTENT and strip per-instance / derived state. Each tuple below is an
explicit allow-list of the fields copied for that doctype — deliberately
explicit (rather than "copy everything minus a deny-list") so a future field
addition defaults to NOT leaking into shared packs until someone opts it in.

Cross-references (Link fields that point at other exported docs, and the
activity/media references embedded in EditorJS content) are handled by the
remap engine, not copied verbatim — see export.py / import_.py / editorjs.py.
"""

# Bump when the manifest schema changes incompatibly. Import refuses packs
# newer than it understands; older packs may be migrated forward.
PACK_FORMAT_VERSION = 1

# Same authority as the within-site template import (course_schedule.py).
EXPORT_ROLES = ("Program Chair", "Seminary Manager", "Registrar")
IMPORT_ROLES = ("Program Chair", "Seminary Manager", "Registrar")

# ---------------------------------------------------------------------------
# Per-doctype content field allow-lists (verbatim copy).
# Link fields that must be remapped on import are listed in *_REF_FIELDS below
# and set separately; they are intentionally absent from the verbatim tuples.
# ---------------------------------------------------------------------------

CHAPTER_FIELDS = (
    "chapter_title",
    "is_scorm_package",
    "scorm_package_path",
    "manifest_file",
    "launch_file",
)  # scorm_package (Link -> File) handled via the media map

LESSON_FIELDS = (
    "lesson_title",
    "body",
    "content",
    "preview",
    "youtube",
    "instructor_notes",
    "instructor_content",
    "allow_discuss",
)

# Lesson Link fields pointing at SCAC rows — remapped after SCAC insert, exactly
# like Course Schedule.import_template's _remap_lesson_scac_links.
LESSON_SCAC_LINK_FIELDS = (
    "assessment_criteria_quiz",
    "assessment_criteria_assignment",
    "assessment_criteria_exam",
    "assessment_criteria_discussion",
)

QUIZ_FIELDS = (
    "title",
    "max_attempts",
    "grading_basis",
    "duration",
    "show_answers",
    "show_submission_history",
    "shuffle_questions",
    "limit_questions_to",
    "passing_percentage",
    "qbyquestion",
)  # course set on import; total_points recomputed; questions handled separately

QUIZ_QUESTION_FIELDS = ("points",)  # `question` Link remapped; type/detail fetch

QUESTION_FIELDS = (
    "question",
    "type",
    "multiple",
    "option_1",
    "is_correct_1",
    "explanation_1",
    "option_2",
    "is_correct_2",
    "explanation_2",
    "option_3",
    "is_correct_3",
    "explanation_3",
    "option_4",
    "is_correct_4",
    "explanation_4",
    "possibility_1",
    "possibility_2",
    "possibility_3",
    "possibility_4",
    "pages_total",
    "scripture_bible_id",
    "memorization_ref",
    "hide_word_count",
    "min_word_length",
)  # course set on import; memorization_resolved_ref/text recomputed

SCRIPTURE_MATCHING_ITEM_FIELDS = ("reference",)  # resolved_ref/fetched_text recomputed

EXAM_FIELDS = (
    "title",
    "duration",
    "qbyquestion",
    "shuffle_questions",
    "limit_questions_to",
)  # course set on import; total_points recomputed; questions handled separately

EXAM_QUESTION_FIELDS = ("points",)  # `question` Link remapped; detail fields fetch

OPEN_QUESTION_FIELDS = ("question", "explanation", "section_break")

ASSIGNMENT_FIELDS = (
    "title",
    "question",
    "type",
    "show_answer",
    "grade_assignment",
    "answer",
)  # course set on import

DISCUSSION_FIELDS = (
    "discussion_name",
    "post_before",
    "prompt",
    "use_studentgroup",
    "min_replies_required",
)  # course set on import

FOLDER_FIELDS = ("foldername",)  # course set; file_reference/parent_folder rebuilt

SCAC_FIELDS = (
    "title",
    "weight_scac",
    "extracredit_scac",
    "fudgepoints_scac",
)  # assesscriteria_scac (stable key) + quiz/assignment/exam/discussion remapped;
# due_date and lesson label intentionally dropped (per-instance)

GRADING_SCALE_FIELDS = (
    "grading_scale_name",
    "description",
    "maxnumgrade",
    "grscale_type",
    "wp_code",
    "wf_code",
    "wp_gpa",
    "wf_gpa",
    "fa_code",
    "fa_gpa",
)

GRADING_SCALE_INTERVAL_FIELDS = (
    "grade_code",
    "threshold",
    "grade_description",
    "grade_pass",
)

# Activity doctypes referenced from lesson content, keyed by the EditorJS block
# field that holds the reference. (Block type -> (data field, doctype).)
ACTIVITY_BLOCKS = {
    "quiz": ("quiz", "Quiz"),
    "exam": ("exam", "Exam Activity"),
    "assignment": ("assignment", "Assignment Activity"),
    "discussionActivity": ("discussionID", "Discussion Activity"),
    "discussionactivity": ("discussionID", "Discussion Activity"),
    "folder": ("folder", "Course Folder"),
}
