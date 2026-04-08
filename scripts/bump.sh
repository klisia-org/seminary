#!/usr/bin/env bash
# Usage: ./scripts/bump.sh 1.2.0
# Updates version in all files, commits, and tags.
set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]] || ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Usage: $0 <MAJOR.MINOR.PATCH>"
  echo "Example: $0 1.2.0"
  exit 1
fi

cd "$(git rev-parse --show-toplevel)"

# 1. Python source of truth
sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" seminary/__init__.py

# 2. Root package.json
sed -i "s/\"version\": \".*\"/\"version\": \"$VERSION\"/" package.json

# 3. Frontend package.json
sed -i "s/\"version\": \".*\"/\"version\": \"$VERSION\"/" frontend/package.json

echo "Version bumped to $VERSION in:"
echo "  - seminary/__init__.py"
echo "  - package.json"
echo "  - frontend/package.json"
echo ""
echo "Next steps:"
echo "  git add seminary/__init__.py package.json frontend/package.json"
echo "  git commit -m 'Bump version to $VERSION'"
echo "  git tag v$VERSION"
