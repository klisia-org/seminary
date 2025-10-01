import frappe


def _get_course_folder_name_for_file(file_name: str) -> str | None:
    visited: set[str] = set()
    current = file_name
    while current and current not in visited:
        course_folder = frappe.db.get_value(
            "Course Folder",
            {"file_reference": current},
            ["name"],
            as_dict=True,
        )
        if course_folder:
            return course_folder.name
        visited.add(current)
        parent = frappe.db.get_value("File", current, "folder")
        if not parent or parent in visited:
            break
        current = parent
    return None


def _link_file(file_name: str, course_folder_name: str) -> None:
    if not file_name or not course_folder_name:
        return
    current = frappe.db.get_value(
        "File",
        file_name,
        ["attached_to_doctype", "attached_to_name"],
        as_dict=True,
    )
    if current and current.attached_to_doctype == "Course Folder" and current.attached_to_name == course_folder_name:
        return
    frappe.db.set_value(
        "File",
        file_name,
        "attached_to_doctype",
        "Course Folder",
        update_modified=False,
    )
    frappe.db.set_value(
        "File",
        file_name,
        "attached_to_name",
        course_folder_name,
        update_modified=False,
    )


def execute():
    course_folders = frappe.get_all("Course Folder", fields=["name", "file_reference"])
    for record in course_folders:
        if record.file_reference:
            _link_file(record.file_reference, record.name)

    file_names = frappe.get_all("File", fields=["name"])
    for file_doc in file_names:
        course_folder_name = _get_course_folder_name_for_file(file_doc.name)
        if course_folder_name:
            _link_file(file_doc.name, course_folder_name)
