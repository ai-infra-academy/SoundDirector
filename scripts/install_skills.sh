#!/usr/bin/env bash
# Install the sound-effects and background-music skills globally.
#
#   scripts/install_skills.sh               # symlink both into ~/.claude/skills
#   scripts/install_skills.sh --copy        # copy instead of symlink (no search script; catalog.json only)
#   scripts/install_skills.sh --dir PATH    # install somewhere else, e.g. ~/.config/opencode/skills
#   scripts/install_skills.sh --uninstall   # remove what this script installed
#
# ~/.claude/skills is read by Claude Code and by OpenCode, so the default install works for both.
# A symlink keeps the skills current with `git pull` and lets the search script work from any project.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SKILLS=(sound-effects background-music)
DEST="$HOME/.claude/skills"
MODE="link"
ACTION="install"

while [ $# -gt 0 ]; do
  case "$1" in
    --copy) MODE="copy" ;;
    --dir) DEST="${2:?--dir needs a path}"; shift ;;
    --uninstall) ACTION="uninstall" ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

if [ -t 1 ]; then G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[34m'; N=$'\033[0m'; else G=""; Y=""; R=""; B=""; N=""; fi
info() { printf '%sINFO%s  %s\n' "$B" "$N" "$*"; }
ok()   { printf '%sOK%s    %s\n' "$G" "$N" "$*"; }
warn() { printf '%sWARN%s  %s\n' "$Y" "$N" "$*"; }
fail() { printf '%sFAIL%s  %s\n' "$R" "$N" "$*"; exit 1; }

points_here() { [ -L "$1" ] && [ "$(cd "$1" 2>/dev/null && pwd -P)" = "$ROOT/.claude/skills/$(basename "$1")" ]; }
is_our_copy() { [ -d "$1" ] && [ ! -L "$1" ] && [ -f "$1/.installed-from-sounddirector" ]; }

mkdir -p "$DEST"
info "Repository: $ROOT"
info "Target:     $DEST ($ACTION, $MODE)"

for skill in "${SKILLS[@]}"; do
  src="$ROOT/.claude/skills/$skill"
  dst="$DEST/$skill"
  [ -f "$src/SKILL.md" ] || fail "$src/SKILL.md is missing"

  if [ "$ACTION" = "uninstall" ]; then
    if points_here "$dst"; then rm "$dst"; ok "removed link $dst"
    elif is_our_copy "$dst"; then rm -rf "$dst"; ok "removed copy $dst"
    elif [ -e "$dst" ] || [ -L "$dst" ]; then warn "$dst was not installed by this script; left it alone"
    else info "$dst not installed"; fi
    continue
  fi

  if points_here "$dst"; then ok "$skill already linked -> $src"; continue; fi
  if is_our_copy "$dst"; then rm -rf "$dst"
  elif [ -e "$dst" ] || [ -L "$dst" ]; then
    fail "$dst already exists and isn't from this repo. Move it away first, then re-run."
  fi

  if [ "$MODE" = "link" ]; then
    ln -s "$src" "$dst"
    ok "$skill linked: $dst -> $src"
  else
    cp -R "$src" "$dst"
    : > "$dst/.installed-from-sounddirector"
    ok "$skill copied to $dst ($(du -sh "$dst" | cut -f1))"
  fi
done

[ "$ACTION" = "uninstall" ] && exit 0

# Smoke test: search through the installed path, the way an agent would.
if [ "$MODE" = "link" ]; then
  for skill in "${SKILLS[@]}"; do
    n="$(cd / && python3 "$DEST/$skill/../../../scripts/search_assets.py" --skill "$skill" --json --limit 1 \
         | python3 -c 'import json,sys; print(json.load(sys.stdin)["catalog_entries"])')" \
      || fail "search through $DEST/$skill failed"
    ok "$skill searchable from any directory ($n assets)"
  done
fi

command -v opencode >/dev/null && info "OpenCode: run 'opencode debug skill' to confirm it sees the skills."
info "Claude Code: start a new session; the skills are listed under /skills."
