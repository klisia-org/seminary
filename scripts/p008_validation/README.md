# p008 validation harness

Live reproductions against `potestas.localhost` (bench on :8006). They reuse the
p006 harness for login and CSRF, so the fixture passwords must be current:

    ../../env/bin/python scripts/p008_validation/<script>.py

`requests` lives in the bench virtualenv, not the system python.

| script | what it pins |
| --- | --- |
| `verify_archives_on_r2.py` | p008 F17 against a **real object store**, which no unit test reaches: the artifact is offloaded, the object is really in the bucket at the recorded size, it reads back as a valid zip through `materialize`, the endpoint hands back a URL rather than building, a presigned GET is signable, and a SCORM package validates through the store. Run it through `bench console` with an **absolute** path — console's cwd is `sites/`. Rolls the database back; the objects it PUT remain. |
| `repro_student_lesson.py` | the two errors the p008 browser pass found on a student's lesson page: `get_lesson` 500 on a lesson with no legacy `body`, and `save_progress` 403 because p007 F1 took Student write off Scheduled Course Roster. The last row checks the row itself stays closed. |

Each row prints `BROKEN` before the fix and `ok` after. Nothing here is a
substitute for `seminary/seminary/tests/test_p008*` — these run against real
fixture data, the tests run on `testable.localhost`.
