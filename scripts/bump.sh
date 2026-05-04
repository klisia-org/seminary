#!/usr/bin/env bash
# Use git add . beforehand
# Usage: ./scripts/bump.sh 1.2.0
# Updates version in all files, commits, pushes, and creates a GitHub Release.
set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]] || ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Usage: $0 <MAJOR.MINOR.PATCH>"
  echo "Example: $0 1.2.0"
  exit 1
fi

cd "$(git rev-parse --show-toplevel)"
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# 1. Update version in all files
sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" seminary/__init__.py
sed -i "s/\"version\": \".*\"/\"version\": \"$VERSION\"/" package.json
sed -i "s/\"version\": \".*\"/\"version\": \"$VERSION\"/" frontend/package.json

echo "Version bumped to $VERSION in:"
echo "  - seminary/__init__.py"
echo "  - package.json"
echo "  - frontend/package.json"
echo ""

# 2. Commit
git add seminary/__init__.py package.json frontend/package.json
git commit -m "Bump version to $VERSION"

# 3. Push
git push origin "$BRANCH"

# 4. Create GitHub Release (also creates the tag)
echo "Creating GitHub Release v$VERSION..."
gh release create "v$VERSION" \
  --target "$BRANCH" \
  --title "v$VERSION" \
  --generate-notes

echo ""
echo "Done! Release v$VERSION created with auto-generated notes from merged PRs."
