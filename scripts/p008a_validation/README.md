# p008a Phase 1.5 validation harness

Reproduces and then regression-checks the p005a findings that p008a fixes, against
`potestas.localhost` (bench on port 8006, fake data only). Not part of the app;
nothing here is imported by seminary. Builds on the p006/p007 harnesses for the
session helpers (`p0check.jar/call`) and fixtures.

Order (with the bench's Python):

```
cd /home/drmrmelo/lms/sites
../env/bin/python ../apps/seminary/scripts/p008a_validation/p15fixtures.py   # writes fx15.json
cd ../apps/seminary/scripts/p008a_validation
../../../../env/bin/python repro_reads.py     # A04-3, A01-18, A01-15, A01-16 -- reads only
../../../../env/bin/python repro_writes.py    # A01-11, A01-12, A01-13, A01-14 -- restores what it changes
../../../../env/bin/python repro_a02_7.py     # A02-7 -- restores what it changes
```

`p15fixtures.py` adds one persona the p006/p007 sets do not have: `p15.sec@example.org`
(`INST-00017`), an Instructor listed on `CS` as **Grader** whose
`Instructor.default_inst_category` is **blank**. That blank default is the precondition
A01-13 requires -- `validate_instructor_of_record_rows` throws only
`if default and default not in of_record`, so an instructor with a non-of-record default
(the p007 `gta`, whose default is `Grader`) is correctly refused and cannot demonstrate
the finding. Re-run the fixture script to reset the row to `Grader` after a repro.

Before the p008a fixes land, every row prints `VULNERABLE`. After they land the same
scripts are the regression check and every row must print `safe`.

**`seminary.tasks.daily` is deliberately never called.** It flips `Academic Term`
flags app-wide and recomputes attendance for every section, which would corrupt the
p006 and p007 fixtures. `hourly` carries the same decorator and proves the same
reachability.

Results of the first run (2026-09-19, `a7abe81d`) are recorded in
`privatedocs/p005a-OWASP-register-rerun.md` §7.1.
