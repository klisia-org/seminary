# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Parse `imsmanifest.xml`, and check what it claims against what the zip holds.

privatedocs p009 §2.5. The manifest is part of the untrusted artifact, so this
module takes exactly four things from it -- the SCORM version, the default
organization, and per SCO a title and a launch path -- and verifies every one of
them. In particular a launch `href` is resolved and then **looked up in the
inventory the explode job just built**: the manifest is checked against the
archive, never the other way round, so a manifest cannot introduce a path the
package does not contain.

Parsing is `defusedxml`, with the DTD forbidden outright. SCORM manifests have
no use for one, and it closes entity expansion as well as external entities --
a manifest is exactly the shape of input that "billion laughs" was written for.

Deliberately frappe-light and exception-based rather than `frappe.throw`-based:
the caller (the explode job) decides what a refusal means -- a `Failed` package
with a reason staff can read, and a counted denial.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass

import defusedxml.ElementTree as ET

#: A manifest may nest items; real packages go two or three deep. The bound is
#: not about correctness, it is about a hand-built manifest that nests until
#: something falls over.
MAX_ITEM_DEPTH = 20

#: Each SCO becomes a Course Lesson (§2.10), so an unbounded item tree is an
#: unbounded number of rows written on the strength of an uploaded file. Raisable
#: as `scorm_max_scos`; the default is far above any real course.
DEFAULT_MAX_SCOS = 200

#: Titles are author strings from a foreign file, and they land in a Data field.
_WHITESPACE = re.compile(r"\s+")

_XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"


class ManifestError(ValueError):
    """The manifest is absent, malformed, or claims something the zip does not
    contain. Always safe to show to staff; never shown to a student."""


@dataclass(frozen=True)
class SCO:
    #: The manifest `<item>` identifier. Lessons are matched on this across a
    #: re-upload, so it is the only durable name a SCO has.
    identifier: str
    title: str
    #: Inventory path of the launch document -- no query, no fragment.
    href: str
    #: The `?query#fragment` the manifest attached, preserved verbatim for the
    #: launch URL and never used for the inventory lookup.
    suffix: str


@dataclass(frozen=True)
class Manifest:
    version: str  # "1.2" | "2004"
    default_organization: str
    scos: tuple[SCO, ...]


# --------------------------------------------------------------------- helpers


def _local(tag) -> str:
    """The local name of a possibly namespaced tag, lowercased.

    Every element and attribute is matched this way. Manifests in the wild
    disagree about prefixes and about namespace URIs (and SCORM 1.2 spells the
    attribute `scormtype` where 2004 spells it `scormType`), so matching on the
    fully qualified name rejects packages that are perfectly valid.
    """
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def _children(element, name: str):
    return [c for c in element if _local(c.tag) == name]


def _first(element, name: str):
    for child in element:
        if _local(child.tag) == name:
            return child
    return None


def _attr(element, name: str, default: str = "") -> str:
    """Attribute by local name, so `adlcp:scormType` and a bare `scormtype`
    both answer."""
    name = name.lower()
    for key, value in element.attrib.items():
        if _local(key) == name:
            return value
    return default


def _text(element) -> str:
    return "".join(element.itertext()) if element is not None else ""


def _clean_title(value: str, fallback: str) -> str:
    """A manifest title is plain text and is stored in a Data field.

    Markup is **stripped**, not sanitised: `clean_rich` would let `<b>` through
    into something that is rendered as a lesson title, and a title is not rich
    text. Entity decoding has already happened in the parser, so this runs after
    it and sees what would actually be stored.
    """
    from frappe.utils import strip_html

    value = _WHITESPACE.sub(" ", strip_html(value or "")).strip()
    return value[:140] or fallback


# ----------------------------------------------------------------- the version


def _detect_version(root) -> str:
    """ "1.2" or "2004". Refuses rather than guessing.

    The launcher advertises `API` for 1.2 and `API_1484_11` for 2004, and
    advertising both confuses packages that probe (§2.8) -- so this has to be
    right. Both specs require `<schemaversion>`; where it is missing or unclear
    the ADL namespace decides, and it is mandatory because `scormType` lives in
    it. If neither answers, the manifest is malformed, and saying so at upload
    beats a chapter that loads and then does nothing.
    """
    metadata = _first(root, "metadata")
    declared = (
        _text(_first(metadata, "schemaversion")).strip().lower()
        if metadata is not None
        else ""
    )
    if declared:
        if "1.2" in declared:
            return "1.2"
        if "2004" in declared or "1.3" in declared or "cam" in declared:
            return "2004"

    namespaces = " ".join(
        str(v)
        for el in root.iter()
        for v in (el.tag, *el.attrib.keys())
        if isinstance(v, str)
    ).lower()
    if "adlcp_v1p3" in namespaces or "adlcp_rootv1p3" in namespaces:
        return "2004"
    if "adlcp_rootv1p2" in namespaces:
        return "1.2"

    raise ManifestError(
        "This SCORM package does not declare which version of SCORM it is."
    )


# ------------------------------------------------------------------- resources


def _resource_map(root) -> dict[str, dict]:
    """`{identifier: {"href", "base", "scormtype"}}` for every `<resource>`.

    `xml:base` is honoured on both `<resources>` and `<resource>` because real
    authoring tools emit it and a package that uses it is not unusual; ignoring
    it would turn every such package into "manifest names a file the archive
    does not contain".
    """
    resources = _first(root, "resources")
    if resources is None:
        return {}

    outer = resources.attrib.get(_XML_BASE, "")
    out = {}
    for resource in _children(resources, "resource"):
        identifier = _attr(resource, "identifier")
        if not identifier:
            continue
        out[identifier] = {
            "href": _attr(resource, "href"),
            "base": posixpath.join(outer, resource.attrib.get(_XML_BASE, "")),
            "scormtype": _attr(resource, "scormtype").strip().lower(),
        }
    return out


def _resolve(base: str, href: str, inventory) -> tuple[str, str]:
    """Resolve a manifest href to `(inventory path, "?query#fragment")`.

    Three refusals, in order, and the third is the one that matters: the path
    must be a key of the inventory. The inventory was built by the explode job
    from members it validated itself, so this single lookup is what stops a
    manifest naming anything outside the package -- traversal included, which is
    why the `..` check below is a courtesy rather than the control.
    """
    href = (href or "").strip().replace("\\", "/")
    if not href:
        raise ManifestError("A SCO in this package has no launch file.")

    # Split BEFORE resolving: `index.html?x=1` is a launch of `index.html`, and
    # looking the whole string up would miss it.
    cut = min(
        (i for i in (href.find("?"), href.find("#")) if i != -1), default=len(href)
    )
    path, suffix = href[:cut], href[cut:]

    if "://" in path or path.startswith("//") or path.startswith("/"):
        raise ManifestError(
            "This SCORM package launches a file outside itself, which is not allowed."
        )

    # NOT `.lstrip("./")`: that strips *characters*, so `../../../etc/passwd`
    # comes back as `etc/passwd` and the check below never fires. `normpath`
    # already removes a leading `./`, which is all that was wanted.
    resolved = posixpath.normpath(posixpath.join(base, path))
    if resolved.startswith("../") or resolved == ".." or resolved in ("", "."):
        raise ManifestError(
            "This SCORM package launches a file outside itself, which is not allowed."
        )

    if resolved not in inventory:
        raise ManifestError(
            f"This SCORM package's manifest names a file it does not contain: {path}"
        )
    return resolved, suffix


# ------------------------------------------------------------------ the items


def _organization(root) -> tuple[str, object]:
    organizations = _first(root, "organizations")
    if organizations is None:
        raise ManifestError("This SCORM package has no organizations.")

    default = _attr(organizations, "default")
    candidates = _children(organizations, "organization")
    if not candidates:
        raise ManifestError("This SCORM package has no organization to play.")

    for org in candidates:
        if default and _attr(org, "identifier") == default:
            return _attr(org, "identifier"), org
    # A `default` naming an organization that is not there is a malformed
    # manifest, but the first organization is unambiguous and playable.
    first = candidates[0]
    return _attr(first, "identifier"), first


def _walk_items(element, resources, inventory, max_scos, depth=0):
    if depth > MAX_ITEM_DEPTH:
        raise ManifestError("This SCORM package's organization is nested too deeply.")

    found = []
    for item in _children(element, "item"):
        ref = _attr(item, "identifierref")
        resource = resources.get(ref) if ref else None
        if resource and _is_sco(resource):
            href, suffix = _resolve(resource["base"], resource["href"], inventory)
            identifier = _attr(item, "identifier") or ref
            found.append(
                SCO(
                    identifier=identifier,
                    title=_clean_title(_text(_first(item, "title")), identifier),
                    href=href,
                    suffix=suffix,
                )
            )
        found.extend(_walk_items(item, resources, inventory, max_scos, depth + 1))
        if len(found) > max_scos:
            raise ManifestError(
                f"This SCORM package declares more than {max_scos} playable items."
            )
    return found


def _is_sco(resource) -> bool:
    """Playable, rather than an asset.

    An explicit `scormType="asset"` is refused. An **absent** scormType is
    treated as playable when the resource has an href, which is a deliberate
    leniency: the attribute is required by both specs and is nonetheless missing
    from real exports, and the strict reading turns those packages into "no
    playable SCO" with nothing an instructor can do about it. Nothing is widened
    by it -- an asset resource with no href still yields no SCO, and every href
    still has to be in the inventory.
    """
    scormtype = resource.get("scormtype") or ""
    if scormtype == "sco":
        return True
    if scormtype:
        return False
    return bool(resource.get("href"))


# ------------------------------------------------------------------- the entry


def parse(xml_bytes: bytes, inventory, max_scos: int = DEFAULT_MAX_SCOS) -> Manifest:
    """Parse and verify a manifest against the package's inventory.

    `inventory` is anything supporting `in` over member paths -- the map the
    explode job has just built, keyed relative to the manifest's own directory.
    """
    try:
        root = ET.fromstring(xml_bytes, forbid_dtd=True)
    except ET.ParseError as e:
        raise ManifestError("This SCORM package's manifest is not valid XML.") from e
    except Exception as e:  # defusedxml's own refusals (DTD, entities, external)
        raise ManifestError(
            "This SCORM package's manifest uses XML features that are not allowed."
        ) from e

    if _local(root.tag) != "manifest":
        raise ManifestError("This SCORM package's manifest is not a manifest.")

    version = _detect_version(root)
    organization_id, organization = _organization(root)
    scos = _walk_items(organization, _resource_map(root), inventory, max_scos)

    if not scos:
        raise ManifestError("This SCORM package has nothing playable in it.")

    return Manifest(
        version=version,
        default_organization=organization_id,
        scos=tuple(scos),
    )
