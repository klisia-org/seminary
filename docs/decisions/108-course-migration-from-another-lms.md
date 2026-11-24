# 108 — Course migration from another LMS

**Date:** 2026-11-23
**Status:** Accepted 2026-11-23; amended 2026-11-23 (§1: Moodle 5.0–5.3)
**Delivers:** LMS-IMP-01 (Yes)
**Related:** 014 (course template import), 041 (course packs), 094 (history import),
095 (rubrics), 097 (course discussions), 106 (QTI import), 107 (chapter release), p009 (SCORM)

## Context

A school moving to seminary wants its courses to come across, not only its quizzes. Today only
106 reads another LMS, and only for questions. Course packs (041) move whole courses, but only
between seminary sites. A SCORM chapter (p009) plays a package but can't be edited. Canvas,
Blackboard, Brightspace and Schoology export IMS Common Cartridge. Moodle's Common Cartridge
export drops quiz settings, books and grading, so Moodle schools need their native backup read.
Populi is only an SIS: it brings programs and courses, not course content. Schools also ask what
they will have to rebuild by hand.

## Decision

1. **Import course** on a Course Schedule with no chapters (014's rule) accepts a Common
   Cartridge 1.1–1.3 (`.imscc`) or a Moodle 5.0–5.3 backup (`.mbz`); a backup from another Moodle
   release is refused with its release named. It reuses 041's import: new local,
   editable records, source ids mapped to new names, files stored by content hash, and one pass
   to rewrite links.
2. **Mapping:**
   - modules or Moodle sections → chapters;
   - pages, Moodle pages/books and web links → lessons, with HTML converted to EditorJS blocks;
   - files → the course's Course Folder;
   - assignments → Assignment Activity, with Canvas rubrics → 095 rubrics;
   - discussion topics and Moodle forums → Discussion Activity (097), with no posts;
   - quizzes → Quiz or Exam Activity through 106's QTI reader. In `.mbz`, the question bank's
     XML is read for the same types.
3. **Export course** writes a Common Cartridge 1.3 from a Course Schedule, so a school can leave
   or share with a school on another LMS. It writes the same items as §2 in reverse, plus a QTI
   2.1 quiz bank.
4. **Rebuild by hand** is stated in two places. The import report lists every skipped item and
   why. A user-guide page lists what never comes across: student work and grades (094's job),
   gradebook weights and categories, release dates and prerequisites (107), groups, LTI tools,
   SCORM settings, H5P, Moodle workshops/lessons/glossaries, and the question types 106 skips.
5. **Populi** needs no reader. Programs and courses come through Frappe's Data Import with a
   CSV template for each, as 094 does for history.
6. Packages are read with `defusedxml` under 041's size and entry limits.

Rejected: importing through SCORM, which keeps nothing editable. Reading only Common Cartridge,
including Moodle's export: Moodle schools would rebuild quizzes and books, and Moodle is common
among small seminaries. Importing student work: it belongs to the record, not the course (094).

## Consequences

A school brings each course in with one upload and gets a written list of what to rebuild. A
school can also take its courses out in a standard format. 106's rejection of Moodle XML is
narrowed: the format is read only inside a `.mbz`. Two formats share one mapping, and Moodle's
backup format changes between versions, so only 5.0–5.3 are read, and readers need fixtures from real
exports. A school on an older Moodle upgrades first or uses Common Cartridge.

## As built

- §1: the section's assessment rows are replaced only when the course brings graded work. Each
  new row has a weight of 0, so the section can't be saved until someone sets the weights.
- §1: the accepted releases are one tuple in `lms_migration/moodle.py`. Each backup's
  `moodle_release` is cut to its major.minor (`5.3.1+ (Build: …)` gives 5.3) and checked against
  that tuple. Both tar.gz and zip backups are read. 5.0–5.3 were widened from 5.3 after a diff of
  Moodle's backup code on 2026-11-23: the parts this reader uses differ only by fields Moodle added.
  Re-run that diff before adding 6.0.
- §2: a quiz with essay questions becomes a quiz plus an exam named "(written)". Canvas's
  `non_cc_assessments` QTI is read before the standard copy, because it keeps every question type.
  A Canvas rubric's ratings are placed on the default rubric scale's nearest level by percentage,
  and each criterion's weight comes from its points.
- §2: some things are skipped and listed in the report: Canvas announcements, the Moodle news
  forum, LTI tools, block-editor pages, and PDFs this site would refuse. Pages and activities no
  module points at go into a last chapter, "Not in a module".
- §3: QTI 2.1 items are resources outside the outline. The export is built in memory, like a pack
  without object storage.
- 041: a discussion block stores its reference under `discussion`. Packs now remap that key too.
  Before this change they missed it.
- The test fixtures are synthetic. Their element names were checked against Moodle and Canvas
  source on 2026-11-23.
