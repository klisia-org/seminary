#!/usr/bin/env bash
# Frappe's semgrep rules, run the same way in CI and in pre-commit.
# Usage: scripts/semgrep.sh [files...]   (no files: the whole repository, as CI scans it)
set -euo pipefail

RULES=".frappe-semgrep"
if [ ! -d "$RULES/rules" ]; then
	git clone --quiet --depth 1 https://github.com/frappe/semgrep-rules.git "$RULES"
elif [ -z "${CI:-}" ]; then
	# Local runs keep up with the rules CI clones fresh; offline, the copy we have still runs.
	git -C "$RULES" pull --quiet --ff-only 2>/dev/null || true
fi

# Only findings a change introduces fail: the ones already there are tracked in a decision record
# and fixed in their own pass. Locally that is against HEAD; CI passes the branch's base.
BASELINE=()
BASE="${SEMGREP_BASELINE_REF:-HEAD}"
if git rev-parse --verify --quiet "$BASE^{commit}" >/dev/null; then
	BASELINE=(--baseline-commit "$(git rev-parse "$BASE")")
fi

exec semgrep scan \
	"${BASELINE[@]}" \
	--config "./$RULES/rules" \
	--exclude node_modules \
	--exclude .history \
	--exclude frontend \
	--exclude portal-shell \
	--exclude seminary/public/frontend \
	--exclude seminary/builder_files \
	--exclude scripts \
	--exclude runbooks \
	--exclude tooling \
	--exclude "$RULES" \
	--error \
	--quiet \
	--metrics=off \
	"$@"
