# p008 validation harness

Live reproductions against `potestas.localhost` (bench on :8006). They reuse the
p006 harness for login and CSRF, so the fixture passwords must be current:

    ../../env/bin/python scripts/p008_validation/<script>.py

`requests` lives in the bench virtualenv, not the system python.

| script | what it pins |
| --- | --- |
| `repro_student_lesson.py` | the two errors the p008 browser pass found on a student's lesson page: `get_lesson` 500 on a lesson with no legacy `body`, and `save_progress` 403 because p007 F1 took Student write off Scheduled Course Roster. The last row checks the row itself stays closed. |

Each row prints `BROKEN` before the fix and `ok` after. Nothing here is a
substitute for `seminary/seminary/tests/test_p008*` — these run against real
fixture data, the tests run on `testable.localhost`.
