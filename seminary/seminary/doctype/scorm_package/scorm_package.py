# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""One unpacked SCORM package, and the inventory delivery serves from.

The inventory is the security control of the whole feature (privatedocs p009
§2.3): it is written once, by the explode job, from member paths that job
normalised itself, and the delivery endpoint answers a request **only** for a
path that is a key of it. A client therefore never names an object key -- it
names an inventory entry or it gets a 404. Traversal, bucket probing and
"guess another school's prefix" all stop at that one lookup.

Two things about the key prefix are deliberate and easy to get backwards:

* **It is random, not a content hash.** p004 keys media by content hash because
  Frappe's blob refcount is `content_hash` and nothing else; here the refcount
  is a chapter link in our own schema, so nothing forces it -- and
  `File.content_hash` is **MD5**, so a key derived from it would let a crafted
  colliding zip land on top of another section's package tree.
* **Dedup is still by content**, on `source_sha256`, computed while streaming
  at explode time. Lookup by a strong hash, addressing by an unguessable id.
"""

from __future__ import annotations

import json

import frappe
from frappe.model.document import Document

#: Top-level key prefix. Deliberately not `media/`, which is `seminary.storage`'s
#: content-addressed space and is refcounted by `File` rows -- a package tree is
#: neither. See p009 §2.3.
KEY_PREFIX = "scorm"

#: Bytes of randomness in a package id, as hex characters.
PACKAGE_ID_LENGTH = 32


class SCORMPackage(Document):
    def before_insert(self):
        if not self.package_id:
            self.package_id = frappe.generate_hash(length=PACKAGE_ID_LENGTH)

    # ------------------------------------------------------------------ keys
    @property
    def key_prefix(self) -> str:
        """The object-storage prefix this package owns, with a trailing slash.

        Every key the explode job writes and every key delivery reads is built
        from here, so a package can only ever address its own subtree.
        """
        if not self.package_id:
            frappe.throw("SCORM package has no package_id")
        return f"{KEY_PREFIX}/{self.package_id}/"

    def key_for(self, member_path: str) -> str:
        return f"{self.key_prefix}{member_path}"

    # ------------------------------------------------------------- inventory
    def get_inventory(self) -> dict[str, dict]:
        """`{member path: {"size", "sha256", "content_type"}}`.

        Parsed on demand and memoised on the document, because delivery reads it
        once per asset request and a package may hold thousands of entries.
        """
        cached = getattr(self, "_inventory", None)
        if cached is None:
            cached = frappe.parse_json(self.inventory or "{}") or {}
            self._inventory = cached
        return cached

    def member(self, member_path: str) -> dict | None:
        """The inventory entry for `member_path`, or None.

        **Looked up verbatim.** No normalisation happens here, and none may be
        added: normalising at read time is where traversal bugs live. The path
        the client sent either is a key of the inventory -- which the explode
        job wrote after validating it -- or it is not.
        """
        return self.get_inventory().get(member_path)

    def set_inventory(self, inventory: dict[str, dict]) -> None:
        self._inventory = inventory
        self.inventory = json.dumps(inventory, sort_keys=True)
        self.entry_count = len(inventory)
        self.total_bytes = sum(int(e.get("size") or 0) for e in inventory.values())

    def on_trash(self):
        """Take the objects with the row.

        `lifecycle.release` is the refcounted door and normally deletes them
        first; this covers a row deleted directly -- from Desk, or by a cascade
        -- which would otherwise strand a whole tree with nothing left pointing
        at it. Deleting twice is harmless; leaving bytes with no row is not.
        """
        from seminary.scorm import lifecycle

        lifecycle.delete_objects(self.name)
