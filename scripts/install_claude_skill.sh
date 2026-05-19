#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_SRC="$ROOT_DIR/skills/jyamzon"
SKILL_DEST="$HOME/.claude/skills/jyamzon"

mkdir -p "$(dirname "$SKILL_DEST")"
rm -rf "$SKILL_DEST"
cp -R "$SKILL_SRC" "$SKILL_DEST"

echo "Installed Claude Code skill to: $SKILL_DEST"

