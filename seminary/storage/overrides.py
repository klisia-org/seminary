# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""`File` controller override supplying the read half of the storage seam.

Frappe gives us hooks for writing and deleting a file, but **none for reading
one**: `File.get_content` (file.py:658-690) resolves a path via `get_full_path`
and calls `open()` on it. For an offloaded file that path is the `/api/method/…`
URL itself, so the read fails with `FileNotFoundError`.

Every consumer of file bytes therefore has to go through here — course pack
export, the Course Folder zip download, plagiarism text extraction, outbound
email attachments, and anything in Frappe itself that reads a File. Overriding
the controller covers all of them at once, including the frappe-internal readers
we do not own and could not otherwise reach.

The override is deliberately narrow: exactly one method, and it delegates to
`super()` for every file that is not offloaded. On a site with no storage backend
nothing is ever offloaded, so this class is a strict no-op there.
"""

from __future__ import annotations

from frappe.core.doctype.file.file import FILE_ENCODING_OPTIONS, File

from seminary.storage.backend import get_storage_backend, key_from_url


class SeminaryFile(File):
    def get_content(self, encodings=None) -> bytes | str:
        """Return file bytes, fetching from object storage when offloaded.

        Mirrors upstream's contract exactly, including its slightly surprising
        decoding behaviour: with `encodings=None` it *tries* to decode the bytes
        to `str` and silently leaves them as `bytes` if every candidate encoding
        fails. Media therefore comes back as bytes and text as str, and callers
        that want raw bytes unconditionally pass `encodings=[]`.
        """
        key = key_from_url(self.file_url)

        # Not offloaded, a folder, or content already in hand — upstream's job.
        if not key or self.is_folder or self.get("content"):
            return super().get_content(encodings=encodings)

        self._content = get_storage_backend().read(key)

        if encodings is None:
            encodings = FILE_ENCODING_OPTIONS

        for encoding in encodings:
            try:
                self._content = self._content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        return self._content
