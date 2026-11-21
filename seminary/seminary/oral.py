# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Oral recordings: recording, processing steps and retention (decisions/100).

Recording
    The portal records with MediaRecorder and sends each chunk as it arrives
    (``start_recording`` → ``upload_chunk`` … → ``finish_recording``), so a
    dropped connection loses seconds, not the answer. Chunks wait in the site's
    private directory, not in object storage: a site without an object store
    must record too. The finished audio is one private File attached to the
    recording, which Frappe offloads like any other large media file.

What a recording belongs to
    ``REFERENCES`` maps a doctype (an exam answer, an oral activity submission,
    an assignment submission) to a resolver that says, for one record, which
    section it is in, whose recording it is, who may record it, which steps run
    and what context those steps need. Each child decision (100a, 100b, 100c)
    registers its doctype here; nothing else can be recorded.

Steps (§4–§6)
    An app provides a step through the ``oral_steps`` hook,
    ``{step: "dotted.path"}``. The path is called with
    ``(recording, step, payload)``, returns at once, and later calls
    ``step_done`` or ``step_failed``. Seminary computes talk time itself. No
    step writes a grade, a rubric score or anything a student can see:
    moments arrive as *Suggested*, score suggestions and consistency notes go to
    the instructor-only ``Oral Step Result``.

Retention (§8)
    ``daily`` deletes the audio once every student on the recording has had
    their grades sent for ``oral_audio_retention_days``, unless one of them has
    an active hold. The transcript, speakers and moments stay.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import timedelta

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import (
    add_days,
    cint,
    flt,
    get_datetime,
    now_datetime,
)

STEPS = (
    "transcribe",
    "diarize",
    "moments",
    "questions",
    "follow_up",
    "score_suggestions",
    "consistency",
)
# Steps that run on a finished recording, in the order they become possible.
# `questions` and `follow_up` work on a submission's text and on one answer;
# 100c calls them itself.
PIPELINE = ("transcribe", "diarize", "moments", "score_suggestions", "consistency")
# A skipped step (turned off or uninstalled after the recording started) counts
# as finished for what follows it.
FINISHED = ("done", "skipped")

# Results only the instructor may see go to Oral Step Result.
STAFF_RESULTS = ("score_suggestions", "consistency")

# doctype -> dotted path of resolve(name, user) -> dict, see `_resolve`.
REFERENCES: dict[str, str] = {
    "Exam Question Result": "seminary.seminary.oral_exams.resolve",  # 100a
    # An oral activity on a section: the recording is made before any
    # submission exists, and submitting points every member's at it (100b).
    "Scheduled Course Assess Criteria": "seminary.seminary.oral_activities.resolve",
    "Oral Defense Question": "seminary.seminary.oral_defense.resolve",  # 100c
}

MIME_EXTENSIONS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
}
MAX_CHUNK_BYTES = 2 * 1024 * 1024
# A generous ceiling on the bitrate, to turn the minutes setting into bytes.
MAX_BYTES_PER_SECOND = 48_000
ABANDONED_HOURS = 24
_NAME_RE = re.compile(r"^[A-Za-z0-9-]+$")


# --------------------------------------------------------------------- settings


def _settings():
    return frappe.get_cached_doc("Seminary Settings")


def allowed_steps() -> list[str]:
    """Steps the school has not turned off (Seminary Settings)."""
    s = _settings()
    # A site that had Seminary Settings before these checks has them unset:
    # unset means allowed; only an explicit untick turns a step off.
    return [
        step
        for step in STEPS
        if s.get(f"oral_step_{step}") in (None, "") or cint(s.get(f"oral_step_{step}"))
    ]


def provided_steps() -> dict[str, str]:
    """{step: dotted path} from the ``oral_steps`` hook; the last app wins."""
    hooks = frappe.get_hooks("oral_steps") or {}
    provided = {}
    for step, paths in dict(hooks).items():
        path = paths[-1] if isinstance(paths, list) else paths
        if step in STEPS and path:
            provided[step] = path
    return provided


def available_steps() -> list[str]:
    """What an instructor may choose: provided by an app and allowed by the school."""
    provided = provided_steps()
    return [step for step in allowed_steps() if step in provided]


def max_seconds() -> int:
    return cint(_settings().get("oral_max_minutes") or 60) * 60


# ------------------------------------------------------------------- references


def _resolve(reference_doctype, reference_name, user=None) -> dict:
    """What a record says about its recording.

    The resolver returns:
    ``course_schedule``; ``participants`` as ``[(user, student)]``;
    ``may_record`` (this user may record it now); ``allow_upload``;
    ``steps`` (chosen for the activity); and optionally ``language``,
    ``expected_speakers``, ``criteria``, ``prompt``, ``text``,
    ``choosable`` (``[(user, student)]`` the recorder may name as present),
    ``max_seconds`` (a shorter limit than the school's),
    ``may_label`` (this user may link speaker labels to students),
    ``on_start`` (a dotted path called with the new recording's name) and
    ``after_step`` (a dotted path called with ``(recording, step)``).
    """
    path = REFERENCES.get(reference_doctype)
    if not path:
        frappe.throw(
            _("{0} cannot be recorded.").format(_(reference_doctype)),
            frappe.PermissionError,
        )
    if not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw(_("Not found."), frappe.PermissionError)
    return frappe.get_attr(path)(reference_name, user or frappe.session.user)


def _context(doc) -> dict:
    return _resolve(doc.reference_doctype, doc.reference_name, doc.recorded_by)


# -------------------------------------------------------------------- recording


def _chunk_dir(name):
    if not _NAME_RE.match(name or ""):
        frappe.throw(_("Invalid recording."))
    return frappe.get_site_path("private", "oral_chunks", name)


def _own_open_recording(recording):
    doc = frappe.get_doc("Oral Recording", recording)
    if doc.recorded_by != frappe.session.user:
        frappe.throw(_("This is not your recording."), frappe.PermissionError)
    if doc.status != "Recording":
        frappe.throw(_("This recording is already finished."))
    return doc


def _clean_mime(mime_type):
    base = (mime_type or "").split(";")[0].strip().lower()
    if base not in MIME_EXTENSIONS:
        frappe.throw(_("Unsupported audio format: {0}.").format(mime_type or "-"))
    return base


def _participants(ctx, chosen=None):
    """The recorder and, from ``choosable``, the classmates named as present."""
    people = list(ctx.get("participants") or [])
    choosable = {student: user for user, student in ctx.get("choosable") or []}
    if isinstance(chosen, str):
        chosen = json.loads(chosen or "[]")
    for student in chosen or []:
        if student not in choosable:
            frappe.throw(_("{0} cannot be named in this recording.").format(student))
        if all(s != student for _u, s in people):
            people.append((choosable[student], student))
    return people


def _limit(ctx):
    own = cint(ctx.get("max_seconds"))
    return min(own, max_seconds()) if own > 0 else max_seconds()


def _open_recording(
    reference_doctype, reference_name, mime_type, language, people, source
):
    ctx = _resolve(reference_doctype, reference_name)
    if not ctx.get("may_record"):
        frappe.throw(_("You cannot record this now."), frappe.PermissionError)
    if source == "Uploaded" and not ctx.get("allow_upload"):
        frappe.throw(_("This activity must be recorded here."), frappe.PermissionError)
    mime = _clean_mime(mime_type)
    chosen = [s for s in (ctx.get("steps") or []) if s in available_steps()]
    doc = frappe.get_doc(
        {
            "doctype": "Oral Recording",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "course_schedule": ctx.get("course_schedule"),
            "status": "Recording",
            "source": source,
            "recorded_by": frappe.session.user,
            "language": language or ctx.get("language"),
            "started_at": now_datetime(),
            "mime_type": mime,
            "steps": json.dumps([s for s in PIPELINE if s in chosen]),
            "participants": [
                {"user": user, "student": student}
                for user, student in _participants(ctx, people)
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    if ctx.get("on_start"):
        frappe.get_attr(ctx["on_start"])(doc.name)
    return doc, ctx


@frappe.whitelist(methods=["POST"])
def start_recording(
    reference_doctype, reference_name, mime_type=None, language=None, participants=None
):
    """Open a recording for one record. Returns its name.

    ``participants`` lists the students named as present (100b §3), from those
    the record lets this user choose."""
    doc, ctx = _open_recording(
        reference_doctype, reference_name, mime_type, language, participants, "Recorded"
    )
    os.makedirs(_chunk_dir(doc.name), exist_ok=True)
    return {"recording": doc.name, "max_seconds": _limit(ctx)}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60, ip_based=False, user_based=True)
def upload_recording(
    reference_doctype, reference_name, participants=None, language=None
):
    """A file recorded elsewhere, where the record allows it (100b §3). Its
    ``started_at`` is the upload time and its source says so."""
    files = frappe.request.files if frappe.request else None
    upload = files.get("file") if files else None
    if not upload:
        frappe.throw(_("No audio received."))
    ctx = _resolve(reference_doctype, reference_name)
    limit = _limit(ctx) * MAX_BYTES_PER_SECOND
    content = upload.stream.read(limit + 1)
    if not content:
        frappe.throw(_("No audio received."))
    if len(content) > limit:
        frappe.throw(_("This recording is longer than the school allows."))
    doc, _ctx = _open_recording(
        reference_doctype,
        reference_name,
        upload.mimetype,
        language,
        participants,
        "Uploaded",
    )
    _attach_audio(doc, content)
    return _finished(doc)


def _chunk_bytes(directory):
    return sum(
        os.path.getsize(os.path.join(directory, f)) for f in os.listdir(directory)
    )


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=240, seconds=60, ip_based=False, user_based=True)
def upload_chunk(recording, seq):
    """Store one chunk. Sending the same ``seq`` again replaces it."""
    doc = _own_open_recording(recording)
    seq = cint(seq)
    if seq < 0 or seq > 99_999:
        frappe.throw(_("Invalid chunk number."))
    files = frappe.request.files if frappe.request else None
    upload = files.get("chunk") if files else None
    if not upload:
        frappe.throw(_("No audio received."))
    content = upload.stream.read(MAX_CHUNK_BYTES + 1)
    if not content:
        frappe.throw(_("No audio received."))
    if len(content) > MAX_CHUNK_BYTES:
        frappe.throw(_("This piece of audio is too large."))
    return _store_chunk(doc, seq, content)


def _store_chunk(doc, seq, content):
    directory = _chunk_dir(doc.name)
    os.makedirs(directory, exist_ok=True)
    if _chunk_bytes(directory) + len(content) > max_seconds() * MAX_BYTES_PER_SECOND:
        frappe.throw(_("This recording is longer than the school allows."))
    path = os.path.join(directory, f"{seq:06d}")
    with open(path + ".part", "wb") as fh:
        fh.write(content)
    os.replace(path + ".part", path)
    return {"seq": seq}


@frappe.whitelist()
def received_chunks(recording):
    """The chunk numbers already stored, so a client can resend what is missing."""
    doc = _own_open_recording(recording)
    directory = _chunk_dir(doc.name)
    if not os.path.isdir(directory):
        return []
    return sorted(int(f) for f in os.listdir(directory) if f.isdigit())


@frappe.whitelist(methods=["POST"])
def finish_recording(recording, chunks):
    """Join chunks ``0 … chunks-1`` into the recording's audio and start its steps."""
    doc = _own_open_recording(recording)
    count = cint(chunks)
    if count <= 0:
        frappe.throw(_("Nothing was recorded."))
    directory = _chunk_dir(doc.name)
    have = set(received_chunks(doc.name))
    missing = [i for i in range(count) if i not in have]
    if missing:
        frappe.throw(
            _("Some of the recording has not arrived yet: pieces {0}.").format(
                ", ".join(str(i) for i in missing[:20])
            ),
            title=_("Recording incomplete"),
        )
    parts = []
    for i in range(count):
        with open(os.path.join(directory, f"{i:06d}"), "rb") as fh:
            parts.append(fh.read())
    content = b"".join(parts)
    _attach_audio(doc, content)
    shutil.rmtree(directory, ignore_errors=True)
    return _finished(doc)


def _attach_audio(doc, content):
    ext = MIME_EXTENSIONS.get(doc.mime_type, ".webm")
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"oral-{doc.name}{ext}",
            "is_private": 1,
            "attached_to_doctype": "Oral Recording",
            "attached_to_name": doc.name,
            "attached_to_field": "audio",
            "content": content,
        }
    )
    file_doc.save(ignore_permissions=True)
    doc.audio = file_doc.file_url


def _finished(doc):
    doc.ended_at = now_datetime()
    # An upload's length is only known once it is transcribed.
    doc.duration_s = (
        0
        if doc.source == "Uploaded"
        else max(
            0,
            int(
                (
                    get_datetime(doc.ended_at) - get_datetime(doc.started_at)
                ).total_seconds()
            ),
        )
    )
    doc.status = "Recorded"
    doc.step_state = json.dumps({s: "pending" for s in _steps_of(doc)})
    doc.save(ignore_permissions=True)
    frappe.enqueue(
        "seminary.seminary.oral.run_steps",
        recording=doc.name,
        queue="short",
        enqueue_after_commit=True,
        now=bool(frappe.flags.in_test),
    )
    return {"recording": doc.name, "status": doc.status}


# ------------------------------------------------------------------------ steps


def _steps_of(doc):
    try:
        return [s for s in json.loads(doc.steps or "[]") if s in PIPELINE]
    except ValueError:
        return []


def _state_of(doc):
    try:
        return json.loads(doc.step_state or "{}")
    except ValueError:
        return {}


def _segments(doc):
    try:
        return json.loads(doc.transcript or "[]")
    except ValueError:
        return []


def _ready(step, state):
    if step == "transcribe":
        return True
    if state.get("transcribe", "done") not in FINISHED:
        return False
    if step == "diarize":
        return True
    return state.get("diarize", "done") in FINISHED


def _payload(doc, step, ctx):
    base = {
        "recording": doc.name,
        "audio": doc.audio,
        "mime_type": doc.mime_type,
        "language": doc.language,
        "duration_s": doc.duration_s,
        "tracks": [
            {"label": s.label, "audio": s.audio, "offset_s": flt(s.audio_offset_s)}
            for s in doc.speakers
            if s.audio
        ],
        # Which steps follow and how many voices to expect, so a provider can
        # do transcription and speaker labels in one job.
        "steps": _steps_of(doc),
        "expected_speakers": ctx.get("expected_speakers") or len(doc.participants),
        # Someone is waiting on this result (a defense follow-up, 100c §3).
        "urgent": bool(ctx.get("urgent")),
    }
    if step == "transcribe":
        return base
    base["segments"] = _segments(doc)
    if step == "diarize":
        return base
    # Names a step must scrub from the transcript and the work before any
    # model reads them (aretenic decisions/091 §4). They are never sent on.
    base["redact"] = _names_of(doc)
    base.update(
        {
            "criteria": ctx.get("criteria") or [],
            "prompt": ctx.get("prompt"),
            "text": ctx.get("text"),
        }
    )
    return base


def _names_of(doc):
    names = set()
    # A captured meeting's speakers are labelled with display names (100d §4).
    if doc.get("activity_meeting"):
        labels = [s.label for s in doc.speakers] + frappe.get_all(
            "Oral Activity Meeting Participant",
            filters={"parent": doc.activity_meeting},
            pluck="display_name",
        )
        for value in labels:
            for part in [value, *(value or "").split()]:
                if part and len(part) >= 2:
                    names.add(part)
    for p in doc.participants:
        row = frappe.db.get_value(
            "Student",
            p.student,
            ["first_name", "middle_name", "last_name", "student_name"],
            as_dict=True,
        )
        for value in (row or {}).values():
            for part in [value, *(value or "").split()]:
                if part and len(part) >= 2:
                    names.add(part)
    return sorted(names)


def step_payload(recording, step):
    """What a step receives, for an app's trials (decisions/090): the same
    payload a run sends, built without running anything."""
    doc = frappe.get_doc("Oral Recording", recording)
    return _payload(doc, step, _context(doc))


def run_steps(recording):
    """Start every chosen step whose inputs are ready. Called after each result."""
    doc = frappe.get_doc("Oral Recording", recording)
    if doc.status in ("Recording", "Failed"):
        return
    steps = _steps_of(doc)
    state = _state_of(doc)
    if state.get("transcribe") == "skipped" or (
        "transcribe" not in steps and not _segments(doc)
    ):
        # Nothing to read: every step after the transcript is skipped too.
        for s in steps:
            if s != "transcribe" and state.get(s, "pending") == "pending":
                state[s] = "skipped"
    if all(state.get(s) in FINISHED for s in steps):
        doc.step_state = json.dumps(state)
        doc.status = "Ready"
        doc.save(ignore_permissions=True)
        return
    provided = provided_steps()
    allowed = set(allowed_steps())
    to_start = [
        s for s in steps if state.get(s, "pending") == "pending" and _ready(s, state)
    ]
    if not to_start:
        return
    for step in to_start:
        state[step] = "running" if step in provided and step in allowed else "skipped"
    doc.step_state = json.dumps(state)
    doc.status = "Processing"
    doc.save(ignore_permissions=True)
    running = [s for s in to_start if state[s] == "running"]
    if not running:
        run_steps(doc.name)
        return
    ctx = _context(doc)
    for step in running:
        try:
            frappe.get_attr(provided[step])(
                recording=doc.name, step=step, payload=_payload(doc, step, ctx)
            )
        except Exception as e:
            frappe.log_error(title=f"Oral step {step} could not start")
            step_failed(doc.name, step, str(e))
            return


def _number(value, what):
    try:
        number = float(value)
    except (TypeError, ValueError):
        frappe.throw(_("{0} must be a number.").format(what))
    if number < 0:
        frappe.throw(_("{0} cannot be negative.").format(what))
    return number


def _clean_segments(segments):
    if not isinstance(segments, list):
        frappe.throw(_("The transcript must be a list of segments."))
    clean = []
    for seg in segments:
        if not isinstance(seg, dict):
            frappe.throw(_("Each segment must be an object."))
        start = _number(seg.get("start"), "start")
        end = _number(seg.get("end"), "end")
        if end < start:
            frappe.throw(_("A segment cannot end before it starts."))
        row = {"start": start, "end": end, "text": str(seg.get("text") or "")}
        if seg.get("speaker") not in (None, ""):
            row["speaker"] = str(seg["speaker"])
        if isinstance(seg.get("words"), list):
            row["words"] = seg["words"]
        clean.append(row)
    return sorted(clean, key=lambda r: (r["start"], r["end"]))


def _apply_transcribe(doc, result):
    segments = _clean_segments(result.get("segments"))
    doc.transcript = json.dumps(segments)
    if not doc.duration_s and segments:
        doc.duration_s = int(max(s["end"] for s in segments))
    if result.get("language") and not doc.language:
        doc.language = str(result["language"])[:20]
    if any("speaker" in s for s in segments):
        _refresh_speakers(doc, segments)


def _apply_diarize(doc, result):
    segments = _segments(doc)
    labels = result.get("labels")
    if not isinstance(labels, list) or len(labels) != len(segments):
        frappe.throw(_("Speaker labels must give one label per transcript segment."))
    for seg, label in zip(segments, labels):
        if label in (None, ""):
            seg.pop("speaker", None)
        else:
            seg["speaker"] = str(label)
    doc.transcript = json.dumps(segments)
    _refresh_speakers(doc, segments)


def _apply_moments(doc, result):
    moments = result.get("moments")
    if not isinstance(moments, list):
        frappe.throw(_("Moments must be a list."))
    for m in moments:
        if not isinstance(m, dict):
            frappe.throw(_("Each moment must be an object."))
        moment = frappe.get_doc(
            {
                "doctype": "Oral Moment",
                "recording": doc.name,
                "source": "Suggested",
                "state": "Suggested",
                "start": _number(m.get("start"), "start"),
                "end": _number(m["end"], "end") if m.get("end") is not None else None,
                "criterion_code": m.get("criterion_code"),
                "question": m.get("question"),
                "note": m.get("reason") or m.get("note"),
            }
        )
        moment.flags.from_step = True
        moment.insert(ignore_permissions=True)


def _apply_staff_result(doc, step, result):
    frappe.get_doc(
        {
            "doctype": "Oral Step Result",
            "recording": doc.name,
            "step": step,
            "received_on": now_datetime(),
            "result": json.dumps(result),
        }
    ).insert(ignore_permissions=True)


APPLY = {
    "transcribe": _apply_transcribe,
    "diarize": _apply_diarize,
    "moments": _apply_moments,
}


def step_done(recording, step, result):
    """Record a step's result and start what it unblocks. Not a web endpoint:
    the app providing the step calls it from its own job or webhook."""
    doc = frappe.get_doc("Oral Recording", recording)
    if step not in _steps_of(doc):
        frappe.throw(_("Step {0} was not chosen for this recording.").format(step))
    state = _state_of(doc)
    if state.get(step) != "running":
        frappe.throw(_("Step {0} is not waiting for a result.").format(step))
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict):
        frappe.throw(_("A step result must be an object."))
    if step in STAFF_RESULTS:
        _apply_staff_result(doc, step, result)
    else:
        APPLY[step](doc, result)
    state[step] = "done"
    doc.step_state = json.dumps(state)
    doc.save(ignore_permissions=True)
    ctx_after = _context(doc).get("after_step")
    if ctx_after:
        frappe.get_attr(ctx_after)(doc.name, step)
    run_steps(doc.name)


def meeting_recorded(meeting, result):
    """A capture method's audio for one Oral Activity Meeting (decisions/100d §2).
    Not a web endpoint: the app providing the method calls it from its own job."""
    from seminary.seminary import oral_meetings

    return oral_meetings.meeting_recorded(meeting, result)


def meeting_failed(meeting, error=None):
    from seminary.seminary import oral_meetings

    return oral_meetings.meeting_failed(meeting, error)


def step_failed(recording, step, error=None):
    """A step could not finish. The recording stays playable and gradable by hand."""
    doc = frappe.get_doc("Oral Recording", recording)
    state = _state_of(doc)
    state[step] = "failed"
    doc.step_state = json.dumps(state)
    doc.status = "Failed"
    doc.error = (f"{step}: {error}" if error else step)[:1000]
    doc.save(ignore_permissions=True)


# ------------------------------------------------------------- reading, grading

STEP_LABELS = {
    "transcribe": "Transcription",
    "diarize": "Who spoke when",
    "moments": "Suggested moments",
    "questions": "Defense questions",
    "follow_up": "Follow-up questions",
    "score_suggestions": "Score suggestions",
    "consistency": "Consistency notes",
}


@frappe.whitelist()
def step_choices():
    """The steps an instructor may choose for an activity, with labels."""
    from seminary.seminary.guards import require_grader

    require_grader()
    return [{"step": s, "label": _(STEP_LABELS[s])} for s in available_steps()]


def _is_staff_of(doc):
    from seminary.seminary.guards import is_course_staff, is_school_role

    return is_school_role(frappe.session.user) or (
        bool(doc.course_schedule) and is_course_staff(doc.course_schedule)
    )


@frappe.whitelist()
def get_recording(recording):
    """A recording for its player: audio, status, transcript and speakers, and
    for the section's staff its moments. One message for missing and refused."""
    doc = (
        frappe.get_doc("Oral Recording", recording)
        if frappe.db.exists("Oral Recording", recording)
        else None
    )
    if not doc or not frappe.has_permission("Oral Recording", "read", doc=doc):
        frappe.throw(_("Recording not found."), frappe.PermissionError)
    staff = _is_staff_of(doc)
    out = {
        "name": doc.name,
        "status": doc.status,
        "source": doc.source,
        "audio": doc.audio,
        "audio_deleted_on": doc.audio_deleted_on,
        "duration_s": doc.duration_s,
        "started_at": doc.started_at,
        "transcript": _segments(doc),
        "speakers": _speakers_for(doc, staff),
        "people": [
            {
                "student": p.student,
                "name": frappe.db.get_value("Student", p.student, "student_name"),
            }
            for p in doc.participants
        ],
        "may_label": _may_label(doc, staff),
        "is_staff": staff,
        "moments": [],
    }
    if staff:
        out["error"] = doc.error
        out["step_results"] = [
            {
                "step": r.step,
                "received_on": r.received_on,
                "result": json.loads(r.result or "{}"),
            }
            for r in frappe.get_all(
                "Oral Step Result",
                filters={"recording": doc.name},
                fields=["step", "received_on", "result"],
                order_by="received_on desc",
            )
        ]
        out["moments"] = frappe.get_all(
            "Oral Moment",
            filters={"recording": doc.name, "state": ["!=", "Dismissed"]},
            fields=[
                "name",
                "start",
                "end",
                "source",
                "state",
                "criterion_code",
                "question",
                "note",
            ],
            order_by="start asc",
        )
    return out


def _speakers_for(doc, staff):
    """Every label and who it is linked to; talk time only for the staff, and
    for a student only their own (100b §6: never a classmate's)."""
    own = (
        None
        if staff
        else frappe.db.get_value("Student", {"user": frappe.session.user}, "name")
    )
    total = sum(flt(s.talk_s) for s in doc.speakers) or 1
    out = []
    for s in doc.speakers:
        row = {"label": s.label, "student": s.student}
        if staff or (own and s.student == own):
            row.update(
                {
                    "talk_s": s.talk_s,
                    "turns": s.turns,
                    "longest_turn_s": s.longest_turn_s,
                    "share": round(flt(s.talk_s) / total * 100),
                }
            )
        out.append(row)
    return out


def _may_label(doc, staff):
    if staff:
        return True
    if not any(p.user == frappe.session.user for p in doc.participants):
        return False
    try:
        ctx = _resolve(doc.reference_doctype, doc.reference_name)
    except frappe.PermissionError:
        return False
    rule = ctx.get("may_label")
    if isinstance(rule, str):
        return bool(frappe.get_attr(rule)(doc.name, frappe.session.user))
    return bool(rule)


@frappe.whitelist(methods=["POST"])
def link_speaker(recording, label, student=None):
    """Link a speaker label to a student on the recording, or unlink it (100b §5).
    Students on the recording may do it while the record allows; the section's
    staff may always correct it."""
    doc = (
        frappe.get_doc("Oral Recording", recording)
        if frappe.db.exists("Oral Recording", recording)
        else None
    )
    if not doc or not frappe.has_permission("Oral Recording", "read", doc=doc):
        frappe.throw(_("Recording not found."), frappe.PermissionError)
    if not _may_label(doc, _is_staff_of(doc)):
        frappe.throw(
            _("The speakers can no longer be changed."), frappe.PermissionError
        )
    row = next((s for s in doc.speakers if s.label == label), None)
    if not row:
        frappe.throw(_("There is no speaker {0} on this recording.").format(label))
    if student and all(p.student != student for p in doc.participants):
        frappe.throw(_("Only students on the recording can be linked to a speaker."))
    row.student = student or None
    doc.save(ignore_permissions=True)
    return {"label": label, "student": row.student}


def _staff_recording(recording):
    doc = frappe.get_doc("Oral Recording", recording)
    if not _is_staff_of(doc):
        frappe.throw(
            _("Only the section's staff can mark moments."), frappe.PermissionError
        )
    return doc


@frappe.whitelist(methods=["POST"])
def add_moment(
    recording, start, end=None, note=None, criterion_code=None, question=None
):
    """The instructor marks a passage by hand (100 §5)."""
    doc = _staff_recording(recording)
    moment = frappe.get_doc(
        {
            "doctype": "Oral Moment",
            "recording": doc.name,
            "source": "Instructor",
            "state": "Kept",
            "start": flt(start),
            "end": flt(end) if end not in (None, "") else None,
            "note": note,
            "criterion_code": criterion_code,
            "question": question,
        }
    )
    moment.insert(ignore_permissions=True)
    return moment.name


@frappe.whitelist(methods=["POST"])
def set_moment_state(moment, state, note=None):
    """Keep or dismiss a suggested moment, or edit a moment's note (100 §6)."""
    if state not in ("Kept", "Dismissed"):
        frappe.throw(_("A moment can only be kept or dismissed."))
    doc = frappe.get_doc("Oral Moment", moment)
    _staff_recording(doc.recording)
    doc.state = state
    if note is not None:
        doc.note = note
    doc.save(ignore_permissions=True)
    return doc.state


# -------------------------------------------------------------------- talk time


def talk_time(segments) -> dict:
    """{label: {talk_s, turns, longest_turn_s}} from labelled segments.

    Overlapping speech counts for both speakers. A turn is a run of consecutive
    segments by the same speaker.
    """
    stats = {}
    last_label, run_start, run_end = None, 0.0, 0.0

    def close_run():
        if last_label is None:
            return
        s = stats[last_label]
        s["longest_turn_s"] = max(s["longest_turn_s"], round(run_end - run_start, 2))

    for seg in sorted(segments, key=lambda r: (flt(r.get("start")), flt(r.get("end")))):
        label = seg.get("speaker")
        if label in (None, ""):
            continue
        start, end = flt(seg.get("start")), flt(seg.get("end"))
        s = stats.setdefault(label, {"talk_s": 0.0, "turns": 0, "longest_turn_s": 0.0})
        s["talk_s"] = round(s["talk_s"] + max(0.0, end - start), 2)
        if label != last_label:
            close_run()
            s["turns"] += 1
            last_label, run_start, run_end = label, start, end
        else:
            run_end = max(run_end, end)
    close_run()
    return stats


def _refresh_speakers(doc, segments):
    stats = talk_time(segments)
    existing = {row.label: row for row in doc.speakers}
    for label in stats:
        if label not in existing:
            existing[label] = doc.append("speakers", {"label": label})
    for label, row in existing.items():
        s = stats.get(label, {"talk_s": 0, "turns": 0, "longest_turn_s": 0})
        row.talk_s, row.turns, row.longest_turn_s = (
            s["talk_s"],
            s["turns"],
            s["longest_turn_s"],
        )


# ------------------------------------------------------------------ permissions


def has_permission(doc, ptype=None, user=None):
    """The students on the recording read it; the section's instructors read it
    within their tier; school roles read everything. Every write goes through
    this module, so the DocPerm grants students and instructors read only."""
    from seminary.seminary.guards import _roles, is_read_ptype, is_school_role
    from seminary.seminary.student_permissions import (
        _granted_by_another_role,
        _instructor_allows,
    )

    user = user or frappe.session.user
    if is_school_role(user) or _granted_by_another_role("Oral Recording", ptype, user):
        return True
    roles = _roles(user)
    if "Instructor" in roles and _instructor_allows(
        "Oral Recording", doc, ptype, user, "course"
    ):
        return True
    if "Student" in roles and is_read_ptype(ptype):
        return bool(
            frappe.db.exists(
                "Oral Recording Participant",
                {"parent": doc.name, "parenttype": "Oral Recording", "user": user},
            )
        )
    return False


def get_permission_query_conditions(user=None):
    from seminary.seminary.guards import _roles, is_school_role
    from seminary.seminary.student_permissions import (
        _granted_by_another_role,
        _instructor_condition,
    )

    user = user or frappe.session.user
    if is_school_role(user) or _granted_by_another_role("Oral Recording", "read", user):
        return ""
    parts = []
    roles = _roles(user)
    if "Instructor" in roles:
        cond = _instructor_condition("Oral Recording", user, "course")
        if cond == "":
            return ""
        if cond:
            parts.append(cond)
    if "Student" in roles:
        parts.append(
            "`tabOral Recording`.name in (select parent from `tabOral Recording Participant` "
            f"where parenttype = 'Oral Recording' and user = {frappe.db.escape(user)})"  # nosec B608 -- escaped
        )
    if not parts:
        return "1=0"
    return "(" + " or ".join(parts) + ")"


# -------------------------------------------------------------------- retention


def daily():
    sweep_abandoned()
    delete_expired_audio()


def sweep_abandoned():
    """A recording left open for a day will not be finished: drop its chunks."""
    cutoff = now_datetime() - timedelta(hours=ABANDONED_HOURS)
    for name in frappe.get_all(
        "Oral Recording",
        filters={"status": "Recording", "started_at": ["<", cutoff]},
        pluck="name",
        limit=500,
    ):
        shutil.rmtree(_chunk_dir(name), ignore_errors=True)
        frappe.db.set_value(
            "Oral Recording",
            name,
            {"status": "Failed", "error": "The recording was never finished."},
        )


def _expiry(doc, days):
    """When the audio may go, or None while it must stay."""
    students = [p.student for p in doc.participants if p.student]
    if not students and doc.get("activity_meeting") and doc.ended_at:
        # A captured meeting nobody was confirmed on waits for no one's grades.
        return add_days(get_datetime(doc.ended_at), days)
    if not students or not doc.course_schedule:
        return None
    sent = frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": doc.course_schedule, "student": ["in", students]},
        fields=["student", "grades_sent_on"],
    )
    by_student = {r.student: r.grades_sent_on for r in sent}
    if any(not by_student.get(s) for s in students):
        return None
    return add_days(max(get_datetime(by_student[s]) for s in students), days)


def _on_hold(doc):
    students = [p.student for p in doc.participants if p.student]
    return bool(students) and bool(
        frappe.db.exists(
            "Student Hold",
            {"parenttype": "Student", "parent": ["in", students], "is_active": 1},
        )
    )


def delete_expired_audio():
    days = cint(_settings().get("oral_audio_retention_days") or 365)
    now = now_datetime()
    names = frappe.get_all(
        "Oral Recording",
        filters={
            "status": ["!=", "Recording"],
            "audio": ["is", "set"],
            "audio_deleted_on": ["is", "not set"],
        },
        pluck="name",
        limit=500,
    )
    for name in names:
        doc = frappe.get_doc("Oral Recording", name)
        expiry = _expiry(doc, days)
        if not expiry or now < expiry or _on_hold(doc):
            continue
        delete_audio(doc)


def delete_audio(doc):
    for file_name in frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Oral Recording", "attached_to_name": doc.name},
        pluck="name",
    ):
        frappe.delete_doc(
            "File", file_name, ignore_permissions=True, delete_permanently=True
        )
    doc.audio = None
    for row in doc.speakers:
        row.audio = None
    doc.audio_deleted_on = now_datetime()
    doc.save(ignore_permissions=True)
