# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from seminary.seminary.integrations.bible import get_bible_name


class BibleAPILanguageDefault(Document):
    def validate(self):
        if self.bible_id and (
            self.has_value_changed("bible_id") or not self.bible_name
        ):
            self.bible_name = get_bible_name(self.bible_id)
