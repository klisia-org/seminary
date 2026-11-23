# 103 — Reordering the course outline by keyboard

**Date:** 2026-11-23
**Status:** Accepted 2026-11-23; implemented 2026-11-23
**Related:** 102 (accessibility conformance), p009 §2.10 (SCORM chapters), 079 (reflection lessons)

## Context

An instructor reorders chapters and lessons by dragging them in the course outline, and there is
no other way. Someone using a keyboard or a screen reader can't reorder at all (WCAG 2.1.1). The
chapter's Edit and Delete icons only appear on hover and can't take focus either. The
accessibility lint reports the drag targets as its last five findings in seminary.

## Decision

1. **Every chapter and lesson an instructor can move gets a Move menu,** a button beside its
   title that shows on hover and on focus. A chapter offers *Move up* and *Move down*. A lesson
   offers the same, plus *Move to* each other chapter, which places it at the end of that
   chapter.
2. **The menu calls the same endpoints as a drop,** so the existing rules still apply: nothing
   moves into or out of a SCORM chapter, and a reflection lesson has no menu, just as it can't
   be dragged.
3. **The result is announced and focus stays on what moved.** The toast says where it went, e.g.
   "Moved to position 3 in Chapter 2". After the outline reloads, focus returns to that item's
   Move button.
4. **Edit Chapter and Delete Chapter become buttons with names,** visible on focus as well as on
   hover.
5. **Dragging stays.** The drop zones are a pointer shortcut for the menu, and each is opted out
   of the lint with that reason.

## Consequences

Every move can now be made with a keyboard. It costs one more control on each row, and it only
shows on hover or focus. Seminary's lint backlog is then empty, so its rules switch on.
