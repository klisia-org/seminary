# 080 — Course image framing on the portal

**Date:** 2026-09-24
**Status:** Accepted 2026-09-24

## Context

The course tile fills its box with `course_image` and always centres it, so a subject off-centre
is cut away. The tile was 3:2 on desktop and 4:3 on phones, so one image was cut two ways.
Instructors want to choose what the tile shows. Desk does not need it.

## Decision

1. **Framing is stored, not baked.** Course Schedule gets three hidden fields: `image_focus_x`
   and `image_focus_y` (0–100, default 50) and `image_zoom` (1–3, default 1). The file is never
   altered, so an instructor can reframe at any time.
2. **One tile shape: 3:2** on every screen, so the editor preview is exactly what students see.
3. **One renderer.** A shared `CourseImageFrame` component draws both the tile and the editor
   preview. It uses `object-fit: cover`, positions the image at the focus point and scales it
   around that point, so the box is always covered and never shows a border.
4. **In-house editor** on the portal course form: drag to move, a slider or the scroll wheel to
   zoom, and Reset. No new dependency.
5. `save_course` writes the framing only when the request carries it, and clamps it to range.
   Choosing a new image resets the framing to the default.

## Consequences

Desk and anything else that reads `course_image` show the uncropped original. Sections copied
from one another carry their framing with them.
