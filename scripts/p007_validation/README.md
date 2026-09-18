# p007 Phase 1 validation harness

Runs the API-checkable rows of privatedocs/p007 §4 against `potestas.localhost`
(bench on port 8006, fake data only). Not part of the app; nothing here is
imported by seminary. Builds on the p006 harness in `../p006_validation`
(session helpers, fixtures, the Phase 0 matrix that must still pass).

Order (with the bench's Python):

```
cd /home/drmrmelo/lms/sites
../env/bin/python ../apps/seminary/scripts/p006_validation/p0fixtures.py  > ../apps/seminary/scripts/p006_validation/fx.json
../env/bin/python ../apps/seminary/scripts/p006_validation/p0fixtures2.py
../env/bin/python ../apps/seminary/scripts/p007_validation/p1fixtures.py   # tiers, gta, instrU, units, withdrawals, chapel rows; writes fx1.json
cd ../apps/seminary/scripts/p007_validation
../../../../env/bin/python p1matrix.py                                     # the §4.1–4.7 rows, PASS/FAIL and a summary
cd /home/drmrmelo/lms/sites
../env/bin/python ../apps/seminary/scripts/p006_validation/p0reset.py
../env/bin/python ../apps/seminary/scripts/p006_validation/p0matrix.py     # Phase 0 regression: must still pass
```

`p1fixtures.py` also makes the p006 instructors instructors of record and hands
the p006 submissions to their students (the Student write row is `if_owner`),
so run it before the Phase 0 matrix on a Phase 1 branch.

Session users (password `P0test!2026`): `stuA`, `stuB`, `instr3` (of record,
on CS only), `instr2` (of record, on CS_B), `gta` (Student + Grader on CS,
enrolled in CS_B), `instrU` (of record, member of the Systematic Theology unit,
listed nowhere), `chair`, `reg` (Student + Registrar), `admin`.

`whitelist_survey.md` is the endpoint classification the ADR and the walk test
(`seminary/seminary/tests/test_p007_whitelist_walk.py`) rest on.
