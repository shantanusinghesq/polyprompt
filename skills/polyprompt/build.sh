#!/usr/bin/env bash
# Assembles the claude.ai Agent Skill zip from the CLI's polyprompt/ package,
# so the skill can never silently drift from the CLI it's a subset of.
#
# Usage: skills/polyprompt/build.sh
# Output: skills/polyprompt/polyprompt-skill.zip

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
BUILD_DIR="$SKILL_DIR/build"

rm -rf "$BUILD_DIR" "$SKILL_DIR/polyprompt-skill.zip"
mkdir -p "$BUILD_DIR/scripts/polyprompt/profiles"

cp "$REPO_ROOT"/polyprompt/*.py "$BUILD_DIR/scripts/polyprompt/"
cp "$REPO_ROOT"/polyprompt/*.json "$BUILD_DIR/scripts/polyprompt/"
cp "$REPO_ROOT"/polyprompt/profiles/*.json "$BUILD_DIR/scripts/polyprompt/profiles/"
find "$BUILD_DIR" -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

cp "$SKILL_DIR/SKILL.md" "$BUILD_DIR/SKILL.md"

# Smoke test: the bundled engine must run standalone before we ship it.
( cd "$BUILD_DIR/scripts" && python3 -m polyprompt rewrite --engine claude "smoke test" >/dev/null )

( cd "$BUILD_DIR" && zip -r -q "$SKILL_DIR/polyprompt-skill.zip" . -x "*.DS_Store" )
rm -rf "$BUILD_DIR"

echo "Built $SKILL_DIR/polyprompt-skill.zip"
echo "Upload at claude.ai -> Settings -> Capabilities -> Skills -> Add -> Upload a skill"
