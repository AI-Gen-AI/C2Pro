---
paths:
  - "**/*.py"
  - "**/*.pyi"
---

# Python Security

> C2Pro-specific security contracts and executable tests override generic examples.

## Secrets

Read secrets from environment/approved secret stores. Never:

- commit credentials;
- log tokens/DSNs/passwords;
- copy production secrets into fixtures/examples;
- persist raw provider responses when bounded normalized evidence is sufficient.

Fail closed when required configuration is absent.

## C2Pro boundaries

Security review must consider, where relevant:

- tenant isolation/RLS;
- Clerk identity → tenant/org mapping;
- database function/role privilege boundaries;
- PII anonymization before external AI providers;
- exact approval/deployment identity binding;
- trusted-state commit semantics;
- safe retry/idempotency;
- filesystem/path containment;
- CI/supply-chain integrity.

## Scanning

Use the repository's current security tooling and workflows (for example gitleaks, CodeQL, dependency review/audit and targeted security tests) rather than assuming a generic scanner is a required gate.

Do not weaken a quality/security baseline merely to produce green status.
