import frappe
from frappe.utils.file_manager import save_file
import os
from frappe.utils import getdate




@frappe.whitelist()
def upload_folder():
    """
    Handle folder uploads using Frappe's file system.
    """
    from frappe.utils.file_manager import save_file

    foldername = frappe.form_dict.get("foldername")
    uploaded_files = frappe.request.files.getlist("files")

    print("Uploading files to folder:", foldername)
    print("Received files:", uploaded_files)

    if not uploaded_files or not foldername:
        frappe.throw("Files and folder name are required.")

    folder = frappe.get_value("File", {"file_name": foldername, "is_folder": 1}, "name")
    if not folder:
        frappe.throw(f"Folder '{foldername}' not found.")

    saved = []
    for file in uploaded_files:
        content = file.stream.read()
        # Pass None for the 'dn' argument since the file is being saved to a folder
        file_doc = save_file(file.filename, content, None, folder=folder, is_private=True, dn=None)
        saved.append({
            "name": file_doc.file_name,
            "url": file_doc.file_url,
        })

    return {
        "folder_name": foldername,
        "files": saved,
    }


@frappe.whitelist()
def get_files_in_folder(foldername):
    """
    Retrieve files in a specified folder.

    Args:
        folder_name (str): Name of the folder to retrieve files from.

    Returns:
        list: List of file metadata.
    """
    if not foldername:
        frappe.throw("Folder name is required.")

    folder = frappe.db.get_value("File", {"file_name": foldername, "is_folder": 1}, "name")


    files = frappe.get_all("File", filters={"folder": folder}, fields='*')

    return files
