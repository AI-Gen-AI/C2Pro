#!/usr/bin/env bash
set -u

branch="${VERCEL_GIT_COMMIT_REF:-}"
previous_sha="${VERCEL_GIT_PREVIOUS_SHA:-}"
current_sha="${VERCEL_GIT_COMMIT_SHA:-}"

# Vercel semantics:
#   exit 0 = ignore/cancel build
#   exit 1 = continue build
#
# Git deploymentEnabled in vercel.json is the primary branch gate. Keep the
# same policy here as defense in depth in case the project setting/config is
# evaluated differently during a Git-triggered deployment.
case "$branch" in
  "")
    # Manual/CLI or otherwise non-Git deployment: there is no branch to
    # classify, so preserve the operator-requested build.
    ;;
  main|hotfix/*|release-candidate/*|preview/*)
    ;;
  *)
    exit 0
    ;;
esac

# Build only when the web app or root dependency/workspace inputs changed.
# Prefer Vercel's last successful deployment SHA. When it is unavailable or
# not present in the clone, fall back to the current commit's first parent.
base_sha=""
if [[ -n "$previous_sha" && -n "$current_sha" ]] &&
   git cat-file -e "${previous_sha}^{commit}" 2>/dev/null &&
   git cat-file -e "${current_sha}^{commit}" 2>/dev/null; then
  base_sha="$previous_sha"
elif git rev-parse --verify HEAD^ >/dev/null 2>&1; then
  base_sha="$(git rev-parse HEAD^)"
  [[ -n "$current_sha" ]] || current_sha="$(git rev-parse HEAD)"
else
  # On an allowed release/preview branch, fail open only when there is no
  # trustworthy comparison base. This preserves production safety without
  # turning ordinary development branches into Vercel deployments.
  exit 1
fi

git diff --quiet "$base_sha" "$current_sha" -- \
  . \
  ../../package.json \
  ../../pnpm-lock.yaml \
  ../../pnpm-workspace.yaml \
  ../../.npmrc
