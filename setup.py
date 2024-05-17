from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in seminary/__init__.py
from seminary import __version__ as version

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
