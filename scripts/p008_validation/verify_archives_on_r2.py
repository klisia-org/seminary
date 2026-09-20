"""p008 F17 against a real object store. Run with `bench --site <site> console`:

    import runpy; runpy.run_path("/path/to/bench/apps/seminary/scripts/p008_validation/verify_archives_on_r2.py")

`bench console` runs with the *sites* directory as cwd, so the path must be
absolute (or `../apps/...`) -- a bare `apps/...` resolves under `sites/`.

Everything the local suites cover runs against a *mock-ish* backend or a local
disk; this is the only check that the offloaded path works against the real
thing -- multipart put, presigned get, and `materialize` pulling an object back
down to validate a SCORM package.

Read-mostly: it creates one Course Folder, two small Files and one archive, then
rolls the database back. The **objects it PUT to the store are not rolled back**
-- they are content-addressed and tiny, and `cleanup_stale_archives` would take
the rows anyway, but say so rather than pretend otherwise.
"""

import io
import zipfile

import frappe

from seminary.api import folder_archive as fa
from seminary.api import folder_upload as fu
from seminary.storage import get_storage_backend
from seminary.storage.backend import key_from_url
from seminary.storage.files import materialize

ROWS = []


def row(label, ok, detail=""):
    ROWS.append((label, "ok" if ok else "BROKEN", detail))


def main():
    backend = get_storage_backend()
    configured = backend.is_configured()
    row("object storage is configured", configured, type(backend).__name__)
    if not configured:
        print("\nThis site has no object store; run this on the site that does.\n")
        return

    cf = frappe.get_doc(
        {"doctype": "Course Folder", "scope": "School", "foldername": "p008-f17-probe"}
    )
    cf.flags.ignore_permissions = True
    cf.insert()
    root = cf.file_reference

    for name, blob in (
        ("f17-probe-a.txt", b"alpha"),
        ("f17-probe-b.bin", bytes(range(256)) * 8),
    ):
        doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": name,
                "content": blob,
                "folder": root,
                "is_private": 1,
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert()

    # --- the build actually reaches the store -------------------------------
    built = fa.build_archive(root, cf.name)
    row("an archive builds", bool(built))
    if not built:
        return

    art = frappe.db.get_value(
        "File",
        built,
        ["file_url", "file_size", "is_private", "attached_to_name"],
        as_dict=True,
    )
    key = key_from_url(art.file_url)
    row("the artifact is offloaded", bool(key), art.file_url[:70])
    row("the artifact is private", art.is_private == 1)
    row(
        "it is attached to the Course Folder",
        art.attached_to_name == cf.name,
        "this is what makes user_may_read the only read rule",
    )

    stat = backend.stat(key) if key else None
    row(
        "the object exists in the store",
        bool(stat),
        f"stat size={stat.get('size') if stat else '-'} vs row {art.file_size}",
    )
    if stat:
        row("stored size matches the row", int(stat["size"]) == int(art.file_size or 0))

    # --- and comes back intact ----------------------------------------------
    try:
        with materialize(built) as path:
            with zipfile.ZipFile(path) as zf:
                members = [i.filename for i in zf.infolist() if not i.is_dir()]
                bad = zf.testzip()
        row("it reads back as a valid zip", bad is None, f"{len(members)} members")
        row("both files travelled", len(members) == 2, str(members))
    except Exception as exc:
        row("it reads back as a valid zip", False, f"{type(exc).__name__}: {exc}")

    # --- the endpoint hands back a URL, never a build ------------------------
    res = fu.download_folder(folder_id=root)
    row(
        "the endpoint reports ready",
        res.get("status") == "ready",
        str(res.get("status")),
    )
    row("and hands back the artifact URL", res.get("url") == art.file_url)

    # --- a presigned GET is actually signable --------------------------------
    try:
        url = backend.presigned_get(
            key,
            ttl=60,
            file_name="probe.zip",
            content_type="application/zip",
            as_attachment=True,
        )
        row(
            "a presigned GET is issued",
            url.startswith("http"),
            url.split("?")[0][:60] + "?…",
        )
    except Exception as exc:
        row("a presigned GET is issued", False, f"{type(exc).__name__}: {exc}")

    # --- SCORM validation needs materialize() on a real object ---------------
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("imsmanifest.xml", "<manifest/>")
        zf.writestr("index.html", "hi")
    pkg = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": "f17-probe.zip",
            "content": buf.getvalue(),
            "is_private": 1,
        }
    )
    pkg.flags.ignore_permissions = True
    pkg.insert()
    try:
        from seminary.seminary import api as sem_api

        sem_api._check_scorm_package(pkg.name)
        row(
            "a SCORM package validates through the store",
            True,
            "materialize() pulled it back to read the central directory",
        )
    except Exception as exc:
        row(
            "a SCORM package validates through the store",
            False,
            f"{type(exc).__name__}: {exc}",
        )


try:
    main()
finally:
    frappe.db.rollback()
    width = max(len(r[0]) for r in ROWS) if ROWS else 10
    print("\n\nF17 ON REAL OBJECT STORAGE\n" + "-" * (width + 12))
    for label, verdict, detail in ROWS:
        print(f"{label.ljust(width)}  {verdict:<7} {detail}")
    broken = [r for r in ROWS if r[1] == "BROKEN"]
    print("-" * (width + 12))
    print(
        f"{len(ROWS) - len(broken)}/{len(ROWS)} ok"
        + (f"  -- {len(broken)} BROKEN" if broken else "")
    )
    print("database rolled back; any object PUT to the store remains\nEND\n")
