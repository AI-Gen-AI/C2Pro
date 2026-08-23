# C2Pro — Agentic Interoperability & Architecture Improvement Candidates

**Status:** REFERENCE / BACKLOG CANDIDATES — NON-CANONICAL  
**Date:** 2026-08-23  
**Repository reviewed:** `AI-Gen-AI/C2Pro`  
**Review baseline:** `main@08774f4897eaf3214b37de83f108b5d209efeca1`  
**Primary external inputs:** Perplexity framework/MCP/A2A report; Gemini agent-framework/MCP/A2A reports supplied by the owner.  
**Purpose:** preserve potentially valuable architecture improvements without changing current product priority, creating implementation authority, or introducing framework-driven scope creep.

> **Authority boundary**
>
> This document records observations and future candidates only. It does **not** amend an ADR, the canonical backlog, a release gate, an MCP security policy, production routing, model/provider authority, deployment authority, or the current product sequence.

---

## 1. Executive conclusion

The external reports contain useful architecture patterns, but their headline recommendation — combining several agent frameworks — is **not** the correct default for C2Pro.

C2Pro already has most of the capabilities these reports present as reasons to adopt additional frameworks:

- LangGraph as the real orchestration runtime;
- PostgreSQL-backed LangGraph checkpointing;
- FastAPI;
- extensive Pydantic contracts;
- LangChain/LangSmith integration;
- pgvector and hybrid retrieval;
- Supabase/PostgreSQL;
- Redis;
- evaluation datasets and domain-specific regression evidence;
- a security-oriented internal layer currently named MCP;
- strong tenant isolation, allowlists, query guards, rate limiting and audit logic.

Therefore the architectural problem is **not lack of frameworks**. The higher-value opportunities are:

1. clarify and standardize the C2Pro MCP boundary;
2. expose business capabilities rather than database primitives to agents;
3. version and conformance-test protocol integrations;
4. preserve a clean future interoperability boundary with AI-Gen and third-party agents;
5. benchmark new retrieval frameworks against C2Pro evidence before adoption;
6. prevent framework accumulation through an explicit adoption gate.

The current product pivot remains more important than any framework migration: **Single-Document Activation / Health-first value from document #1** remains the correct immediate direction.

---

## 2. Current architecture already covers much of the external recommendation

### 2.1 Orchestration

Current backend dependencies include:

- `langgraph==1.2.10`;
- `langgraph-checkpoint-postgres`;
- `langchain`;
- `langchain-core`;
- `langchain-anthropic`;
- `langsmith`.

The repository also contains:

- LangGraph checkpointing architecture documentation;
- checkpointer verification scripts;
- PostgreSQL/Supabase checkpoint migrations;
- LangGraph coherence subgraphs;
- decision-intelligence LangGraph adapters.

**Decision:** do not replace LangGraph merely because another framework benchmarks well in a third-party report.

### 2.2 Typed contracts

C2Pro already uses Pydantic v2 throughout the API and domain layers.

**Decision:** Pydantic AI is not a required migration. A future isolated use is justified only if it solves a measured problem that existing Pydantic + LangGraph contracts do not.

### 2.3 Retrieval

C2Pro already contains:

- pgvector;
- retrieval application/domain services;
- hybrid search/scoring tests;
- retrieval evaluation datasets;
- domain-specific golden/evaluation evidence.

**Decision:** LlamaIndex is a benchmark candidate, not an architectural default.

### 2.4 Security-oriented agent access

The repository already includes multiple MCP-labelled components:

- `apps/api/src/core/mcp/...`
- `apps/api/src/mcp/adapters/mcp_gateway.py`
- `mcp_query_guard.py`
- `mcp_rate_limiter.py`
- `mcp_audit.py`
- database allowlists and security tests.

This is valuable existing security logic and should be preserved.

---

## 3. Finding C2P-1 — clarify the meaning of “MCP”

### 3.1 Observed ambiguity

C2Pro currently uses the acronym **MCP** in at least two overlapping ways:

1. documentation and API tags describe an **MCP Server — Model Context Protocol**;
2. `MCPGateway` is documented as **Master Control Program (MCP)**;
3. the exposed interface is primarily C2Pro-specific REST endpoints such as:
   - `/api/v1/mcp/query-view`
   - `/api/v1/mcp/call-function`
   - `/api/v1/mcp/views`
   - `/api/v1/mcp/functions`

The internal security design is useful, but naming it as if it were automatically equivalent to a specific Model Context Protocol wire contract risks future ambiguity.

### 3.2 Proposed future action

Perform a bounded **MCP Semantic & Conformance Audit**:

```text
C2Pro internal capability/security plane
    ├─ tenant isolation
    ├─ allowlists
    ├─ query guard
    ├─ rate limiting
    └─ audit
             │
             ▼
optional standard MCP adapter
    ├─ explicit MCP spec version
    ├─ protocol conformance tests
    ├─ compatibility matrix
    └─ business-level tools
```

### 3.3 Important constraint

Do **not** rewrite the secure internal layer merely to obtain protocol purity.

Preferred pattern:

**preserve domain/security logic → add a standards adapter at the boundary.**

---

## 4. Finding C2P-2 — expose business capabilities, not storage primitives

A future agent-facing C2Pro interface should not primarily give an LLM generic database operations such as “query view X” or “call function Y”.

The safer and more product-aligned surface is a small set of domain capabilities.

### Candidate read-only tools

```text
get_project_health
get_document_category_coverage
list_gap_alerts
get_finding_evidence
get_project_risks
get_document_requirements
get_coherence_status
get_coherence_subscore
```

`get_coherence_subscore` must preserve the current product invariant: relational coherence is meaningful only when sufficient reconcilable evidence exists.

### Why this is better

A business-capability surface:

- reduces tool-selection ambiguity;
- reduces prompt exposure to storage internals;
- keeps schema/storage changes behind the application layer;
- improves audit semantics;
- makes authorization easier to reason about;
- creates a stable integration contract for AI-Gen;
- aligns agent actions with C2Pro product concepts rather than database layout.

### Initial authority

If implemented, start **READ-ONLY**.

Mutation tools must be separately designed and gated. A tool being representable through MCP must never imply that an AI agent is authorized to execute a consequential business mutation.

---

## 5. Finding C2P-3 — introduce MCP version and conformance governance

The MCP specification changed materially in the `2026-07-28` revision. Among the published changes are:

- stateless protocol core;
- removal of the legacy `initialize` / `initialized` handshake for the new revision;
- removal of protocol-level `Mcp-Session-Id`;
- `server/discover`;
- self-describing requests;
- `Mcp-Method` / `Mcp-Name` routing headers for Streamable HTTP;
- redesigned multi-round-trip interactions;
- cacheable deterministic list results;
- authorization hardening;
- formal deprecation policy.

### Proposed rule

Any future standards-compliant MCP adapter should declare:

```text
protocol_name
protocol_version
supported_transports
supported_capabilities
authentication_mode
authorization_policy_ref
tool_catalog_version
client_compatibility_matrix
conformance_test_evidence
security_negative_test_evidence
deprecation/migration plan
```

### Principle

Treat MCP as a **versioned public contract**, not as a generic feature label.

---

## 6. Finding C2P-4 — future C2Pro capability boundary for AI-Gen

A strategically useful medium-term pattern is:

```text
AI-Gen
  │
  ▼
C2Pro Specialist
  │
  ▼
C2Pro read-only capability adapter
  │
  ├─ Health
  ├─ Coverage / Missing Data
  ├─ Findings
  ├─ Evidence
  ├─ Risks
  └─ Relational Coherence when valid
  │
  ▼
C2Pro application/domain layer
  │
  ▼
LangGraph + PostgreSQL/Supabase + pgvector
```

This keeps:

- AI-Gen as the higher-level intelligence OS;
- C2Pro as the authoritative professional/product vertical;
- C2Pro storage and internal orchestration private;
- cross-system use explicit and auditable.

### Non-goal

AI-Gen must not gain database authority merely because C2Pro is one of its professional verticals.

---

## 7. Finding C2P-5 — retrieval framework adoption must be benchmark-driven

The external reports recommend LlamaIndex strongly and cite benchmark figures such as RAGAS scores, throughput and token overhead.

Those figures are useful as **hypothesis generators**, but they are not a sufficient basis for migration because they depend on:

- model/version;
- prompts;
- corpus;
- chunking;
- hardware;
- provider;
- caching;
- retriever configuration;
- reranking;
- evaluation definition;
- network;
- framework version.

### Proposed bounded spike — only when retrieval becomes a measured bottleneck

Compare:

```text
CURRENT C2PRO RETRIEVAL
vs
LLAMAINDEX REFERENCE SPIKE
```

on the same C2Pro corpus and tasks.

Minimum measures:

- recall;
- precision;
- evidence/citation fidelity;
- false-positive rate;
- false-negative rate;
- latency;
- token consumption;
- cost;
- operational complexity;
- deterministic failure behavior;
- tenant/data-isolation implications.

### Adoption rule

No migration unless the candidate provides a **material, repeatable improvement** on C2Pro's own workloads.

---

## 8. Finding C2P-6 — A2A is a future external boundary, not an internal orchestration requirement

A2A v1.0 is intended for communication among independent agents and is complementary to MCP.

It should **not** be introduced merely because C2Pro has multiple agentic components.

### Do not use A2A for

```text
LangGraph node -> LangGraph node
internal planner -> internal reviewer
internal specialist -> internal tool
```

Use native orchestration or MCP/tool contracts where appropriate.

### Potential future use

A2A becomes relevant if C2Pro genuinely interoperates with independently operated systems, for example:

```text
C2Pro <-> customer's procurement agent
C2Pro <-> supplier agent
C2Pro <-> SAP/enterprise agent service
C2Pro <-> externally operated AI-Gen service
```

### Trigger for adoption

Require evidence of a real boundary with independent:

- owner;
- lifecycle;
- trust domain;
- deployment;
- authentication;
- service contract.

Until then: **DEFERRED**.

---

## 9. Finding C2P-7 — framework/protocol adoption gate

Before introducing a new framework, protocol layer or managed agent platform, require an explicit answer to:

```text
1. What measurable problem exists?
2. Can the current architecture solve it?
3. What bounded experiment proves the gap?
4. What is the quality delta?
5. What is the latency/cost delta?
6. What new security authority is introduced?
7. What new operational dependency is introduced?
8. What is the lock-in impact?
9. How is rollback performed?
10. What evidence is required for adoption?
```

Decision rule:

```text
no measured problem        -> reject/defer
no measurable improvement  -> reject/defer
higher authority without value -> reject
clear evidence + bounded benefit -> architecture decision gate
```

This prevents architecture by accumulation.

---

## 10. Framework decisions recorded from the external review

| Technology | Current recommendation | Reason |
|---|---|---|
| LangGraph | **KEEP** | Already production architecture; state/checkpointing/flows exist |
| LangChain/LangSmith | **KEEP where currently justified** | Already integrated |
| Pydantic | **KEEP** | Core typed contract layer |
| Pydantic AI | **DO NOT ADOPT NOW** | No measured gap requiring another agent runtime |
| LlamaIndex | **BENCHMARK CANDIDATE ONLY** | Retrieval already exists; require own-corpus evidence |
| CrewAI | **DO NOT ADOPT NOW** | Adds another orchestration abstraction without clear need |
| smolagents | **DO NOT ADOPT NOW** | No current use case outweighs sandbox/governance cost |
| Google ADK | **DO NOT ADOPT NOW** | No GCP control-plane requirement |
| OpenAI Agents SDK | **CASE-SPECIFIC ONLY** | Provider SDK, not replacement for current C2Pro architecture |
| A2A | **DEFERRED** | Only for real independent agent boundaries |
| MCP standard adapter | **HIGH-VALUE FUTURE CANDIDATE** | Interoperability without exposing internal storage/architecture |

---

## 11. Relationship to ADR-024 — do not disturb current product priority

The recent Single-Document Activation decision remains the more important near-term product work.

Current product model:

```text
one document
   ↓
six-category decomposition
   ↓
state + findings + missing_data
   ↓
actionable gap alerts
   ↓
additional evidence requested
   ↓
relational coherence when evidence is sufficient
```

The interoperability ideas in this report should expose or support that model; they must **not** displace it.

A framework migration that delays first-document value is negative value.

---

## 12. Proposed future backlog candidates

These labels are intentionally **non-canonical**. They must not be interpreted as approved TASK IDs.

| Candidate | Priority | Trigger | Exit evidence |
|---|---:|---|---|
| MCP Semantic & Naming Audit | High | after current P0 product stabilization | clear internal-vs-standard boundary and no naming ambiguity |
| Standard MCP Read-Only Capability Adapter | High/Medium | real AI-Gen/external consumer need | conformance + auth + tenant isolation + negative tests |
| MCP Version Compatibility Matrix | High if adapter exists | before exposing standard MCP | exact supported versions/transports/clients documented and tested |
| Business Tool Contract v1 | High/Medium | before any external agent access | narrow typed read-only tools with evidence semantics |
| Retrieval Framework Benchmark | Medium/Deferred | measured retrieval limitation | own-corpus comparative evidence |
| A2A Readiness ADR | Low/Deferred | first independent external agent boundary | trust/auth/task lifecycle/rollback model |
| Technology Adoption Gate | Medium | next architecture governance refresh | documented mandatory decision checklist |

---

## 13. Risks to avoid

1. **Framework tax by accumulation**  
   Multiple runtimes create debugging, versioning and observability costs.

2. **Protocol-name ambiguity**  
   Calling a REST security layer “Model Context Protocol” without conformance semantics can confuse future maintainers.

3. **Database-shaped agent tools**  
   Exposing storage primitives produces brittle and overly powerful tool surfaces.

4. **Mutation creep**  
   Read capability must not silently evolve into write/action authority.

5. **Benchmark cargo culting**  
   External benchmark winners may lose on C2Pro's EPC/procurement corpus.

6. **A2A premature complexity**  
   A2A adds a distributed-system boundary; do not use it to solve an in-process design problem.

---

## 14. Suggested repository location

Recommended future path if the owner chooses to version this report:

`docs/planning/AGENTIC_INTEROPERABILITY_IMPROVEMENT_CANDIDATES_2026-08-23.md`

Alternative if C2Pro later creates a dedicated architecture-review area:

`docs/architecture/reviews/agentic-interoperability-improvement-candidates-2026-08-23.md`

This report should remain **reference material** until individual candidates are promoted through the normal C2Pro architecture/backlog process.

---

## 15. Evidence anchors

Repository evidence reviewed:

- `apps/api/requirements.txt`
- `docs/architecture/LANGGRAPH_CHECKPOINTING.md`
- `docs/coherence_engine/coherence_langgraph_subgraph_v3.md`
- `apps/api/src/modules/decision_intelligence/adapters/langgraph/`
- `apps/api/src/modules/retrieval/`
- `infrastructure/evaluation/datasets/retrieval/`
- `apps/api/src/core/mcp/`
- `apps/api/src/mcp/adapters/`
- `docs/architecture/decisions/ADR-024-single-document-activation.md`
- current `main` commit `08774f4897eaf3214b37de83f108b5d209efeca1`

External evidence to revalidate when implementation is contemplated:

- MCP specification/release `2026-07-28`;
- A2A v1.0 specification and implementation guidance;
- any framework benchmark cited by Perplexity/Gemini.

---

## 16. Final decision record

**Keep the current architecture.**  
**Do not introduce a framework stack for its own sake.**  
**Preserve C2Pro's domain, evidence and security boundaries.**  
**Standardize interoperability through adapters when a real consumer exists.**  
**Benchmark before replacing retrieval.**  
**Keep A2A deferred until there is a true independent-agent boundary.**  
**Do not let this report change ADR-024/P0 priority or grant implementation authority.**
