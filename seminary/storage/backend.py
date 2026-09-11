# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The storage-backend interface, its local-disk default, and the URL scheme.

Mirrors `seminary.seminary.financial.backend`: an ABC, a default implementation
that is *not* a degraded mode, and a resolver. A storage app (closed-source)
registers a real object-store backend under the `seminary_storage_backend` hook;
with none installed, `LocalDiskBackend` reports itself unconfigured, nothing ever
offloads, and Frappe's own disk pipeline runs untouched.

## The URL scheme, and why it looks like this

An offloaded file's `file_url` is:

    /api/method/seminary.storage.api.download_file?key=media/ab/abc123.../lecture.mp4

Three properties of that string are load-bearing, all verified against Frappe
16.22.0 (`frappe/core/doctype/file/file.py`):

1. **`/api/method/` is in `URL_PREFIXES` (file.py:44)**, so `is_remote_file`
   (86-90) is True and `save_file` (752), `write_file` (729),
   `validate_file_path` (290), `validate_file_url` (301) and
   `handle_is_private_changed` (312) all early-return. The disk pipeline no-ops
   without us patching it.
2. **The path contains no `/files/` substring** — hence the `media/` prefix.
   `get_full_path` (698) and `validate_remote_file` (419) both branch on
   `"/files/" in file_path`, and we must not trip either.
3. **The key, not a docname.** The legacy `save_file` form
   (`frappe/utils/file_manager.py:151-190`) needs the URL *before* the File row
   exists, and `find_file_by_url` matches the exact string — so two File rows over
   one blob (`create_attachment_copy`, `comms.py`) must produce an *identical*
   URL. A content-hash key gives that for free.

The key carries **no filename**, which is deliberate — see `object_key`. It is
therefore hex-only, so the URL needs no percent-encoding: the desk attachment
sidebar runs `encodeURI(file_url)`, which would double-encode any `%` we
introduced. The human-readable name lives in `File.file_name`, and the download
endpoint puts it back on the way out via `Content-Disposition`.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager

import frappe

#: Whitelisted endpoint that serves offloaded files. Permission-checked, then
#: redirects to a short-lived presigned URL — so offloading does not widen access.
DOWNLOAD_ENDPOINT = "seminary.storage.api.download_file"

URL_PREFIX = f"/api/method/{DOWNLOAD_ENDPOINT}?key="

#: Top-level key prefix. Deliberately not "files" — see the module docstring.
KEY_PREFIX = "media"


def object_key(content_hash: str) -> str:
    """Build the object key for a blob. A pure function of its content.

    Keyed by content hash so that re-uploading identical bytes PUTs to the same
    key and is therefore idempotent. This matters because Frappe's own dedup
    (file.py:784-800) gates on `exists_on_disk()`, which is always False for a
    remote URL — so upstream will happily "re-write" a blob we already hold.

    **The filename is deliberately not part of the key**, and leaving it out is
    load-bearing rather than cosmetic. `_delete_file_on_disk` (file.py:603-618)
    decides whether a blob is still needed by counting File rows that share a
    `content_hash` — and nothing else; the `is_private` clause is commented out
    upstream. So if the key were a function of anything *besides* the content
    hash, two rows holding identical bytes under different names would map to two
    distinct objects while still refcounting as one: deleting either row would
    find the other, conclude the blob is shared, and delete neither object. Ever.
    That is exactly what happens in practice, because `generate_file_name`
    (file.py:803) suffixes every upload with `content_hash[-6:]`, so
    `lecture.mp4` and `lecture-copy.mp4` reach us with different names and the
    same hash.

    Dropping the name also stops private filenames leaking into a `file_url` that
    gets embedded in stored HTML. The real name is preserved on `File.file_name`
    and reattached by the download endpoint as `Content-Disposition`.

    The two-character fan-out keeps any single key prefix from becoming a hot
    partition in the object store.
    """
    return f"{KEY_PREFIX}/{content_hash[:2]}/{content_hash}"


def url_for_key(key: str) -> str:
    return f"{URL_PREFIX}{key}"


def is_offloaded(file_url: str | None) -> bool:
    return bool(file_url) and file_url.startswith(URL_PREFIX)


#: Matches any file URL that may be embedded in stored content — on-disk and
#: offloaded alike. Use this in place of a bare `/private/files/` scan, or
#: offloaded media becomes invisible to whatever is doing the scanning.
#: (`course_pack/editorjs.py` keeps its own copy to stay frappe-free.)
FILE_URL_RE = re.compile(
    r"/(?:private/)?files/[^\"'<>)\s]+"
    r"|" + re.escape(URL_PREFIX) + r"[A-Za-z0-9/._-]+"
)


def normalize_file_url(url: str) -> str:
    """Reduce a URL to the exact string stored in `File.file_url`.

    Frappe appends `?fid=<name>` to private URLs (`File.unique_url`), so callers
    that look a File up by URL strip the query string. That is wrong for an
    offloaded URL, whose `?key=` *is* the address — stripping it yields a bare
    endpoint path that matches nothing, and the file is silently skipped.
    """
    if is_offloaded(url):
        return url
    return (url or "").split("?")[0]


def key_from_url(file_url: str | None) -> str | None:
    """Extract the object key from a `file_url`, or None if it is not offloaded."""
    if not is_offloaded(file_url):
        return None
    key = file_url[len(URL_PREFIX) :]
    # Defence in depth: the key is built by `object_key` and never by a client,
    # but this value reaches the object store, so refuse anything path-shaped.
    if (
        not key
        or key.startswith("/")
        or ".." in key
        or not key.startswith(f"{KEY_PREFIX}/")
    ):
        return None
    return key


class StorageBackend(ABC):
    """Contract seminary depends on for offloaded media.

    Implemented by a storage app; falls back to `LocalDiskBackend` when none is
    installed. Deliberately expressed in plain keys and bytes — no object-store
    SDK types leak across the seam — so a different provider is one class.
    """

    @abstractmethod
    def is_configured(self) -> bool:
        """True when this site has a usable object store.

        This is the single kill switch: `routing.should_offload` returns False
        whenever it is False, so nothing is ever written to, or read from, a
        backend that cannot serve it.
        """

    @abstractmethod
    def put(self, key: str, content: bytes, content_type: str | None = None) -> None:
        """Store `content` at `key`. Must be idempotent — see `object_key`."""

    @abstractmethod
    def put_fileobj(self, key: str, fileobj, content_type: str | None = None) -> None:
        """Store the contents of an open binary `fileobj` at `key`.

        For payloads that must never be held in memory as a single `bytes` — a
        Course Pack of lecture video being the case that forced this. An
        implementation is expected to upload in parts.
        """

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Return the whole object. Prefer `stream` for anything large."""

    @abstractmethod
    def stream(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        """Yield the object in chunks, so callers need not hold it in memory."""

    @abstractmethod
    def materialize(self, key: str, suffix: str = ""):
        """Context manager yielding a real filesystem path for `key`.

        For the handful of consumers that need a path rather than bytes —
        `zipfile.extractall` on a SCORM package being the live one. The file is
        removed on exit.

        `suffix` is the original file extension, supplied by the caller because
        the key does not carry one (see `object_key`). Some readers sniff it.
        """

    @abstractmethod
    def stat(self, key: str) -> dict | None:
        """Return `{"size": int, "etag": str}` for `key`, or None if absent.

        The authoritative size of an object the server did not write itself —
        which is the only size a direct browser upload may be trusted on.
        """

    @abstractmethod
    def copy(self, source_key: str, dest_key: str) -> None:
        """Copy an object within the store, without moving bytes through here.

        Used to promote a freshly uploaded object from its temporary key to its
        content-addressed one once its hash is known.
        """

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove the object. Only ever called once no File row references it."""

    @abstractmethod
    def list_keys(self, prefix: str) -> list[dict]:
        """Return `[{"key", "size", "last_modified"}]` under `prefix`.

        For sweeping abandoned uploads; not a general-purpose listing.
        """

    @abstractmethod
    def presigned_get(
        self,
        key: str,
        ttl: int | None = None,
        file_name: str | None = None,
        content_type: str | None = None,
        as_attachment: bool = False,
    ) -> str:
        """Return a short-lived, directly-fetchable URL for `key`.

        This is what takes egress off the origin: the download endpoint checks
        permission and then redirects here, so bytes travel object-store→browser
        and never through a worker.
        """

    @abstractmethod
    def presigned_put(
        self, key: str, ttl: int | None = None, content_type: str | None = None
    ) -> str:
        """Return a short-lived URL the browser may PUT a single object to.

        The counterpart of `presigned_get`, and what keeps a large upload out of
        worker memory entirely. `key` must always be chosen by the server: a URL
        that let a client name its own key would be an arbitrary-write primitive
        over the whole bucket.
        """


class LocalDiskBackend(StorageBackend):
    """No object store installed: nothing offloads, everything stays on disk.

    This is the default and a fully supported deployment, not a degraded mode.
    Because `is_configured()` is False, `should_offload` always returns False, no
    `file_url` is ever given the offloaded prefix, and the remaining methods are
    unreachable by construction — reaching one is a bug in the caller, not a
    site-configuration state, so they raise rather than silently no-op.
    """

    def is_configured(self) -> bool:
        return False

    def _unreachable(self, op: str):
        raise NotImplementedError(
            f"seminary.storage: {op}() called with no object-storage backend configured. "
            "Offloaded files cannot exist on this site, so this indicates a caller "
            "bypassed routing.should_offload() or is_offloaded()."
        )

    def put(self, key: str, content: bytes, content_type: str | None = None) -> None:
        self._unreachable("put")

    def put_fileobj(self, key: str, fileobj, content_type: str | None = None) -> None:
        self._unreachable("put_fileobj")

    def read(self, key: str) -> bytes:
        self._unreachable("read")

    def stream(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        self._unreachable("stream")

    @contextmanager
    def materialize(self, key: str, suffix: str = ""):
        self._unreachable("materialize")
        yield  # pragma: no cover - unreachable, keeps this a generator

    def stat(self, key: str) -> dict | None:
        self._unreachable("stat")

    def copy(self, source_key: str, dest_key: str) -> None:
        self._unreachable("copy")

    def delete(self, key: str) -> None:
        self._unreachable("delete")

    def list_keys(self, prefix: str) -> list[dict]:
        self._unreachable("list_keys")

    def presigned_get(
        self,
        key: str,
        ttl: int | None = None,
        file_name: str | None = None,
        content_type: str | None = None,
        as_attachment: bool = False,
    ) -> str:
        self._unreachable("presigned_get")

    def presigned_put(
        self, key: str, ttl: int | None = None, content_type: str | None = None
    ) -> str:
        self._unreachable("presigned_put")


def get_storage_backend() -> StorageBackend:
    """Resolve the registered storage backend, or the local-disk fallback.

    The last registration wins (standard Frappe hook-override semantics), so an
    app installed later can supersede an earlier one.
    """
    paths = frappe.get_hooks("seminary_storage_backend")
    if not paths:
        return LocalDiskBackend()
    return frappe.get_attr(paths[-1])()
