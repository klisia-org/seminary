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
)  # scorm_package (Link -> File) handled via the media map. The three extracted-
# path fields are gone with the extraction itself (p008 F8): a path is not
# portable between sites, and one taken from a manifest is not to be trusted.

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

# Folder records in the manifest carry `foldername`, the original `scope` and,
# for Instructor scope, the originating professor's display name only
# (`origin_instructor_name`). course / instructor / file_reference /
# parent_folder are set on import from the destination (p006 F2, ADR §2.2b).
FOLDER_FIELDS = ("foldername", "scope", "origin_instructor_name")

SCAC_FIELDS = (
    "title",
    "weight_scac",
    "extracredit_scac",
    "fudgepoints_scac",
    "grading_mode_override",
)  # assesscriteria_scac (stable key) + quiz/assignment/exam/discussion remapped;
# due_date and lesson label intentionally dropped (per-instance).
# course_competency is a Link to a per-course record, so it is remapped on import
# by competency_code rather than carried as a raw name (ADR 065).

# Per-dimension weights travel with the assessment: they say what the activity
# measures, which is part of the course design rather than a per-offering choice.
ASSESSMENT_DIMENSION_WEIGHT_FIELDS = (
    "dimension_code",
    "weight",
)

# Competencies are course-level curriculum, so a course pack that omitted them
# would import a competency-based course that cannot be graded.
COURSE_COMPETENCY_FIELDS = (
    "competency_code",
    "competency_name",
    "sequence",
    "statement",
    "is_active",
)

COURSE_COMPETENCY_DIMENSION_FIELDS = (
    "dimension_code",
    "demonstrated_by",
    "weight",
)

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

# A competency scale's dimensions are part of its vocabulary: without them an
# imported competency has no dimension to describe (ADR 065).
GRADING_SCALE_DIMENSION_FIELDS = (
    "dimension",
    "dimension_code",
    "sequence",
    "description",
)

# Activity doctypes referenced from lesson content, keyed by the EditorJS block
# field that holds the reference. (Block type -> (data field, doctype).)
ACTIVITY_BLOCKS = {
    "quiz": ("quiz", "Quiz"),
    "exam": ("exam", "Exam Activity"),
    "assignment": ("assignment", "Assignment Activity"),
    "discussionActivity": ("discussionID", "Discussion Activity"),
    "discussionactivity": ("discussionID", "Discussion Activity"),
    # A folder block stores the Course Folder docname in `folder_ref`; `folder`
    # is only the display label (p006 F2). Blocks that predate the docname
    # reference carry `folder` alone — see editorjs.scan_folder_refs.
    "folder": ("folder_ref", "Course Folder"),
}


# ---------------------------------------------------------------------------
# Import-side trust (privatedocs p008 F9; ADR 041 "Import-side trust").
#
# A pack is UNTRUSTED INPUT -- it is a zip file from another school. The tuples
# above have governed what the exporter writes since day one; the importer used
# to ignore them, instantiating whatever `doctype` the manifest named and
# update()-ing it with whatever fields it carried, under ignore_permissions
# (p005 A01-7, Critical: a pack containing a User with System Manager, or a
# Client Script). These maps make the same allow-lists govern the import.
#
# An unknown FIELD is dropped silently -- that is version skew between sites. An
# unknown DOCTYPE throws -- that is not skew, it is the attack.
# ---------------------------------------------------------------------------

IMPORTABLE_DOCTYPES = {
    "questions": {
        "Question": QUESTION_FIELDS,
        "Open Question": OPEN_QUESTION_FIELDS,
    },
    "activities": {
        "Quiz": QUIZ_FIELDS,
        "Exam Activity": EXAM_FIELDS,
        "Assignment Activity": ASSIGNMENT_FIELDS,
        "Discussion Activity": DISCUSSION_FIELDS,
    },
}

# Decompression and size caps; each can be raised in site_config.json.
MAX_PACK_BYTES = 2 * 1024**3  # course_pack_max_bytes: the zip itself
MAX_PACK_UNCOMPRESSED_BYTES = 4 * 1024**3  # course_pack_max_uncompressed_bytes
MAX_PACK_ENTRIES = 20000  # course_pack_max_entries
MAX_PACK_MANIFEST_BYTES = 8 * 1024**2  # course_pack_max_manifest_bytes
# A ratio check only means something on a payload big enough to hurt: a small
# pack that is mostly JSON compresses very well and is no bomb.
PACK_RATIO_FLOOR_BYTES = 100 * 1024**2
MAX_PACK_RATIO = 200
