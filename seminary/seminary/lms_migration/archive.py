"""A course export from another LMS, read as untrusted input (decisions/108 §6).

A Common Cartridge is a zip. A Moodle backup is a gzipped tar (older releases
wrote a zip). Both are checked against entry, size and per-member limits from
the archive's own directory before a member is read; tar members other than
regular files are ignored, and no path is ever written to disk."""

import io
import posixpath
import tarfile
import zipfile

import frappe
from defusedxml import DefusedXmlException, ElementTree
from frappe import _

# Each can be raised in site_config.json.
MAX_BYTES = 1024**3  # lms_migration_max_bytes: the upload itself
MAX_UNCOMPRESSED_BYTES = 3 * 1024**3  # lms_migration_max_uncompressed_bytes
MAX_ENTRIES = 50000  # lms_migration_max_entries
MAX_MEMBER_BYTES = 1024**3  # lms_migration_max_member_bytes
MAX_XML_BYTES = 64 * 1024**2  # lms_migration_max_xml_bytes: one XML file


def limit(key, default):
	return int(frappe.conf.get(key) or default)


def _clean(name):
	name = posixpath.normpath((name or "").replace("\\", "/")).lstrip("/")
	if name in ("", ".") or name.startswith("..") or name.startswith("__MACOSX/"):
		return None
	return name


class Archive:
	def __init__(self, content):
		if len(content) > limit("lms_migration_max_bytes", MAX_BYTES):
			frappe.throw(_("The file is too large to import."))
		self._zip = None
		self._files = {}
		buf = io.BytesIO(content)
		if zipfile.is_zipfile(buf):
			self._open_zip(buf)
		else:
			self._open_tar(content)

	def _check(self, sizes):
		if len(sizes) > limit("lms_migration_max_entries", MAX_ENTRIES):
			frappe.throw(_("The package has too many files to import."))
		if sum(sizes) > limit("lms_migration_max_uncompressed_bytes", MAX_UNCOMPRESSED_BYTES):
			frappe.throw(_("The package is too large to import once unpacked."))
		if any(s > limit("lms_migration_max_member_bytes", MAX_MEMBER_BYTES) for s in sizes):
			frappe.throw(_("The package contains a file that is too large."))

	def _open_zip(self, buf):
		try:
			zf = zipfile.ZipFile(buf)
		except zipfile.BadZipFile:
			frappe.throw(_("The file is not a course export."))
		infos = [i for i in zf.infolist() if not i.is_dir()]
		self._check([i.file_size for i in infos])
		self._zip = zf
		self._names = {}
		for info in infos:
			name = _clean(info.filename)
			if name:
				self._names[name] = info

	def _open_tar(self, content):
		try:
			tf = tarfile.open(fileobj=io.BytesIO(content), mode="r:*")
		except tarfile.TarError, EOFError, OSError:
			frappe.throw(_("The file is not a course export."))
		with tf:
			members = [m for m in tf.getmembers() if m.isreg()]
			self._check([m.size for m in members])
			for m in members:
				name = _clean(m.name)
				if not name:
					continue
				f = tf.extractfile(m)
				if f is not None:
					self._files[name] = f.read()
		self._names = dict.fromkeys(self._files)

	def names(self):
		return list(self._names)

	def has(self, name):
		return name in self._names

	def read(self, name):
		if name not in self._names:
			return None
		if self._zip is not None:
			return self._zip.read(self._names[name])
		return self._files[name]

	def size(self, name):
		if self._zip is not None:
			return self._names[name].file_size
		return len(self._files[name])

	def xml(self, name):
		"""The parsed XML root of a member, or None when it is missing or broken."""
		if not self.has(name):
			return None
		if self.size(name) > limit("lms_migration_max_xml_bytes", MAX_XML_BYTES):
			frappe.throw(_("{0} is too large to read.").format(name))
		try:
			return ElementTree.fromstring(self.read(name))
		except ElementTree.ParseError:
			return None
		except DefusedXmlException:
			frappe.throw(_("{0} declares XML entities, which are not allowed.").format(name))


def ln(tag):
	"""Local name of an XML tag, without its namespace."""
	return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def kids(el, name):
	return [c for c in el if ln(c.tag) == name] if el is not None else []


def kid(el, name):
	found = kids(el, name)
	return found[0] if found else None


def desc(el, name):
	return [c for c in el.iter() if ln(c.tag) == name] if el is not None else []


def first(el, name):
	found = desc(el, name)
	return found[0] if found else None


def text(el, default=""):
	if el is None:
		return default
	return "".join(el.itertext()).strip()


def kid_text(el, name, default=""):
	return text(kid(el, name), default)
