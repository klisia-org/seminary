"""Provider contract for the plagiarism checker.

Mirrors the comms adapter shape (a class per provider, resolved through a
hooks.py registry): an adapter implements ``check(target, corpus, config)`` and
returns a ``PlagiarismReport``. The service layer persists that report to a
Plagiarism Check Result doc — adapters never touch the database.
"""

from dataclasses import dataclass, field

# Terminal statuses a report can carry (mirrored on the result doctype Select).
STATUS_COMPLETED = "Completed"
STATUS_SKIPPED = "Skipped"
STATUS_FAILED = "Failed"


@dataclass
class MatchedSource:
    """One other submission the target resembled, with the score and (for the
    top few) the verbatim passages that overlapped."""

    source_submission: str
    similarity: float = 0.0  # 0-100, blended cosine + Jaccard
    source_student: str | None = None
    source_student_name: str | None = None
    source_course: str | None = None
    same_student: bool = False
    matched_passages: list = field(default_factory=list)  # [{text, ratio}]


@dataclass
class PlagiarismReport:
    """The full outcome of one check. ``overall_score`` is the headline number
    (max similarity across kept sources, honoring exclude-same-student)."""

    status: str = STATUS_COMPLETED
    overall_score: float = 0.0
    checked_chars: int = 0
    source_count: int = 0
    error: str | None = None
    engine_meta: dict = field(default_factory=dict)
    matched_sources: list = field(default_factory=list)


class PlagiarismAdapter:
    """Base class every provider adapter subclasses.

    ``requires_account`` tells the service whether an enabled Plagiarism
    Provider Account is needed (internal = self-contained; external = needs
    endpoint + key)."""

    provider_key: str | None = None
    requires_account: bool = False

    def check(self, target: dict, corpus: list, config: dict) -> PlagiarismReport:
        """target: {name, student, text}. corpus: list of
        {name, student, member_name, course, text}. config: the resolved
        Seminary Settings plagiarism options (+ optional account config)."""
        raise NotImplementedError
