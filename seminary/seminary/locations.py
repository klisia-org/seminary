"""One-directional mirror of the seminary facilities hierarchy
(Campus → Building → Room) into the ERPNext ``Location`` NestedSet tree, so
Assets (whose ``location`` is mandatory) can be placed in a room. See ADR 039.

The seminary doctypes are the source of truth; Locations are *derived* and never
edited back — the same pattern Chapel uses to upsert a Public Event (ADR 029).
Each seminary doc stores its mirror in a ``location`` Link; that link (not the
name) is the identity, so the upsert is idempotent. All of this is gated by the
``sync_rooms_to_asset_locations`` Seminary Setting (default on) and degrades to a
no-op when off.

Tree shape:
    root (is_group)            ← Seminary Settings.root_asset_location or "Seminary Locations"
      └ Campus (is_group)
          └ Building (is_group)
              └ Room (is_container)   ← assets sit here
Rooms with no building hang directly off the root.
"""

import frappe

_ROOT_NAME = "Seminary Locations"


def _sync_enabled():
    try:
        return bool(
            frappe.db.get_single_value(
                "Seminary Settings", "sync_rooms_to_asset_locations"
            )
        )
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public entry points (called from Campus/Building/Room controllers + backfill)
# ---------------------------------------------------------------------------


def ensure_root_location():
    """Return the root Location name, creating the default root if needed."""
    configured = frappe.db.get_single_value("Seminary Settings", "root_asset_location")
    if configured and frappe.db.exists("Location", configured):
        return configured
    if not frappe.db.exists("Location", _ROOT_NAME):
        frappe.get_doc(
            {"doctype": "Location", "location_name": _ROOT_NAME, "is_group": 1}
        ).insert(ignore_permissions=True)
    return _ROOT_NAME


def ensure_campus_location(campus):
    """Upsert the Location mirroring a Campus (a group under the root)."""
    if not _sync_enabled():
        return None
    root = ensure_root_location()
    return _upsert(campus, campus.campus_name, root, is_group=1, is_container=0)


def ensure_building_location(building):
    """Upsert the Location mirroring a Building (a group under its campus)."""
    if not _sync_enabled():
        return None
    campus = frappe.get_doc("Campus", building.campus)
    parent = ensure_campus_location(campus) or ensure_root_location()
    desired = f"{building.campus} - {building.building_name}"
    return _upsert(building, desired, parent, is_group=1, is_container=0)


def ensure_room_location(room):
    """Upsert the Location mirroring a Room (a container under its building, or
    the root when the room has no building)."""
    if not _sync_enabled():
        return None
    if room.building:
        building = frappe.get_doc("Building", room.building)
        parent = ensure_building_location(building) or ensure_root_location()
        desired = f"{parent} - {room.room_name}"
    else:
        parent = ensure_root_location()
        desired = room.room_name
    return _upsert(room, desired, parent, is_group=0, is_container=1)


def detach_location(doc):
    """On trash of a Campus/Building/Room, remove its mirror Location — but only
    when it is safe (no child Locations, no Assets placed there). Never orphan
    an asset; leave the Location in place otherwise."""
    loc = doc.get("location")
    if not loc or not frappe.db.exists("Location", loc):
        return
    if frappe.db.exists("Location", {"parent_location": loc}):
        return
    if frappe.db.exists("DocType", "Asset") and frappe.db.exists(
        "Asset", {"location": loc}
    ):
        return
    # force=True bypasses the "linked by" check — the doc being trashed still
    # links to this Location at on_trash time. Safe here: we've already
    # confirmed no child Locations and no Assets depend on it.
    try:
        frappe.delete_doc("Location", loc, force=True, ignore_permissions=True)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), f"locations.detach_location failed: {loc}"
        )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _upsert(doc, desired_name, parent, is_group, is_container):
    """Create or update the Location mirroring ``doc`` and store its name back on
    ``doc.location`` (via db_set, so the controller's on_update doesn't recurse).
    Returns the Location name."""
    existing = doc.get("location")
    if existing and frappe.db.exists("Location", existing):
        loc = frappe.get_doc("Location", existing)
        changed = False
        if loc.parent_location != parent:
            loc.parent_location = parent
            changed = True
        if int(loc.is_group or 0) != int(is_group):
            loc.is_group = int(is_group)
            changed = True
        if int(loc.is_container or 0) != int(is_container):
            loc.is_container = int(is_container)
            changed = True
        if changed:
            loc.flags.ignore_permissions = True
            loc.save(ignore_permissions=True)
        # Best-effort rename when the source's display name changed. Frappe
        # updates Asset link references on rename; failures are non-fatal.
        if loc.name != desired_name:
            new_name = _unique_location_name(desired_name, exclude=loc.name)
            if new_name != loc.name:
                try:
                    frappe.rename_doc(
                        "Location",
                        loc.name,
                        new_name,
                        force=True,
                        ignore_permissions=True,
                    )
                    doc.db_set("location", new_name, update_modified=False)
                except Exception:
                    frappe.log_error(
                        frappe.get_traceback(),
                        f"locations._upsert rename failed: {loc.name} -> {new_name}",
                    )
        return doc.get("location")

    name = _unique_location_name(desired_name)
    loc = frappe.get_doc(
        {
            "doctype": "Location",
            "location_name": name,
            "parent_location": parent,
            "is_group": int(is_group),
            "is_container": int(is_container),
        }
    )
    loc.insert(ignore_permissions=True)
    doc.db_set("location", loc.name, update_modified=False)
    return loc.name


def _unique_location_name(base, exclude=None):
    """A Location name not already taken (Location.location_name is unique and is
    the docname). ``exclude`` lets an existing Location keep its own name."""
    name = base
    i = 2
    while frappe.db.exists("Location", name) and name != exclude:
        name = f"{base} ({i})"
        i += 1
    return name


def backfill():
    """Create/refresh Locations for every existing Campus, Building, and Room.
    Idempotent; gated by the sync setting. Used by the install/migrate backfill
    patch and by the Seminary Settings on_update when the toggle is switched on."""
    if not _sync_enabled():
        return
    for name in frappe.get_all("Campus", pluck="name"):
        ensure_campus_location(frappe.get_doc("Campus", name))
    for name in frappe.get_all("Building", pluck="name"):
        ensure_building_location(frappe.get_doc("Building", name))
    for name in frappe.get_all("Room", pluck="name"):
        ensure_room_location(frappe.get_doc("Room", name))
    frappe.db.commit()
