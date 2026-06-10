# 041 — Course Packs: portable, full-fidelity course bundles

**Date:** 2026-06-10
**Status:** Accepted

## Context

The platform should let independent seminary installs **share courses and adapt
them** — a library smaller/under-resourced schools contribute to and pull from.
The within-site `import_template` (ADR 014) copies a Course Schedule's structure
but only *shares Links* to assessment activities; it carries no quizzes, exams,
questions, media or grading config, and cannot cross sites. The SCORM
chapter-import is unsuitable (static-serve, no runtime, uneditable — the opposite
of "make it theirs").

## Decision

Add a **Course Pack**: a self-contained `.zip` exporting a Course Schedule's full
authored content, importable on any other site as fresh, fully-editable local
records. Module: `seminary/seminary/course_pack/` (`export.py`, `import_.py`,
`editorjs.py`, `constants.py`).

Key choices:

- **Identity = source docnames, remapped on import.** The manifest keys every
  record by its source docname and lesson content keeps references verbatim;
  import builds `source_name → new_name` / `source_url → new_url` maps and does a
  single rewrite pass. This mirrors `import_template`'s existing map approach
  rather than introducing a second synthetic-id layer (a simplification of the
  plan's "pack-local ids" — same goal: import never assumes a source name is free).
- **Carry content, strip state.** Explicit per-doctype allow-lists in
  `constants.py` (deny-by-default). Stripped: roster, grades, dates, room,
  instructors, workflow, calendar_token, seat caches, fetch caches, metadata.
- **Bundle all media** (public + private) by **content hash** (auto-dedup); SCORM
  zips re-extracted on import. EditorJS `content` and legacy `body` macros are
  scanned for both activity refs and `/files` URLs; rich-text HTML fields are
  scanned generically for embedded media. The URL scanner allows literal spaces
  (Frappe stores them) and the File lookup tries both raw and percent-decoded forms.
- **Course Folders** are bundled in full: the folder is referenced by *foldername*
  (not docname), so export resolves the Course Folder by (foldername, course),
  walks its File tree into the pack, and import recreates the folder, rebuilds the
  files inside it, and remaps the content reference (deduping the foldername on clash).
- **Institution deps create-if-missing by stable name** (Grading Scale,
  Assessment Criteria). On a name clash with different content: **reuse the local
  one and warn** — never overwrite institutional config, never hard-fail.
- **Import builds a Draft Course Schedule** under a Course the importer chooses
  (new or existing), with a strict write order so references resolve: media →
  questions → activities → SCAC → chapters/lessons → lesson SCAC-link remap.
  Direct child-doc inserts, **no parent `self.save()`** (extends ADR 014's
  denorm-race rationale to a new writer).
- **SCORM export is out of scope for v1** (the native pack is the platform path).

## Consequences

- A course's quizzes/exams/questions/grading/media now move between sites as new,
  editable docs — the foundation for a shared library. The pack format
  (`pack_format_version`) is hub-ready; only the bundle is built now.
- **Single transaction, all-or-nothing.** Caveat: `save_file` writes media bytes
  before commit, so a mid-import failure rolls back the DB but can orphan bytes on
  disk (unreferenced, harmless). No resume — re-run on failure.
- The imported CS is an incomplete Draft (no dates/room/instructors); the registrar
  completes it, or copies it onward with `import_template`.
- New whitelisted methods + desk JS require `bench restart` / clear-cache.
- Packs with recorded video can be large (incompressible); import respects the
  ADR 040 upload limits. Future: stream to a hub instead of building in memory.
- Adding a new field to a carried doctype will NOT appear in packs until added to
  the relevant allow-list in `constants.py` (deliberate).
