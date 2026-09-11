# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Backend-agnostic helpers for consumers that need more than `get_content()`.

Reading a whole file needs nothing from this module: the `SeminaryFile`
controller override makes `File.get_content()` transparent for offloaded files,
so existing callers keep working untouched.

These helpers exist for the two cases `get_content()` cannot serve:

- **`materialize`** — a caller that needs a real filesystem *path*, not bytes.
  `zipfile.ZipFile(path).extractall()` on a SCORM package is the live example;
  an offloaded file has no path, so one is produced temporarily.
- **`open_stream`** — a caller copying a large file somewhere else, which should
  not hold hundreds of megabytes of lecture video in worker memory just to hand
  it onward.

Both take either a `File` doc or a docname, and both work identically whether the
file is on disk or offloaded, so callers never branch on storage location.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

import frappe

from seminary.storage.backend import get_storage_backend, key_from_url

CHUNK_SIZE = 1024 * 1024


def _as_doc(file_doc_or_name):
    if isinstance(file_doc_or_name, str):
        return frappe.get_doc("File", file_doc_or_name)
    return file_doc_or_name


@contextmanager
def materialize(file_doc_or_name):
    """Yield a filesystem path for a File, wherever its bytes actually live.

    A local file yields its real path and is left alone. An offloaded file is
    downloaded to a temporary file, whose path is yielded and which is removed on
    exit — so callers must not retain the path beyond the `with` block.
    """
    doc = _as_doc(file_doc_or_name)
    key = key_from_url(doc.file_url)

    if not key:
        yield doc.get_full_path()
        return

    # The key carries no extension (see backend.object_key), so pass the real one
    # through — readers that sniff by suffix would otherwise misjudge the file.
    suffix = os.path.splitext(doc.file_name or "")[1]
    with get_storage_backend().materialize(key, suffix=suffix) as path:
        yield path


@contextmanager
def open_stream(file_doc_or_name) -> Iterator[Iterator[bytes]]:
    """Yield an iterator of byte chunks for a File, wherever its bytes live."""
    doc = _as_doc(file_doc_or_name)
    key = key_from_url(doc.file_url)

    if key:
        yield get_storage_backend().stream(key, chunk_size=CHUNK_SIZE)
        return

    with open(doc.get_full_path(), "rb") as handle:
        yield iter(lambda: handle.read(CHUNK_SIZE), b"")


def copy_into_zip(archive, file_doc_or_name, arcname: str) -> None:
    """Write a File into an open `zipfile.ZipFile` without buffering it whole.

    `writestr` would require the entire file in memory first, which for a folder
    of lecture video is exactly the worker-memory profile object storage is meant
    to remove.
    """
    with open_stream(file_doc_or_name) as chunks, archive.open(arcname, "w") as target:
        for chunk in chunks:
            target.write(chunk)


@contextmanager
def temp_download(key: str, suffix: str = ""):
    """Download an object to a named temporary file and yield its path.

    Shared implementation for object-storage backends' `materialize()`; kept here
    so each backend does not reinvent the streaming-to-tempfile dance.
    """
    backend = get_storage_backend()
    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        with handle:
            for chunk in backend.stream(key, chunk_size=CHUNK_SIZE):
                handle.write(chunk)
        yield handle.name
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


__all__ = ["copy_into_zip", "materialize", "open_stream", "temp_download"]
