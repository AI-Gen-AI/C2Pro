# Release Signoff Policy

**Version:** 2.0  
**Effective Date:** 2026-10-01  
**Status:** Current policy

## Governance

This policy defines release evidence and approval requirements. It does not own task status.

- open release work → `.c2pro/control/` + work envelopes;
- product lifecycle/qualification → Product Control;
- exact technical evidence → GitHub checks/artifacts + bounded release evidence;
- legacy backlog references → historical/cold only.

See `docs/RELEASE_CRITERIA.md` for the current workflow/evidence map.

## Signoff invariant

A signoff applies only to the exact release identity it names:

- commit SHA;
- environment;
- backend/frontend deployment identities where applicable;
- required workflow/check evidence;
- Product Control state;
- manual approvers.

Evidence from a different SHA/environment cannot be substituted.

## Minimum release record

```yaml
release_id: <release-id>
commit_sha: <40-char-sha>
environment: <staging|production>
required_checks: []
deployment_identity: {}
product_control_ref: <ref>
manual_signoff:
  product: <pending|approved|not-required>
  security: <pending|approved|not-required>
  operations: <pending|approved|not-required>
waivers: []
```

## Decision rules

- Required ruleset checks must pass.
- Applicable security/secret/dependency gates must have no unresolved blocking result.
- Required production qualification must pass for the exact observed deployment identities.
- Open Product Control gates remain open until reconciled by their owner.
- Manual signoff cannot convert missing technical evidence into a pass.
- Waivers are explicit residual-risk acceptances; they do not rewrite the underlying result.

## Evidence hygiene

Do not persist credentials, DSNs, tokens or unrestricted provider payloads in a release bundle. Prefer normalized identifiers, hashes and check outcomes.

## Historical policy

The pre-2026-10-01 workflow names/coverage thresholds previously listed here are retained in Git history. They are not current release authority because the CI topology has changed.
