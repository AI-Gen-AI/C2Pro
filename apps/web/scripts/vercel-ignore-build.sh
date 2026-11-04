#!/usr/bin/env bash
set -u

branch="${VERCEL_GIT_COMMIT_REF:-}"
previous_sha="${VERCEL_GIT_PREVIOUS_SHA:-}"
current_sha="${VERCEL_GIT_COMMIT_SHA:-}"

# Vercel semantics:
#   exit 0 = ignore/cancel build
#   exit 1 = continue build
#
# Scope this pilot exception to the NEW Vercel project only. The existing
# v0-c2-pro project must continue to ignore this feature branch.
if [[ "$branch" == "feat/projectgraph-functional-20261104" ]]; then
  if [[ "${VERCEL_PROJECT_ID:-}" == "prj_z11Gj70PWALqxN0EKOIWPVmQNWW3" ]] || \
     [[ "${VERCEL_URL:-}" == c2pro-projectgraph-pilot-*.vercel.app ]] || \
     [[ "${VERCEL_PROJECT_PRODUCTION_URL:-}" == c2pro-projectgraph-pilot-*.vercel.app ]]; then
    exit 1
  fi
  exit 0
fi
# Git deploymentEnabled in vercel.json is the primary branch gate. Keep the
# same policy here as defense in depth in case the project setting/config is
# evaluated differently during a Git-triggered deployment.
case "$branch" in
  "")
    # Manual/CLI or otherwise non-Git deployment: there is no branch to
    # classify, so preserve the operator-requested build.
    ;;
  main|integration/acc01-e2e-20261025|hotfix/*|release-candidate/*|preview/*)
    ;;
  *)
    exit 0
    ;;
esac

# The owner-approved integration branch is the current C2Pro pilot release.
# A manual production deployment must not be skipped simply because Vercel
# already built this same commit in Preview. Apply this override ONLY to the
# explicitly authorized branch, not to other development branches.
if [[ "$branch" == "integration/acc01-e2e-20261025" && "${VERCEL_ENV:-}" == "production" ]]; then
  exit 1
fi

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
