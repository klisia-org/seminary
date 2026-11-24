import re
from pathlib import Path

from setuptools import find_packages, setup

here = Path(__file__).parent

# Read, not import: an isolated build (uv, pip >= 23) does not have the package
# on sys.path, so `from seminary import __version__` fails there.
version = re.search(
	r'^__version__\s*=\s*["\']([^"\']+)["\']',
	(here / "seminary" / "__init__.py").read_text(),
	re.M,
).group(1)

install_requires = [
	line.split("#", 1)[0].strip()
	for line in (here / "requirements.txt").read_text().splitlines()
	if line.split("#", 1)[0].strip()
]

setup(
	name="seminary",
	version=version,
	description="Seminary Management System",
	author="Klisia and Frappe",
	author_email="support@seminaryerp.org",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
)
