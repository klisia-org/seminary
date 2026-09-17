# p006 Phase 0 validation harness

Runs the API-checkable rows of privatedocs/p006 §4 against `potestas.localhost`
(bench on port 8006, fake data only) and the inter-school pack round trip into
`testable.localhost`. Not part of the app; nothing here is imported by seminary.

Order (all from this directory, with the bench's Python):

```
cd /home/drmrmelo/lms/sites
../env/bin/python <here>/p0fixtures.py  > <here>/fx.json   # seeds users, submissions, holds, a second section
../env/bin/python <here>/p0fixtures2.py                    # scoped folders, lessons embedding them, third instructor
../env/bin/python <here>/p0reset.py                        # returns fixtures to the pre-matrix state (repeatable)
../env/bin/python <here>/p0matrix.py                       # 102 rows, prints PASS/FAIL and a summary
../env/bin/python <here>/p0pack.py                         # export on potestas as a chair, import on testable
```

Passwords for the session users are set to `P0test!2026` by the fixture scripts
(`bench --site potestas.localhost set-password`). The matrix logs in through
`/api/method/login`, renders one portal page to obtain a CSRF token, and then
exercises each endpoint as guest, two students, three instructors, a
Student+Registrar user, a Program Chair and Administrator.

`p0matrix.py` is deliberately not idempotent (it grades, enrolls, re-scopes
folders); run `p0reset.py` before every run. `p0pack.py` reuses `p0pack.zip`
when present; delete it to force a fresh export.
