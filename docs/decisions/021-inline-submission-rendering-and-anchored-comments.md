# 021 — Inline Submission Rendering and Anchored Grading Comments

**Date:** 2026-05-23
**Status:** Accepted

## Context

The Assignment Submission grading view rendered uploaded files as a download
link and a single `comments` Text Editor blob — professors had to download
each PDF / image / document, mark it up locally, and write generic feedback.
Quizzes/Discussions/Exams had their own grading flows; assignments didn't.
On the student side, the only feedback channel was that same one blob.

The redesign needed to render every submission type in the browser, let
profs leave feedback anchored to a page region, an image pin, or a video
timestamp, and give students a mirror view so they could see exactly where
each comment points. It also needed to introduce a YouTube type for sermon-
delivery feedback — a workflow the alumni Continuing Education module is
expected to reuse unchanged.

## Decision

### Submission types and viewers

Six types, one viewer component each, dispatched by `SubmissionViewer.vue`:
PDF (`pdfjs-dist`), Image (`<img>`), Text (read-only `v-html`), Document
(`mammoth.js` for `.docx`; download fallback for legacy `.doc`), URL (link
card), **YouTube** (IFrame Player API). YouTube is a first-class Assignment
Activity type, separate from URL — its UI/embed differs and the timestamp
anchor model is unique to it.

`pdfjs-dist` is used from Phase 1 even though a native `<iframe>` would
render PDFs more cheaply, because Phase 2 region pins need coordinates the
iframe doesn't expose. No throwaway viewer.

`mammoth.js` runs in the browser; LibreOffice server-side conversion is
deferred (added when fidelity becomes a real complaint). `.doc` files
stay as download links with an explicit "no inline preview" note.

### One child doctype, many anchor flavors

Anchored comments live in `Assignment Submission Comment`, a child table on
`Assignment Submission` (`comments_thread`). A `Select` `anchor_type` field
(`General | Page | Region | TextRange | Timestamp`) discriminates;
`depends_on` conditionals scope the per-type fields (`page`, `x_pct`,
`y_pct`, `range_from/to`, `timestamp_s`). Image pins reuse `Region` with
`page=1` — one schema for both image and PDF pin overlays, one API surface
(`get/add/update/delete_submission_comment`), one render path per overlay
component. The existing single `comments` field is kept for back-compat;
new feedback flows through the child table.

### `postComment` lives in `SubmissionViewer`, not the sidebar

`pendingAnchor` is held by `SubmissionViewer` (which owns both viewer and
sidebar). The "post" action is also defined there and passed to
`CommentSidebar` as an `onPost` callback prop. Earlier the sidebar made
the API call itself, reading `pendingAnchor` via a prop — that introduced
a reactivity race where pin anchors silently became `General`. Lifting the
action to where the state lives eliminates the prop hop entirely. The
sidebar stays pure UI; per-row edit/resolve/delete (which don't depend on
parent state) remain there.

### Edit-lock policy

Once any `Assignment Submission Comment` row exists, `canModifyAssignment`
returns false — the student can no longer change the answer or attachment.
Comments would otherwise risk pointing at stale content. The lock takes
effect on next page load (the resource's `comments_thread` is what was
fetched).

### `canComment` flows down

A `canComment` Boolean passes from `Assignment.vue` through `SubmissionViewer`
into every viewer and the sidebar. Students get `false`: the input section
and per-row action buttons hide; the click-to-anchor handlers no-op; the
crosshair cursor reverts. The backend enforces the same gate
(`_can_grade_submission`) — UI hiding is defence in depth, not the
permission boundary.

### Dashboard tolerates `NULL` course

`get_assignment_dashboard` counts roster members with
`(course = X OR course IS NULL)`. Roughly a third of historical Assignment
Submissions in production carry no course tag (Text submissions
particularly; an Assignment-specific quirk no other submission type has).
The roster filter is the real scope; the `course` filter would just
exclude legitimate work and silently undercount.

### `RichTextEditor` (Teleport) for ProseMirror in deep DOM

The student answer input and prof comments box use `RichTextEditor`, which
Teleports the editor to `<body>` with `z-index: 9999`. This avoids the
known ProseMirror crash in deeply nested DOM. A global
`.PopoverContent { z-index: 10000 }` rule (in `RichTextEditor.vue`) keeps
the menu's heading / font-color dropdowns visible above the teleported
wrapper — they portal to `<body>` too but ship with no z-index.
`TextViewer.vue` doesn't use any editor — pure `<div v-html>`, since
read-only display doesn't need ProseMirror at all.

### Lazy chunking in `vite.config.js`

`pdfjs-dist` and `mammoth` are split out of `vendor` so they load only
when an instructor opens a PDF or `.docx` submission. The same audit
pulled `@editorjs/*`, `highlight.js`, `markdown-it`, and `socket.io-client`
into their own named chunks — even though those are reached eagerly via
`utils/index.js` / `LessonContent.vue` / `main.js`, separating them lets
them download in parallel and cache independently of `vendor`. Vendor
shrank from 3.84 MB to 2.75 MB minified.

## Consequences

- Profs grade in the browser; no more download-mark-upload round trip. Each
  feedback anchor stays visible in the student's mirror view, with
  bidirectional hover-sync between the sidebar list and the viewer pins.
- The child doctype + anchor model is provider-agnostic on the timestamp
  axis, so the alumni sermon-feedback CE workflow can reuse it unchanged
  (and Vimeo / other video providers are a one-file frontend addition).
- **Open: text-range comments on Text submissions.** Schema and API
  support `anchor_type='TextRange'`; the overlay needs a ProseMirror
  `comment` mark extension on a read-only Tiptap instance — significant
  work, deferred. Text submissions get general comments only for now.
- **Open: `.doc` rendering.** Download-only. Revisit if the server-side
  LibreOffice/queue/cache pattern becomes worth its operational weight.
- **Open: the old single `comments` field.** Coexists with the child
  table; profs may post in either. Worth deciding later whether to
  deprecate the blob or surface both threads in the sidebar.
- The "parent owns state, sidebar emits to a parent-supplied callback"
  pattern from `SubmissionViewer ↔ CommentSidebar` is the right shape for
  any editor + side-panel pair where the side-panel needs parent state at
  call time. Reusable.
