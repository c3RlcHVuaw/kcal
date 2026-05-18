#!/usr/bin/env sh
set -eu

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not inside a git repository." >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Git remote 'origin' is not configured." >&2
  echo "Add it first, for example:" >&2
  echo "  git remote add origin git@github.com:OWNER/kcal-tracker.git" >&2
  exit 1
fi

if [ -z "$(git status --porcelain)" ]; then
  echo "No changes to commit."
  exit 0
fi

message="${1:-Auto-push project changes}"

git add -A
git commit -m "$message"

branch="$(git branch --show-current)"
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git push
else
  git push -u origin "$branch"
fi
