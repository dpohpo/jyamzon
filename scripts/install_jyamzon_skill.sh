#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_SRC="$ROOT_DIR/skills/jyamzon"

install_codex=false
install_claude=false

usage() {
  cat <<'USAGE'
Usage: scripts/install_jyamzon_skill.sh [--all|--codex|--claude]

Installs the bundled jyamzon skill into local agent skill folders.

Options:
  --all      Install to ~/.codex/skills and ~/.claude/skills
  --codex    Install to ~/.codex/skills only
  --claude   Install to ~/.claude/skills only
USAGE
}

if [[ $# -eq 0 ]]; then
  install_codex=true
  install_claude=true
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      install_codex=true
      install_claude=true
      ;;
    --codex)
      install_codex=true
      ;;
    --claude)
      install_claude=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
  shift
done

install_one() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  cp -R "$SKILL_SRC" "$dest"
  echo "Installed jyamzon skill to: $dest"
}

if [[ "$install_codex" == true ]]; then
  install_one "$HOME/.codex/skills/jyamzon"
fi

if [[ "$install_claude" == true ]]; then
  install_one "$HOME/.claude/skills/jyamzon"
fi
