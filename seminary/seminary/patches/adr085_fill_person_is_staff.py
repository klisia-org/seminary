"""Fill Person.is_staff on existing sites (decisions/085)."""

from seminary.seminary.staff import refresh


def execute():
    refresh()
