"""Build and unpack a real SCORM package on a site with live object storage.

    bench --site potestas.localhost execute \
        seminary.scripts_p009.p3fixtures.main   # (or via runpy, see README)

Everything the automated suite covers runs against a fake backend in a dict.
This is the only check that the unpack path works against the real store --
multipart-capable `put_fileobj`, `stream` back out through the proxy, and a
presigned GET for the redirected members.

Leaves behind: one Course Schedule Chapter, one File, one SCORM Package and its
objects. `teardown()` removes all of them, objects included.
"""

import io
import pathlib
import zipfile

import frappe

MANIFEST = """<?xml version="1.0"?>
<manifest identifier="P9" xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
  <metadata><schema>ADL SCORM</schema><schemaversion>1.2</schemaversion></metadata>
  <organizations default="ORG"><organization identifier="ORG">
    <title>p009 smoke package</title>
    <item identifier="SCO1" identifierref="RES1"><title>Lesson one</title></item>
    <item identifier="SCO2" identifierref="RES2"><title>Lesson two</title></item>
  </organization></organizations>
  <resources>
    <resource identifier="RES1" adlcp:scormtype="sco" href="index.html"/>
    <resource identifier="RES2" adlcp:scormtype="sco" href="two/start.html"/>
    <resource identifier="RES3" adlcp:scormtype="asset" href="media/clip.mp4"/>
  </resources>
</manifest>"""

INDEX = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="assets/style.css"></head>
<body><h1>p009 SCO one</h1>
<img src="assets/dot.png" alt="">
<video src="media/clip.mp4" controls></video>
<script src="assets/app.js"></script></body></html>"""

TWO = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="../assets/style.css"></head>
<body><h1>p009 SCO two</h1></body></html>"""

MEMBERS = {
    "index.html": INDEX,
    "two/start.html": TWO,
    "assets/style.css": "body{font-family:system-ui}h1{color:#036}",
    "assets/app.js": "console.log('p009 sco');",
    "assets/dot.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 64,
    # Big enough to be worth redirecting, small enough to be polite.
    "media/clip.mp4": b"\x00\x00\x00\x18ftypmp42" + b"\x11" * (256 * 1024),
}

CHAPTER_TITLE = "ZZT p009 smoke"


def _zip_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("imsmanifest.xml", MANIFEST)
        for name, content in MEMBERS.items():
            zf.writestr(name, content)
    return buf.getvalue()


def main(zip_path=None, title=None):
    """Unpack the built-in smoke package, or a real one from `zip_path`.

    A synthetic package is structurally honest and nothing like what an
    authoring tool emits. Pass a real export to find out what the difference
    costs -- that is what this argument is for.
    """
    from seminary.scorm import explode, tokens

    teardown(quiet=True)

    chapter = frappe.new_doc("Course Schedule Chapter")
    chapter.chapter_title = title or CHAPTER_TITLE
    chapter.is_scorm_package = 1
    chapter.flags.ignore_mandatory = True
    chapter.flags.ignore_permissions = True
    chapter.insert()

    payload = pathlib.Path(zip_path).read_bytes() if zip_path else _zip_bytes()
    f = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": "zzt-p009-smoke.zip",
            "content": payload,
            "is_private": 1,
        }
    )
    f.flags.ignore_permissions = True
    f.insert()

    package = frappe.get_doc(
        {"doctype": "SCORM Package", "source_file": f.name, "status": "Pending"}
    )
    package.insert(ignore_permissions=True)
    frappe.db.set_value(
        "Course Schedule Chapter", chapter.name, "scorm_package_ref", package.name
    )
    frappe.db.commit()

    explode.explode_package(chapter.name, package.name)
    package.reload()

    if package.status != "Ready":
        print(f"UNPACK FAILED: {package.failure_reason}")
        return

    token = tokens.mint("Administrator", package.name, chapter.name)
    host = frappe.conf.get("scorm_delivery_host") or "(scorm_delivery_host NOT SET)"

    print(f"zip bytes          {len(payload)}")
    print(f"chapter            {chapter.name}")
    print(f"package            {package.name}  id={package.package_id}")
    print(f"scorm_version      {package.scorm_version}")
    print(f"entries            {package.entry_count}  bytes={package.total_bytes}")
    print(f"SCOs               {[i.sco_identifier for i in package.items]}")
    print(
        "lessons            "
        + str(
            frappe.get_all(
                "Course Lesson",
                filters={"chapter": chapter.name},
                pluck="lesson_title",
                order_by="creation",
            )
        )
    )
    print(f"inventory          {sorted(package.get_inventory())}")
    print(f"HOST               {host}")
    print(f"BASE               /scorm/{token}/{package.package_id}/")


def teardown(quiet=False):
    from seminary.scorm import lifecycle

    for name in frappe.get_all(
        "Course Schedule Chapter",
        filters={"chapter_title": ["like", "ZZT p009%"]},
        pluck="name",
    ):
        ref = frappe.db.get_value("Course Schedule Chapter", name, "scorm_package_ref")
        frappe.db.delete("Course Schedule Lesson Reference", {"parent": name})
        frappe.db.delete("Course Lesson", {"chapter": name})
        frappe.db.delete("Course Schedule Chapter", name)
        if ref:
            frappe.db.set_value(
                "Course Schedule Chapter",
                {"scorm_package_ref": ref},
                "scorm_package_ref",
                None,
            )
            lifecycle.release(ref)

    for name in frappe.get_all(
        "File", filters={"file_name": "zzt-p009-smoke.zip"}, pluck="name"
    ):
        frappe.delete_doc("File", name, ignore_permissions=True, force=True)

    frappe.db.commit()
    if not quiet:
        print("p009 smoke fixtures removed, objects included")
