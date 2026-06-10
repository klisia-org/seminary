# 039 — Facilities hierarchy and one-directional Location mirror

**Date:** 2026-06-10
**Status:** Accepted

## Context

Rooms were flat — no building or campus — and disconnected from ERPNext's Assets
module. Two future needs are painful to retrofit once data exists:

1. **Multi-site seminaries** need a real Campus → Building → Room hierarchy for
   scheduling, filtering ("rooms in Building X"), and per-campus attributes.
2. **Asset tracking** — ERPNext's `Asset.location` is **mandatory** and links to
   `Location`, a NestedSet tree. To place an asset (a projector, a piano — things that
   are also Room Features) in a room, that room must exist as a `Location`. Without a
   bridge, a seminary maintains a parallel Location tree by hand.

The field is trivial to add later; the *data* (hundreds of rooms with no Locations once
assets already exist) is what's painful. So the hierarchy and the Location bridge are
established now.

## Decision

Introduce **Campus** and **Building** as seminary-owned doctypes, add `building`
(+ derived `campus`) and `location` to **Room**, and **mirror the hierarchy
one-directionally into the ERPNext `Location` tree**.

### Seminary hierarchy is the source of truth; Location is derived

The seminary doctypes are authoritative. Locations are created/updated *from* them and
never edited back — the same pattern Chapel uses to upsert a Public Event (ADR 029).
This avoids the two-tree synchronization trap. Each seminary doc stores its mirror in a
read-only `location` Link, and **that link (not the Location name) is the identity**, so
the upsert (`seminary/seminary/locations.py`) is idempotent.

Tree shape:

```
root (is_group)            ← Seminary Settings.root_asset_location, or auto "Seminary Locations"
  └ Campus   (is_group)
      └ Building (is_group)
          └ Room   (is_container)   ← assets sit here
```

Rooms with no building hang directly off the root, so a single-site seminary can ignore
Campus/Building entirely.

### Opt-out, not opt-in

A `sync_rooms_to_asset_locations` Seminary Setting (**default on**) gates the whole
mirror. A seminary that doesn't track assets turns it off and zero Locations are created.
`root_asset_location` lets asset-using seminaries root the subtree under their existing
Location instead of the auto root. Switching the toggle on enqueues a backfill; a
migrate-time patch (`backfill_facility_locations`) covers existing data.

### Engine mechanics

- **Recursive parent-ensure** — saving a Room ensures its building → campus → root
  Locations exist first (a Location's parent must exist before insert; `lft/rgt` are
  NestedSet-managed and never set by hand).
- **Idempotent upsert** keyed on the stored link; `db_set` writes the link back so the
  controller's `on_update` doesn't recurse.
- **Naming** composes readable, unique names (`"Campus - Building"`,
  `"Campus - Building - Room"`); collisions get a numeric suffix. Identity is the link,
  so names only matter at create.
- **Rename** is best-effort: when a source's display name changes, the Location is
  renamed (Frappe updates Asset link references); failures are logged, non-fatal.
- **Trash safety**: a mirror Location is deleted only when it has no child Locations and
  no Asset references it; otherwise it's left in place. Never orphan an asset.

### Timezone deferred

Campus carries an **informational** `timezone` field, but it is *not* wired into
attendance/chapel check-in windows — those remain on site time (tz-naive
`now_datetime()`), as ADR 036 documents. Per-campus timezone enforcement is a separate
future decision; the field is present now only so the data model is ready.

## Consequences

- New `Campus`/`Building` doctypes (auto-synced, no fixtures); Room gains
  `building`/`campus`/`location`; Seminary Settings gains the toggle + root link.
- Asset-tracking seminaries get a room-level Location for free; the Room *Feature* vs.
  *Asset* reconciliation report becomes possible later.
- Course Schedule is **not** wired to the hierarchy in this build — filtering the
  room picker by building/campus is a clean follow-on.
- The hierarchy is fully optional: single-site and non-asset seminaries see no change.
