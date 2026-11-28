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

The storage half is deliberately narrow: one method, which delegates to
`super()` for every file that is not offloaded. The three privacy methods below
it belong to `seminary.seminary.file_policy` (p007 §8.2) and live here only
because a doctype has one controller. On a site with no storage backend
nothing is ever offloaded, so this class is a strict no-op there.
"""

from __future__ import annotations

import frappe
from frappe.core.doctype.file.file import FILE_ENCODING_OPTIONS, File

from seminary.storage.backend import get_storage_backend, key_from_url


class SeminaryFile(File):
	# --- privacy policy (privatedocs/p007 §8.2) ------------------------------
	# Both run *ahead* of upstream on purpose: `before_insert` writes the bytes
	# to the public or private directory and `validate` moves them, so the
	# decision has to be made before either happens. A `doc_events` hook would
	# run after the controller and find the file already in place.

	def before_insert(self):
		from seminary.seminary import file_policy

		file_policy.apply_on_insert(self)
		super().before_insert()

	def validate(self):
		from seminary.seminary import file_policy

		file_policy.check_on_save(self)
		super().validate()

	def _delete_file_on_disk(self):
		"""An offloaded file is shared by URL, not by hash.

		Upstream decides by `content_hash`, which it clears on every remote
		file (file.py: "a remote file has no local blob to hash"), so for a
		browser's direct upload, or a twin file_policy attaches elsewhere, it
		always sees the blob as shared and never deletes it. For an offloaded
		file the URL names the object, so other rows over that URL are what
		keep it (privatedocs p029: retention must remove a video's object).
		"""
		if not key_from_url(self.file_url):
			return super()._delete_file_on_disk()
		shared = frappe.get_all(
			"File",
			filters={"file_url": self.file_url, "name": ["!=", self.name]},
			limit=1,
		) or (
			self.content_hash
			and frappe.get_all(
				"File",
				filters={"content_hash": self.content_hash, "name": ["!=", self.name]},
				limit=1,
			)
		)
		self.delete_file_data_content(only_thumbnail=bool(shared))

	def is_downloadable(self):
		from seminary.seminary import file_policy

		return bool(super().is_downloadable()) or file_policy.intranet_readable(self)

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
