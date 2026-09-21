# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The CMI data model: what is persisted, and what every value must be (p009 §2.9).

Two SCORM versions, one internal shape. SCORM 1.2 says `cmi.core.lesson_status`
and folds completion and success into one vocabulary; 2004 splits them into
`cmi.completion_status` and `cmi.success_status`. Both map onto the same
`SCORM Attempt` fields, so the rest of the app never learns which version a
package speaks.

**The allow-list is closed.** The launcher accepts and answers the *whole* data
model locally -- spec compliance is a client-side property, and a package that
asks for `cmi.interactions.0.id` should get an answer rather than an error -- but
an element that is not named here never reaches the database. An unknown element
is version skew and is dropped; a malformed *value* on a known element is the
attack, and throws. Same discipline as `course_pack/constants.py`.

Nothing here touches frappe, so the rules are testable on their own and the
error messages say which value was refused rather than "invalid".
"""

from __future__ import annotations

import re

#: SCORM error codes a package can read back through `LMSGetLastError`.
ERR_GENERAL = "101"
ERR_TYPE_MISMATCH = "406"
ERR_OUT_OF_RANGE = "407"

#: `cmi` element -> the `SCORM Attempt` field it lands in. Everything else is
#: dropped on the way in, silently, because it is skew rather than attack.
ELEMENTS = {
    # --- SCORM 2004 -------------------------------------------------------
    "cmi.completion_status": "completion_status",
    "cmi.success_status": "success_status",
    "cmi.score.raw": "score_raw",
    "cmi.score.min": "score_min",
    "cmi.score.max": "score_max",
    "cmi.score.scaled": "score_scaled",
    "cmi.location": "location",
    "cmi.suspend_data": "suspend_data",
    "cmi.session_time": "session_time",
    "cmi.total_time": "total_time",
    # --- SCORM 1.2 --------------------------------------------------------
    # `lesson_status` is one field over there and two here; it is expanded by
    # `normalise` rather than mapped, so it has no entry.
    "cmi.core.score.raw": "score_raw",
    "cmi.core.score.min": "score_min",
    "cmi.core.score.max": "score_max",
    "cmi.core.lesson_location": "location",
    "cmi.core.session_time": "session_time",
    "cmi.core.total_time": "total_time",
}

LESSON_STATUS = "cmi.core.lesson_status"

COMPLETION_VALUES = {"completed", "incomplete", "not attempted", "unknown"}
SUCCESS_VALUES = {"passed", "failed", "unknown"}

#: 1.2 folds the two together. `browsed` is a visit, not progress towards
#: completion, and is recorded as such rather than discarded.
LESSON_STATUS_MAP = {
    "passed": ("completed", "passed"),
    "failed": ("completed", "failed"),
    "completed": ("completed", "unknown"),
    "incomplete": ("incomplete", "unknown"),
    "browsed": ("incomplete", "unknown"),
    "not attempted": ("not attempted", "unknown"),
}

#: 1.2: `hhhh:mm:ss[.ss]`. 2004: an ISO 8601 duration, always starting `P`.
_TIME_1_2 = re.compile(r"^\d{2,4}:[0-5]\d:[0-5]\d(\.\d{1,2})?$")
_TIME_2004 = re.compile(
    r"^P(?=\d|T\d)(\d+Y)?(\d+M)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+(\.\d{1,2})?S)?)?$"
)

MAX_LOCATION = 1000
DEFAULT_MAX_SUSPEND = 64000  # scorm_max_suspend_bytes -- the 2004 4th ed limit


class CMIError(ValueError):
    """A value the data model does not allow.

    Carries a SCORM error code so the package can read a sensible answer back
    rather than a broken call. The code is a class attribute overridden per
    instance by `_refuse` rather than an `__init__` kwarg: an exception whose
    `__init__` does not pass its arguments through to `super()` breaks under
    `copy` and `pickle`, and passing the code through would put it inside
    `str(e)` -- which is the text that reaches the log and the runtime.
    """

    code: str = ERR_GENERAL


def _refuse(message: str, code: str = ERR_GENERAL) -> CMIError:
    error = CMIError(message)
    error.code = code
    return error


def normalise(data: dict) -> dict:
    """`{cmi element: value}` -> `{attempt field: value}`, allow-list applied.

    Values are not validated here beyond what is needed to expand
    `lesson_status`; the controller validates, so that no write path can skip
    it -- including one that does not come through `commit` at all.
    """
    if not isinstance(data, dict):
        raise _refuse("The runtime sent something that is not a data model.")

    out: dict[str, object] = {}

    status = data.get(LESSON_STATUS)
    if status is not None:
        key = str(status).strip().lower()
        if key not in LESSON_STATUS_MAP:
            raise _refuse(
                f"lesson_status {status!r} is not a SCORM 1.2 status.",
                ERR_TYPE_MISMATCH,
            )
        completion, success = LESSON_STATUS_MAP[key]
        out["completion_status"] = completion
        # 1.2 has no separate success vocabulary, so `unknown` here means "this
        # package never said" -- it must not overwrite a pass already recorded.
        if success != "unknown":
            out["success_status"] = success

    for element, field in ELEMENTS.items():
        if element in data:
            out[field] = data[element]

    return out


# ------------------------------------------------------------------ validators


def check_vocabulary(field: str, value, allowed: set[str]) -> str:
    text = str(value or "").strip().lower()
    if text not in allowed:
        raise _refuse(
            f"{field} {value!r} is not one of {sorted(allowed)}.", ERR_TYPE_MISMATCH
        )
    return text


def check_number(field: str, value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as e:
        raise _refuse(f"{field} {value!r} is not a number.", ERR_TYPE_MISMATCH) from e


def clamp(value: float, low: float, high: float) -> float:
    """Scores are **clamped, not refused**.

    A package that reports 110 out of 100 is badly written, not hostile, and
    refusing the commit would lose the student's real progress along with the
    bad number. Bounds-checking makes the claim well-formed; §2.12 is what keeps
    it from being treated as an assessment.
    """
    return min(max(value, low), high)


def check_time(field: str, value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if _TIME_1_2.match(text) or _TIME_2004.match(text):
        return text
    raise _refuse(f"{field} {value!r} is not a SCORM duration.", ERR_TYPE_MISMATCH)


def check_length(field: str, value, limit: int) -> str:
    text = "" if value is None else str(value)
    if len(text) > limit:
        raise _refuse(
            f"{field} is {len(text)} characters; the limit is {limit}.",
            ERR_OUT_OF_RANGE,
        )
    return text
