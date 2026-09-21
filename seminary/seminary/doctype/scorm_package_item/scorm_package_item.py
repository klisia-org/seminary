# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""One SCO from a package's manifest (privatedocs p009 §2.5).

Only `<item>`s whose `identifierref` resolves to a resource with
`adlcp:scormType="sco"` become rows here; asset-only resources do not. Each row
becomes a Course Lesson (§2.10), and `sco_identifier` is what a re-uploaded
package is matched on so a cohort's recorded progress survives a replacement.
"""

from frappe.model.document import Document


class SCORMPackageItem(Document):
    pass
