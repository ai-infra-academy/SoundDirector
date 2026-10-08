#!/usr/bin/env bash
# Publish this repository to GitHub and turn on the GitHub Pages site.
#
#   scripts/publish_github.sh                    # public repo <gh user>/SoundDirector
#   scripts/publish_github.sh --private          # private repo (Pages needs a paid plan)
#   scripts/publish_github.sh --repo my-sounds   # different repository name
#   scripts/publish_github.sh --dry-run          # run the checks and print the plan only
#
# Steps:
#   1. preflight checks
#   2. validate the catalogs and run the tests
#   3. create the GitHub repo if it is missing
#   4. add the remote
#   5. push main
#   6. enable Pages (Source: GitHub Actions)
#   7. wait for the deploy and print the site URL
#
# It is safe to re-run: steps that are already done are skipped.
# Everything is logged to the terminal and to publish.log.

set -euo pipefail

REPO_NAME="SoundDirector"
VISIBILITY="public"
DRY_RUN=0
WAIT=1
BRANCH="main"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$ROOT/publish.log"
cd "$ROOT"

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --private) VISIBILITY="private" ;;
    --public) VISIBILITY="public" ;;
    --repo) REPO_NAME="${2:?--repo needs a name}"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    --no-wait) WAIT=0 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 1 ;;
  esac
  shift
done

# ---------- logging ----------
: > "$LOG_FILE"
if [ -t 1 ]; then
  C_RESET=$'\033[0m'; C_DIM=$'\033[2m'; C_BLUE=$'\033[34m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BOLD=$'\033[1m'
else
  C_RESET=""; C_DIM=""; C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BOLD=""
fi
STEP=0
TOTAL=7
_log() { # level colour message
  local ts; ts="$(date '+%H:%M:%S')"
  printf '%s %s%-5s%s %s\n' "${C_DIM}${ts}${C_RESET}" "$2" "$1" "$C_RESET" "$3"
  printf '%s %-5s %s\n' "$ts" "$1" "$3" >> "$LOG_FILE"
}
step() { STEP=$((STEP + 1)); echo; _log "STEP" "$C_BOLD$C_BLUE" "[$STEP/$TOTAL] $*"; }
info() { _log "INFO" "$C_BLUE" "$*"; }
ok()   { _log "OK" "$C_GREEN" "$*"; }
did()  { if [ "$DRY_RUN" -eq 1 ]; then _log "PLAN" "$C_YELLOW" "would: $*"; else ok "$*"; fi; }
warn() { _log "WARN" "$C_YELLOW" "$*"; }
FAILED=0
fail() { FAILED=1; _log "FAIL" "$C_RED" "$*"; echo "Stopped at step $STEP. Full log: $LOG_FILE"; exit 1; }
run() { # run a command, log it, and stream its output into the log
  info "\$ $*"
  if [ "$DRY_RUN" -eq 1 ]; then info "(dry run: skipped)"; return 0; fi
  "$@" 2>&1 | tee -a "$LOG_FILE"
  return "${PIPESTATUS[0]}"
}
check() { # like run, but also runs in dry-run mode (read-only commands)
  info "\$ $*"
  "$@" 2>&1 | tee -a "$LOG_FILE"
  return "${PIPESTATUS[0]}"
}
trap 'rc=$?; [ $rc -ne 0 ] && [ $FAILED -eq 0 ] && _log "FAIL" "$C_RED" "Stopped at step $STEP (exit $rc). Full log: $LOG_FILE"' EXIT

info "Publishing $(basename "$ROOT") ($( [ "$DRY_RUN" -eq 1 ] && echo "dry run" || echo "live" ))"

# ---------- 1. preflight ----------
step "Preflight checks"
command -v git >/dev/null || fail "git is not installed."
command -v gh >/dev/null || fail "GitHub CLI 'gh' is not installed. Install it with: brew install gh"
command -v python3 >/dev/null || fail "python3 is not installed."
gh auth status >/dev/null 2>&1 || fail "GitHub CLI is not logged in. Run: gh auth login"
OWNER="$(gh api user -q .login)"
FULL="$OWNER/$REPO_NAME"
ok "Logged in to GitHub as $OWNER; target repository $FULL ($VISIBILITY)"
if [ -d .github/workflows ]; then
  SCOPES="$(gh auth status -h github.com 2>&1 | grep -i 'token scopes' || true)"
  if [ -n "$SCOPES" ] && ! printf '%s' "$SCOPES" | grep -q "'workflow'"; then
    fail "Your gh login lacks the 'workflow' scope, which GitHub requires to push .github/workflows/. Run: gh auth refresh -h github.com -s workflow   then re-run this script."
  fi
  ok "gh token can push workflow files"
fi

[ -d .git ] || fail "This folder is not a git repository."
CURRENT="$(git rev-parse --abbrev-ref HEAD)"
[ "$CURRENT" = "$BRANCH" ] || fail "Current branch is '$CURRENT'; switch to '$BRANCH' first."
git rev-parse HEAD >/dev/null 2>&1 || fail "No commits yet. Commit your files first."
if [ -n "$(git status --porcelain)" ]; then
  git status --short | tee -a "$LOG_FILE"
  fail "You have uncommitted changes (listed above). Commit or stash them, then re-run."
fi
ok "Working tree clean on $BRANCH at $(git rev-parse --short HEAD): $(git log -1 --format=%s)"

BIG="$(git ls-files -z | xargs -0 du -k 2>/dev/null | awk '$1 > 51200 {print $2}')"
[ -z "$BIG" ] || fail "Files over 50 MB will be rejected or warned by GitHub: $BIG"
info "Tracked files: $(git ls-files | wc -l | tr -d ' '), working size $(du -sh .claude/skills | cut -f1) of audio"

# ---------- 2. quality gate ----------
step "Validate catalogs and run tests"
check python3 scripts/validate_catalog.py --all || fail "Catalog validation failed."
check python3 -m unittest discover -s tests || fail "Tests failed."
ok "Catalogs valid and tests pass"

# ---------- 3. repository ----------
step "Create the GitHub repository"
if gh repo view "$FULL" >/dev/null 2>&1; then
  ok "Repository $FULL already exists; skipping creation"
else
  run gh repo create "$FULL" "--$VISIBILITY" \
    --description "Searchable sound effects and instrumental background music skills for Claude Code" \
    || fail "Could not create $FULL."
  did "create https://github.com/$FULL"
fi

# ---------- 4. remote ----------
step "Configure the git remote"
PROTOCOL="$(gh config get git_protocol -h github.com 2>/dev/null || echo https)"
if [ "$PROTOCOL" = "ssh" ]; then
  if ssh -o BatchMode=yes -o ConnectTimeout=10 -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    URL="git@github.com:$FULL.git"
  else
    warn "SSH access to GitHub isn't working; using HTTPS with gh credentials instead"
    PROTOCOL="https"
  fi
fi
if [ "$PROTOCOL" != "ssh" ]; then
  [ "$DRY_RUN" -eq 1 ] || gh auth setup-git >/dev/null 2>&1 || true
  URL="https://github.com/$FULL.git"
fi
if git remote get-url origin >/dev/null 2>&1; then
  EXISTING="$(git remote get-url origin)"
  case "$EXISTING" in
    *"$FULL"*|*"$FULL.git") ok "origin already points to $EXISTING" ;;
    *) fail "origin points to $EXISTING, not $FULL. Fix it with: git remote set-url origin $URL" ;;
  esac
else
  run git remote add origin "$URL"
  did "add origin -> $URL"
fi

# ---------- 5. push ----------
step "Push $BRANCH (the audio is large, so this can take a few minutes)"
if ! run git push -u origin "$BRANCH"; then
  if grep -q "without \`workflow\` scope" "$LOG_FILE"; then
    fail "GitHub rejected the workflow files: your gh token lacks the 'workflow' scope. Run: gh auth refresh -h github.com -s workflow   then re-run this script."
  fi
  fail "Push failed. See the git output above, fix the cause, and re-run."
fi
did "push $(git rev-parse --short HEAD) to $FULL"

# ---------- 6. pages ----------
step "Enable GitHub Pages (Source: GitHub Actions)"
if [ "$DRY_RUN" -eq 1 ]; then
  info "(dry run: would enable Pages with build_type=workflow)"
elif gh api "repos/$FULL/pages" >/dev/null 2>&1; then
  run gh api -X PUT "repos/$FULL/pages" -f build_type=workflow >/dev/null || warn "Could not update the Pages source; set it in Settings → Pages."
  ok "Pages already enabled; source set to GitHub Actions"
else
  if run gh api -X POST "repos/$FULL/pages" -f build_type=workflow >/dev/null; then
    ok "Pages enabled"
  else
    warn "Could not enable Pages automatically (private repos need a paid plan). Set it in Settings → Pages → Source: GitHub Actions."
  fi
fi

# ---------- 7. deploy ----------
step "Wait for the site deploy"
SITE_URL="https://$OWNER.github.io/$REPO_NAME/"
if PAGES_URL="$(gh api "repos/$FULL/pages" -q .html_url 2>/dev/null)" && [ -n "$PAGES_URL" ]; then SITE_URL="$PAGES_URL"; fi
if [ "$DRY_RUN" -eq 1 ] || [ "$WAIT" -eq 0 ]; then
  info "Skipping the wait. Follow the deploy with: gh run watch -R $FULL"
else
  RUN_ID=""
  for _ in $(seq 1 12); do
    RUN_ID="$(gh run list -R "$FULL" --workflow pages.yml --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || true)"
    [ -n "$RUN_ID" ] && break
    info "Waiting for the deploy workflow to start..."
    sleep 5
  done
  if [ -z "$RUN_ID" ]; then
    # The push may have happened before Pages was enabled; start a deploy explicitly.
    run gh workflow run pages.yml -R "$FULL" --ref "$BRANCH" || true
    sleep 8
    RUN_ID="$(gh run list -R "$FULL" --workflow pages.yml --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || true)"
  fi
  if [ -n "$RUN_ID" ]; then
    info "Following run https://github.com/$FULL/actions/runs/$RUN_ID"
    if gh run watch "$RUN_ID" -R "$FULL" --exit-status 2>&1 | tee -a "$LOG_FILE" >/dev/null; then
      ok "Deploy finished"
    else
      warn "The deploy did not succeed. If it failed because Pages was not enabled yet, re-run it with: gh run rerun $RUN_ID -R $FULL"
    fi
  else
    warn "No deploy run found. Start one with: gh workflow run pages.yml -R $FULL"
  fi
fi

echo
if [ "$DRY_RUN" -eq 1 ]; then ok "Dry run complete. Nothing was changed on GitHub. Run without --dry-run to publish."; else ok "Done"; fi
info "Repository: https://github.com/$FULL"
info "Website:    $SITE_URL"
info "CI runs:    https://github.com/$FULL/actions"
info "Log file:   $LOG_FILE"
