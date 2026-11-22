#!/usr/bin/env python3
"""Stabilize the POT file before commit.

Only new or removed strings get through; a regenerated POT with the same strings is restored, so
translators see no churn. Shared by every app and kept in sync by a script.
"""

import glob
import subprocess
import sys


def pot_path():
	found = glob.glob("*/locale/main.pot")
	return found[0] if len(found) == 1 else None


def previous_pot(path):
	"""The last committed version of the POT file."""
	result = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, text=True)
	return result.stdout if result.returncode == 0 else ""


def msgids(content):
	found, current, inside = set(), [], False
	for line in content.splitlines():
		if line.startswith("msgid "):
			inside, current = True, [line[7:-1]]
		elif inside and line.startswith('"'):
			current.append(line[1:-1])
		else:
			if inside and current:
				found.add("".join(current))
			inside, current = False, []
	if inside and current:
		found.add("".join(current))
	return found


def main():
	path = pot_path()
	if not path:
		sys.exit(0)
	staged = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True)
	if path not in staged.stdout.split():
		sys.exit(0)

	old, new = msgids(previous_pot(path)), msgids(open(path).read())
	added, removed = new - old, old - new
	if not added and not removed:
		print("POT file has no new or removed strings, only formatting changes.")
		print("   Restoring the committed version to avoid translation churn.")
		# Working tree and index together, so pre-commit does not see a modified file.
		subprocess.run(["git", "checkout", "HEAD", "--", path])
		sys.exit(0)
	if added:
		print(f"POT file: {len(added)} new string(s)")
		for s in sorted(added)[:5]:
			print(f"   + {s[:80]}")
	if removed:
		print(f"POT file: {len(removed)} removed string(s)")
		for s in sorted(removed)[:5]:
			print(f"   - {s[:80]}")


if __name__ == "__main__":
	main()
