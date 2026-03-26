#!/usr/bin/env bash
set -euo pipefail

# sync-clean.sh — Sync the 'clean' branch from the working branch
#
# Creates a squashed snapshot of the source branch on top of origin/main,
# with dev-only paths (listed in .cleanignore) stripped out.
# Result: clean branch stays slim (1 commit ahead of main per sync).
#
# Usage:
#   ./scripts/sync-clean.sh                              # sync from current branch
#   ./scripts/sync-clean.sh feature/agentic-runtime      # sync from specific branch
#   ./scripts/sync-clean.sh --push                       # sync and push
#   ./scripts/sync-clean.sh --push feature/agentic-runtime

SOURCE_BRANCH=""
PUSH=false

for arg in "$@"; do
  case "$arg" in
    --push) PUSH=true ;;
    *) SOURCE_BRANCH="$arg" ;;
  esac
done

SOURCE_BRANCH="${SOURCE_BRANCH:-$(git branch --show-current)}"

if [ "$SOURCE_BRANCH" = "clean" ]; then
  echo "Error: already on clean branch. Switch to your working branch first."
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
CLEANIGNORE="$REPO_ROOT/.cleanignore"
if [ ! -f "$CLEANIGNORE" ]; then
  echo "Error: .cleanignore not found at $CLEANIGNORE"
  exit 1
fi

# Read paths from .cleanignore (skip comments and blank lines)
EXCLUDE_PATHS=()
while IFS= read -r line; do
  line="${line%%#*}"        # strip inline comments
  line="${line// /}"        # trim whitespace
  [ -z "$line" ] && continue
  EXCLUDE_PATHS+=("$line")
done < "$CLEANIGNORE"

if [ ${#EXCLUDE_PATHS[@]} -eq 0 ]; then
  echo "Error: no paths found in .cleanignore"
  exit 1
fi

echo "=== Syncing clean branch from $SOURCE_BRANCH ==="
echo "Paths to exclude: ${#EXCLUDE_PATHS[@]}"

# Stash any uncommitted work
STASHED=false
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Stashing uncommitted changes..."
  git stash push -m "sync-clean: auto-stash"
  STASHED=true
fi

# Fetch latest main
git fetch origin main --quiet 2>/dev/null || true

# Strategy: reset clean branch to origin/main, then overlay source files
# This avoids merge commits and keeps history squashed.

if git rev-parse --verify clean >/dev/null 2>&1; then
  git checkout clean
  # Reset clean to origin/main (no history from source branch)
  git reset --soft origin/main
else
  echo "Creating clean branch from origin/main..."
  git checkout -b clean origin/main
fi

# Overlay all files from source branch
git checkout "$SOURCE_BRANCH" -- . 2>/dev/null || true

# Stage everything
git add -A

# Remove excluded paths (supports globs like **/.claude/ and **/tests/findings.md)
REMOVED=0
for pattern in "${EXCLUDE_PATHS[@]}"; do
  MATCHES=$(git ls-files --cached "$pattern" 2>/dev/null || true)
  if [ -n "$MATCHES" ]; then
    echo "$MATCHES" | xargs git rm -r --cached --quiet --force 2>/dev/null || true
    echo "$MATCHES" | xargs rm -rf 2>/dev/null || true
    COUNT=$(echo "$MATCHES" | wc -l)
    REMOVED=$((REMOVED + COUNT))
  fi
done

echo "Stripped $REMOVED excluded files"

# Check if there's anything to commit
if git diff --cached --quiet; then
  echo "No changes to commit (clean branch is up to date with $SOURCE_BRANCH)"
else
  CHANGED=$(git diff --cached --stat | tail -1)
  git commit -m "$(cat <<EOF
chore: sync clean from $SOURCE_BRANCH

$CHANGED
Stripped $REMOVED dev-only files via .cleanignore
EOF
)"
fi

echo ""
echo "=== Clean branch status ==="
echo "Commits ahead of main: $(git log --oneline origin/main..clean | wc -l)"
git log --oneline -5 clean

if [ "$PUSH" = true ]; then
  echo ""
  echo "Pushing clean to origin..."
  git push origin clean --force-with-lease
fi

# Return to source branch
git checkout "$SOURCE_BRANCH"

# Restore stash if we stashed
if [ "$STASHED" = true ]; then
  echo "Restoring stashed changes..."
  git stash pop
fi

echo ""
echo "Done. You're back on $SOURCE_BRANCH."
