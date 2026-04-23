#!/usr/bin/env bash
set -euo pipefail

# Blocks dev-only specs/docs on non-dev branches.
# Usage:
#   scripts/check_dev_specs_branch.sh            # check files in HEAD
#   scripts/check_dev_specs_branch.sh --staged   # check staged files
#   scripts/check_dev_specs_branch.sh --worktree # check unstaged worktree diff

MODE="head"
if [[ "${1:-}" == "--staged" ]]; then
  MODE="staged"
elif [[ "${1:-}" == "--worktree" ]]; then
  MODE="worktree"
elif [[ -n "${1:-}" ]]; then
  echo "Unknown option: $1" >&2
  exit 2
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
if [[ "$BRANCH" == "dev" ]]; then
  exit 0
fi

case "$MODE" in
  staged)
    PATHS="$(git diff --cached --name-only --diff-filter=ACMR || true)"
    ;;
  worktree)
    PATHS="$(git diff --name-only --diff-filter=ACMR || true)"
    ;;
  head)
    PATHS="$(git ls-tree -r --name-only HEAD || true)"
    ;;
esac

if [[ -z "$PATHS" ]]; then
  exit 0
fi

VIOLATIONS="$(printf "%s\n" "$PATHS" | rg '^(docs/AGENT_SPECSLIST_DEV\.md|docs/demos/)' || true)"
if [[ -z "$VIOLATIONS" ]]; then
  exit 0
fi

echo "ERROR: dev-only specs docs detected on branch '$BRANCH'." >&2
echo "These paths are restricted to 'dev':" >&2
printf "%s\n" "$VIOLATIONS" >&2
echo >&2
echo "Fix options:" >&2
echo "  - move this work to branch 'dev', or" >&2
echo "  - remove these files from this branch/commit." >&2
exit 1
