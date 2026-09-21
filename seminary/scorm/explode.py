# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Unpack a SCORM package from its zip into object storage (p009 §2.4).

The **only** writer of the `scorm/` prefix, and the only place in this app that
opens a package. It runs as a background job because a package is measured in
gigabytes, and it writes an *inventory* -- the map of member paths delivery is
allowed to answer for. Everything the delivery side does safely, it does because
this module validated the path before recording it.

Three properties to preserve if this is ever edited:

* **Nothing lands on local disk as a tree.** The zip is materialised to a single
  temporary file so its central directory can be read; members are streamed
  from it straight to the object store. p005 A01-6 / A02-4 / p005a A05-8 were
  all one mechanism -- extracting instructor content into a directory -- and it
  does not come back in any form.
* **Nothing is trusted from the archive.** Not the member paths, not the
  declared sizes, not the manifest's claims, not the content types.
* **A refusal leaves nothing behind.** Objects written before a failure are
  deleted, the row is marked Failed with a reason staff can read, and the
  refusal is counted.

Memory is O(chunk) throughout: each member is read twice from a local temporary
file -- once to hash and bound it, once to upload it -- rather than once into a
`bytes`. Two passes over a file already in the page cache is cheaper than
holding a 1 GiB member in a worker.
"""

from __future__ import annotations

import hashlib
import zipfile

import frappe

from seminary.scorm import archive, lessons
from seminary.scorm.archive import PackageError
from seminary.scorm.manifest import ManifestError

CHUNK = 1024 * 1024


def enqueue(chapter: str, package_name: str) -> None:
    """Queue the unpack. Called after the chapter has saved and committed."""
    frappe.enqueue(
        "seminary.scorm.explode.explode_package",
        queue="long",
        timeout=3600,
        enqueue_after_commit=True,
        job_id=f"scorm-explode::{package_name}",
        deduplicate=True,
        chapter=chapter,
        package_name=package_name,
    )


def explode_package(chapter: str, package_name: str) -> None:
    """Entry point for the job. Never raises: a refusal is a Failed row."""
    package = frappe.get_doc("SCORM Package", package_name)
    if package.status not in ("Pending", "Failed"):
        return

    package.db_set("status", "Exploding", update_modified=False)
    written: list[str] = []
    try:
        _explode(package, chapter, written)
    except (PackageError, ManifestError) as e:
        _fail(package, chapter, str(e), written)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), f"scorm: unpacking {package_name} failed"
        )
        _fail(
            package,
            chapter,
            frappe._("This SCORM package could not be unpacked."),
            written,
        )


def _fail(package, chapter, reason: str, written: list[str]) -> None:
    from seminary.seminary import security_log
    from seminary.storage.backend import get_storage_backend

    backend = get_storage_backend()
    for key in written:
        try:
            backend.delete(key)
        except Exception:
            # Best effort. A stranded object is swept later; losing the reason
            # the package was refused would be the worse outcome.
            frappe.log_error(
                f"{key}\n{frappe.get_traceback()}",
                "scorm: could not clean up after a failed unpack",
            )

    package.db_set(
        {"status": "Failed", "failure_reason": reason[:1000]}, update_modified=False
    )
    security_log.record_denial(
        "scorm_explode_refused", package=package.name, chapter=chapter, reason=reason
    )
    frappe.db.commit()


def _adopt(package, chapter: str, existing: str) -> bool:
    """Point the chapter at a package that is already unpacked, and drop ours.

    A template import and a Course Pack both share one zip across sections
    (`pin_scorm_package` leaves an already-attached File where it is), so the
    same bytes arrive repeatedly. Dedup is on the **SHA-256** computed while
    streaming, never on `File.content_hash`, which is MD5 -- see
    `SCORMPackage`'s module docstring for why that distinction is load-bearing.
    """
    frappe.db.set_value(
        "Course Schedule Chapter", chapter, "scorm_package_ref", existing
    )
    frappe.delete_doc(
        "SCORM Package", package.name, ignore_permissions=True, force=True
    )
    lessons.reconcile(frappe.get_doc("SCORM Package", existing), chapter)
    frappe.db.commit()
    return True


def _explode(package, chapter: str, written: list[str]) -> None:
    from seminary.scorm import manifest as manifest_module
    from seminary.storage.backend import get_storage_backend
    from seminary.storage.files import materialize

    backend = get_storage_backend()
    if not backend.is_configured():
        # There is no local-disk fallback, by decision (§2.1). A private on-disk
        # tree behind this same inventory would be safe, and would be the second
        # implementation nobody tests.
        raise PackageError(
            frappe._(
                "This site has no object storage, so SCORM packages cannot be played."
            )
        )

    source = frappe.get_doc("File", package.source_file)

    with materialize(source) as path:
        with open(path, "rb") as fh:
            digest = hashlib.sha256()
            for block in iter(lambda: fh.read(CHUNK), b""):
                digest.update(block)
        sha256 = digest.hexdigest()
        package.db_set("source_sha256", sha256, update_modified=False)

        already = frappe.db.get_value(
            "SCORM Package",
            {
                "source_sha256": sha256,
                "status": "Ready",
                "name": ["!=", package.name],
            },
            "name",
        )
        if already:
            _adopt(package, chapter, already)
            return

        try:
            zf = zipfile.ZipFile(path)
        except zipfile.BadZipFile as e:
            raise PackageError(
                frappe._("This file is not a SCORM package (not a zip archive).")
            ) from e

        with zf:
            # The same bounds the chapter accepted the file under, re-run against
            # the file as it is now rather than as it was at pin time.
            archive.check_bounds(zf, source.file_size or 0)

            manifest_name = archive.find_manifest(zf.namelist())
            root = archive.package_root(manifest_name)
            inventory = _upload_members(zf, package, root, backend, written)

            if manifest_name[len(root) :] not in inventory:
                raise PackageError(
                    frappe._("This SCORM package's manifest could not be read.")
                )

            parsed = manifest_module.parse(
                zf.read(manifest_name),
                inventory,
                max_scos=archive.cap(
                    "scorm_max_scos", manifest_module.DEFAULT_MAX_SCOS
                ),
            )

    _record(package, inventory, parsed)
    lessons.reconcile(package, chapter)
    frappe.db.commit()


def _upload_members(zf, package, root: str, backend, written: list[str]) -> dict:
    """Stream every member under `root` to object storage; return the inventory.

    Keys are **relative to the manifest's own directory**, so a package that was
    zipped with its containing folder addresses itself exactly as one zipped at
    the root does, and the manifest's relative hrefs resolve against the same
    space delivery serves from.
    """
    member_cap = archive.cap("scorm_max_member_bytes", archive.MAX_MEMBER_BYTES)
    proxy_cap = archive.cap(
        "scorm_proxy_member_max_bytes", archive.MAX_PROXIED_MEMBER_BYTES
    )

    inventory: dict[str, dict] = {}
    seen: dict[str, str] = {}

    for info in zf.infolist():
        raw = info.filename.replace("\\", "/")
        if info.is_dir():
            continue
        if archive.is_symlink(info):
            raise PackageError(frappe._("This SCORM package contains a symbolic link."))
        if root and not raw.startswith(root):
            # Outside the package root: not part of the package, so not served.
            continue

        relative = raw[len(root) :]
        if archive.is_junk(relative):
            continue

        path = archive.normalise_member_path(relative)

        for key in archive.collision_keys(path):
            if key in seen and seen[key] != path:
                raise PackageError(
                    frappe._(
                        "This SCORM package contains two files whose names differ only "
                        "in case or accents: {0} and {1}."
                    ).format(seen[key], path)
                )
            seen[key] = path

        content_type = archive.content_type_for(path)
        if archive.is_proxied(path) and info.file_size > proxy_cap:
            # Refused here rather than at serve time: this member has to be
            # streamed through a worker (§2.6), and the instructor is the one who
            # can do something about it.
            raise PackageError(
                frappe._(
                    "This SCORM package contains a text file that is too large: {0}."
                ).format(path)
            )

        size, sha256 = _measure(zf, info, member_cap)

        key = package.key_for(path)
        with zf.open(info) as member:
            backend.put_fileobj(key, member, content_type=content_type)
        written.append(key)

        inventory[path] = {
            "size": size,
            "sha256": sha256,
            "content_type": content_type,
        }

    if not inventory:
        raise PackageError(frappe._("This SCORM package is empty."))
    return inventory


def _measure(zf, info, member_cap: int) -> tuple[int, str]:
    """Hash a member and bound it, without trusting the size it declares.

    `zf.read` stops at the declared size and then fails its CRC (p008 F17), but
    a streaming copy has no such guarantee for free -- so the counter is here,
    and it aborts rather than finishing an upload it should not have started.
    """
    digest = hashlib.sha256()
    size = 0
    with zf.open(info) as member:
        while True:
            block = member.read(CHUNK)
            if not block:
                break
            size += len(block)
            if size > member_cap or size > info.file_size:
                raise PackageError(
                    frappe._("This SCORM package contains a file that is too large.")
                )
            digest.update(block)
    return size, digest.hexdigest()


def _record(package, inventory: dict, parsed) -> None:
    package.set_inventory(inventory)
    package.scorm_version = parsed.version
    package.default_organization = parsed.default_organization
    package.items = []
    for sco in parsed.scos:
        package.append(
            "items",
            {
                "sco_identifier": sco.identifier,
                "title": sco.title,
                "href": sco.href + sco.suffix,
            },
        )
    package.status = "Ready"
    package.failure_reason = None
    package.save(ignore_permissions=True)
    frappe.db.commit()
