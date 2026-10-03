# GitHub Actions storage governance v1

**Repository:** AI-Gen-AI/C2Pro
**Status:** active
**Date:** 2026-10-03

## Objective

Keep C2Pro within the included GitHub Actions storage allowances without weakening CI coverage.

C2Pro is a public repository. Standard GitHub-hosted runners are therefore the canonical execution target: their minutes are free for public repositories and they avoid exposing the persistent AI-Gen VPS to public-repository workflow execution. Larger GitHub-hosted runners and self-hosted runners are not admitted by default.

## Storage policy

- repository artifact/log retention target: 7 days;
- every `actions/upload-artifact` step must declare `retention-days` between 1 and 7;
- no workflow may silently fall back to GitHub's 90-day artifact default;
- standard GitHub-hosted runner labels only;
- no larger runner or self-hosted runner without an explicit governance change;
- cache storage remains at the default 10 GiB repository ceiling and is allowed to use GitHub's normal LRU/stale-cache eviction.

## Baseline observed on 2026-10-03

- 11,453 artifacts;
- approximately 1.314 GiB of artifact storage;
- approximately 10 GiB of active Actions cache storage;
- repository artifact/log retention configured at 90 days;
- all active workflow jobs observed on standard `ubuntu-latest` runners;
- no repository self-hosted runners registered.

Historical artifact cleanup is intentionally limited to regenerable CI evidence older than the policy window. Release deliverables that require durable distribution belong in GitHub Releases or another durable release store, not transient Actions artifacts.

## Regression control

`scripts/development/validate_github_actions_storage_policy.py` and its development test fail if a workflow:

- introduces a non-standard, larger, or self-hosted runner;
- uploads an artifact without an explicit retention period;
- sets artifact retention above 7 days;
- introduces an unreviewed reusable workflow job.

The lightweight development-control workflow watches `.github/workflows/**`, so storage-policy regressions are checked whenever workflow definitions change.
