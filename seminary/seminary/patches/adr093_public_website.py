"""decisions/093: write the Public Website switch (on) and the navbar's Portal
link (/seminary) on existing sites, where the new fields would otherwise read
as off and empty, turning every public page into a 404."""

from seminary.install import seed_public_website_defaults


def execute():
    seed_public_website_defaults()
