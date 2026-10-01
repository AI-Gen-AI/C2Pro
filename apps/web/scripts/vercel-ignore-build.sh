#!/usr/bin/env bash
set -u

previous_sha="${VERCEL_GIT_PREVIOUS_SHA:-}"
current_sha="${VERCEL_GIT_COMMIT_SHA:-}"

# Vercel semantics: exit 0 = ignore/cancel build; exit 1 = build.
# If we cannot prove two resolvable commits exist, fail open to BUILD.
[[ -n "$previous_sha" && -n "$current_sha" ]] || exit 1
git cat-file -e "${previous_sha}^{commit}" 2>/dev/null || exit 1
git cat-file -e "${current_sha}^{commit}" 2>/dev/null || exit 1

git diff --quiet "$previous_sha" "$current_sha" -- \
  . \
  ../../package.json \
  ../../pnpm-lock.yaml \
  ../../pnpm-workspace.yaml \
  ../../.npmrc
