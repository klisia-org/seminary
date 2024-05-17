import frappe
import os
import re

def pre_uninstall():
    """
    Remove the SVG symbol file from the sites/assets/frappe/icons/timeless/icons.svg file by ID.
    """
    src_path = os.path.join(os.path.dirname(frappe.get_site_path()), 'assets', 'frappe', 'icons', 'timeless', 'icons.svg')

    with open(src_path, 'r+') as f:
        content = f.read()

        # Find the symbol tag with the specified ID.
        m = re.search(r'<svg id="icon-sem"(.|\n)*</svg>', content)
        if m:
            # Remove the symbol tag from the content.
            content = content[:m.start()] + content[m.end():]

        f.seek(0)
        f.write(content)
        f.truncate()