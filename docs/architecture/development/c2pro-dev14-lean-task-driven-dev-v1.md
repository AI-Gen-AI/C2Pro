# C2Pro DEV-14 — Lightweight Task-Driven / SDD / TDD

**Scope:** C2Pro only. **Owner authorization:** 2026-10-09 (#991).
**Execution:** owner-supervised coding in a dedicated branch, with CI and a human merge. This decision does not claim that the optional Agent Factory .c2pro queue is active.

## Minimum development loop

1. Use the existing Product MASTER Task or canonical C2PRO-DEV Task and state observable acceptance; reuse existing parent GitHub issues.
2. Write a short SDD only if needed; Product subtasks are already in docs/product/pq-hitl-2026-01-delivery-spec-v1.md.
3. Add a failing test first, implement narrowly and prove GREEN in a separate worktree.
4. Open a Task-linked PR, obtain exact-head CI and independent review, then human merge. PR MERGED does not mean Product ACCEPTED or PROD_VALIDATED.

The approved C2Pro direct-development mode does **not** require creating a new AI-GEN Agent Factory qualification programme. AF-DEV remains an optional separate architecture, not a mandatory prerequisite for owner-supervised C2Pro code work. We do not modify current.yaml active_work, claim worker receipts, bypass security gates, or grant production credentials.

## Delivered in DEV-14

- DEV-14.2: Product Task parent and 28 atomic packages resolved from existing Product MASTER and its canonical delivery specification. Optional Product WORK receipts have a distinct schema in .c2pro/product-work/; a prepared receipt is not an assigned receipt.
- DEV-14.3: strict single-block YAML trace, duplicate-key/unknown-ID/wrong-parent validation, per-Task claims for multi-Task PRs and changed-path checks. Authority is resolved from the **pre-PR base**, not self-authorized from head changes.
- DEV-14.4: a read-only Action runs on all PRs in AUDIT mode first. Missing/invalid trace metadata is diagnostic, not a hard failure. No release, Product acceptance or permission mutation.

## Adoption

Place a single fenced YAML block with a c2pro_trace mapping in the PR description. For a new document-only task, specify effect_claim SPEC_ONLY; the trace must reference a canonical Task, its parent issue and SDD. For owner-supervised implementation use execution_mode OWNER_SUPERVISED, canonical acceptance IDs and human PR review; this is Task mapping only, not a WORK receipt. For autonomous AGENT_WORK, genuine assigned WORK remains obligatory. The audit does not fabricate either.

ENFORCE requires a later explicit approval and verified coverage of Product WORK assignment, workspace receipts and acceptance registry. Until then, the workflow remains AUDIT and existing CI/security checks retain their authority.
