#!/usr/bin/env python3
"""
Stabilize POT file before commit.
Only allows new/removed strings through, discards reformatting noise.
"""

import subprocess
import sys


def get_previous_pot():
    """Get the last committed version of the POT file."""
    try:
        result = subprocess.run(
            ["git", "show", "HEAD:seminary/locale/main.pot"],
            capture_output=True, text=True
        )
        return result.stdout
    except Exception:
        return ""


def extract_msgids(pot_content):
    """Extract all msgid strings from POT content."""
    msgids = set()
    current_msgid = []
    in_msgid = False

    for line in pot_content.splitlines():
        if line.startswith("msgid "):
            in_msgid = True
            current_msgid = [line[7:-1]]  # strip 'msgid "' and trailing '"'
        elif in_msgid and line.startswith('"'):
            current_msgid.append(line[1:-1])
        else:
            if in_msgid and current_msgid:
                msgids.add("".join(current_msgid))
            in_msgid = False
            current_msgid = []

    if in_msgid and current_msgid:
        msgids.add("".join(current_msgid))

    return msgids


def main():
    pot_file = "seminary/locale/main.pot"

    # Check if POT file is staged
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True
    )
    if pot_file not in result.stdout:
        sys.exit(0)  # POT not staged, nothing to do

    # Compare msgids
    old_pot = get_previous_pot()
    with open(pot_file, "r") as f:
        new_pot = f.read()

    old_msgids = extract_msgids(old_pot)
    new_msgids = extract_msgids(new_pot)

    added = new_msgids - old_msgids
    removed = old_msgids - new_msgids

    if not added and not removed:
        # No real string changes — just reformatting noise
        print("⚠️  POT file has no new/removed strings, only formatting changes.")
        print("   Restoring previous version to avoid translation churn.")
        subprocess.run(["git", "checkout", "--", pot_file])
        subprocess.run(["git", "reset", "HEAD", pot_file])
        sys.exit(0)

    if added:
        print(f"✅ POT file: {len(added)} new string(s)")
        for s in list(added)[:5]:
            print(f"   + {s[:80]}...")

    if removed:
        print(f"🗑️  POT file: {len(removed)} removed string(s)")
        for s in list(removed)[:5]:
            print(f"   - {s[:80]}...")


if __name__ == "__main__":
    main()
