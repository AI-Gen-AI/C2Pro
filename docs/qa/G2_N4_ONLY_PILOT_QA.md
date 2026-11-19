# G2: Governed N4-only pilot (DRAFT, NOT DEPLOYED)

Base SHA: 799ce5315c01cdf6ec83f5716a02a509a6be1785 (PR #1270).

The old reprocess path automatically follows N4 to N12. No safe N4-only REST path existed at the base SHA. This candidate introduces a separate default-OFF endpoint scoped to one authorized owner, tenant, project, PDF R1, source SHA, prior generation and fence in Railway pilot. No user/global toggle.

The pilot uses the existing transactionally budgeted N4 runner. Workflow topology: N1 then N2 then governed N4 then END. No N12, HITL, Score, Trust, N17 or automatic approval. An exact 23-window N2 plan is checked before any reservation. Any billable SETTLED/RESERVED/UNKNOWN receipt in a prior generation for the same source blocks a new call. No silent replay billing.

The POST requires source/revision/status and CAS checks, starts a new generation via official repository method and queues the existing parser followed by a distinct N4-only task. Generic reprocess rejects pilot marker. Generic recovery skips it (must not accidentally start full N12). Zero auto retry on unknown usage.

After successful persistence, result is PROPOSED_N12_UNASSESSED or NO_FINDINGS_UNASSESSED; incomplete is PARTIAL_UNASSESSED. Document is never advertised as fully ANALYZED. Owner-only GET surfaces source-backed PROPOSED findings, revision, run, N2 span, and VERIFIED_IN_N2 / ORIGINAL_PDF_UNVERIFIED distinction. It does not create HITL or mark PDF verified.

## Before any separate CORE monetary GO (NOT authorized here)
- Review exact SHA and independent E QA of new endpoints, owner access, route and fail-closed identity.
- Verify 23/23 and receipt settlement in ephemeral PG with concurrent workers/replay/crash; no N12 invocations.
- Verify source bytes and N2 SHA/revision, 23 planned windows, current fenced authority, no stale leases.
- Verify budget TENANT USD 5, global UNKNOWN, dedup cross-generation, input/output pricing.
- Prove normal documents still run N4 to N12, while pilot never runs N12/HITL/Score.
- Verify output query authorizes owner only and any quote is matched to N2, with separate human review against PDF original.
- Provision an expiring server-only approved scope only in an explicitly authorized UAT deployment, never commit owner IDs, secrets or populated scope.
- Scope expiration also disables owner GET: plan a separately authorized read mechanism if human QA is delayed.
- Do not perform UAT SQL writes, reprocess, paid inference, reservations or deployment before CORE authorization.

## QA states
DRAFT code prepared for independent E audit; focal tests do not replace the full E QA nor browser UAT. No production change.

## P1 — historical read-only QA, partial evidence (#7002874201)
- The **POST/worker** still use the expiring execution policy and reject PARTIAL_UNASSESSED; expired grants cannot queue, reserve or restart any provider.
- The **GET** now invokes a separate, owner-only READ policy that permits PARTIAL_UNASSESSED and ignores execution expiration only for retrieval. The exact server-side UAT scope and persisted digest/owner/tenant/doc/R1/N2 SHA/generation must match; removing the server-side scope revokes read access.
- The GET requires current pinned parsed-text revision; its SELECT joins the current processing authority with equality on generation/revision/fencing, requires source SHA and an active document revision, and refuses stale/missing runs. No DML, retry, task dispatch, N12, HITL or trust promotion.
- Response includes truthful PARTIAL_UNASSESSED and original ledger status separately; existing PROPOSED findings, N2 analysis spans and quotes are read with tenant/run-scoped pagination. N2 citation verification never establishes original PDF page verification.
- Focused permanent suite: tests/unit/analysis/test_g2_n4_partial_read_p1.py, including expiry-read/POST-denial, GET 200, paginated PROPOSED quotes, foreign owner/tenant/project, stale revision/generation/fence and marker forgery. Independent E should also exercise real SQL against ephemeral PG before PASS.
