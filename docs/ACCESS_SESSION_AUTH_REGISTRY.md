# C2Pro — Access, Session & Authentication Companion

**Status:** Current governance companion  
**Version:** 1.0.0  
**Created:** 2026-09-16  
**Scope:** Public C2Pro repository  

> This is the **sanitized C2Pro companion** to the internal AI-Gen operational access/session/authentication registry. It intentionally excludes internal account details, credential metadata, provider scopes, private filesystem topology and secret-adjacent operational data.

---

## 1. Purpose

This document defines the product-safe operational invariants that every C2Pro development, review, recovery and release session must respect.

It does **not** contain credentials and it does **not** grant authorization.

The internal cross-project source of truth is maintained by AI-Gen Agent OS. This public companion exists so C2Pro contributors and automation can understand the required boundaries without exposing internal security state.

---

## 2. Core invariant

```text
documented capability != policy permission != current authorization
```

A tool, user, session or agent being technically capable of performing an action does not authorize that action.

Before any mutation, the effective identity, target, repository state, authentication mode and applicable approval gate must all be established independently.

---

## 3. Separation of roles

C2Pro operations SHOULD preserve these conceptual roles even when implementations evolve:

| Role | Responsibility | Default posture |
|---|---|---|
| Custodian / administrator | Holds or authorizes privileged provider access | Human-controlled; not a generic worker |
| Code worker | Performs bounded repository work | Least privilege; task-scoped |
| Independent reviewer | Reviews evidence/diffs independently | Read-only by default |
| Merger / release authority | Accepts and integrates approved work | Separate explicit gate |
| Runtime / deployment principal | Operates product infrastructure | Separate from developer/reviewer identity |

A role change must be explicit. Reviewer identity must not silently become author/worker identity.

---

## 4. Session boundary

Every privileged or long-running C2Pro session must be able to establish, at minimum:

- effective execution identity;
- effective HOME/runtime domain;
- current working directory;
- repository/worktree;
- branch/ref;
- mutation scope;
- provider authentication state;
- human-approval requirement;
- last live verification.

HOME and CWD are both part of the execution boundary. A valid credential under one identity does not make an inherited working directory under another identity safe or valid.

---

## 5. Repository/worktree ownership

Repository and worktree actions must execute under an identity that can legitimately traverse and operate on the target worktree.

Do not solve an identity-boundary failure by broadly weakening filesystem permissions or changing ownership unless that change is itself designed, reviewed and explicitly authorized.

Preferred response to a boundary mismatch:

1. classify the effective identity;
2. classify worktree ownership/access;
3. run the operation under the correct identity or use a bounded evidence-transfer pattern;
4. preserve least privilege.

---

## 6. Authentication classes

### 6.1 Persistent authentication

Reusable provider/session authentication intentionally stored under an approved identity/runtime domain.

It requires explicit ownership, least-privilege review, protected storage and a known revoke/rotate path.

### 6.2 Ephemeral delegation

A credential or authorization capability is made available only for one bounded operation and then removed.

Any ephemeral delegation must satisfy all of the following:

- explicit authorization;
- known source/custodian;
- known target identity;
- frozen destination/action;
- no secret printed or logged;
- no persistence in Git config, remote URL, shell profile, evidence file or repository;
- post-action verification;
- credential cleared immediately after use;
- persistent safety barriers remain unchanged unless their modification was separately approved.

### 6.3 Session-only authentication

Interactive authentication valid only in a current process/session. It is not portable authority and must not be assumed valid in sibling identities or later sessions.

---

## 7. Git mutation boundary

C2Pro may use persistent barriers that deliberately allow read/fetch while blocking default push/write paths.

Such a barrier is a security control, not a defect.

A controlled push must be fail-closed and SHOULD establish:

- exact local commit/ref;
- clean/frozen local state;
- remote base/CAS state;
- destination branch/ref;
- lease/precondition semantics;
- one bounded push attempt where specified;
- explicit authentication source;
- post-push remote SHA verification;
- unchanged/restored persistent push barrier.

No script may silently remove a persistent push barrier merely because valid credentials are available.

---

## 8. Independent review boundary

Independent reviewers SHOULD receive the minimum evidence needed to review the change.

Where filesystem or identity separation prevents direct access, use a bounded evidence-transfer workspace rather than broad cross-HOME access.

Review evidence should bind, where applicable:

- base/ref;
- exact diff or content hash;
- test/qualification evidence;
- review prompt/contract;
- exact reviewer response;
- immutable verdict gate.

A reviewer `PASS` only satisfies the review gate defined for that task. It does not independently authorize commit, push, PR, merge, deployment or Sonar mutation.

---

## 9. Product authorization boundary

This operational companion does not supersede product/runtime authorization specifications.

For platform-operator and cross-tenant capability rules, the canonical C2Pro specification remains:

`docs/C2_6_PLATFORM_OPERATOR_AUTHORIZATION_BOUNDARY.md`

Runtime principal authorization, database capability enablement and developer/provider authentication are separate security domains and must not be conflated.

---

## 10. Secret-handling invariant

Never commit or persist:

- passwords;
- access/refresh tokens;
- private keys;
- service-account material;
- OAuth authorization URLs containing transient challenges;
- session cookies;
- recovery codes;
- bearer headers;
- secret `.env` values.

Operational documentation may record credential **type**, **owner role**, **persistence class**, **status** and **verification method**, but not the secret itself.

---

## 11. Safe preflight

Before a privileged repository operation, a session SHOULD establish equivalent evidence to:

```bash
whoami
printf 'HOME=%s\nPWD=%s\n' "$HOME" "$PWD"
git rev-parse --show-toplevel 2>/dev/null || true
git branch --show-current 2>/dev/null || true
git status --short 2>/dev/null || true
git config --show-origin --get-all remote.origin.pushurl 2>/dev/null || true
git remote get-url origin 2>/dev/null || true
```

Provider authentication should be verified with status/account metadata commands that do not print secret values.

---

## 12. Fail-closed conditions

Stop the mutation and classify the gap when any of these is unknown or inconsistent:

- effective identity;
- target worktree/repository;
- branch/ref;
- expected local state;
- expected remote state;
- authorization for the intended mutation;
- authentication source;
- reviewer verdict where required;
- provider mutation boundary;
- post-action verification method.

`UNKNOWN` is a valid state. Guessing is not.

---

## 13. Drift triggers

Reverify and update the internal AI-Gen registry when:

- execution identities change;
- HOME/CWD/worktree ownership changes;
- authentication mechanism changes;
- credentials rotate or are revoked;
- provider scopes change;
- Git push/mutation barriers change;
- a new external provider is introduced;
- an agent gains or loses write capability;
- a security incident exposes an undocumented boundary.

This public companion should change only when the **product-safe invariant or operating contract** changes, not for every credential/session rotation.

---

## 14. Cross-project governance

AI-Gen Agent OS owns the detailed internal registry of operational identities, credential classes and session capabilities. C2Pro owns product-local authorization, repository and release gates.

Cross-project execution must preserve:

- least privilege;
- separation of worker/reviewer/merger responsibilities;
- explicit HITL for high-risk actions;
- product-specific authorization boundaries;
- fail-closed mutation gates;
- no secret replication between repositories.
