"""Seed the ethnic groups and keep every stored value (ADR 086)."""

from seminary.seminary.ethnic_groups import keep_existing_values


def execute():
    keep_existing_values()
