# LF-01 — Langflow diagnostic lab (2026-11-20)

**Purpose:** Evaluate Langflow as an isolated visual aid for C2Pro's real N4-to-user diagnostic gap. C2Pro's LangGraph remains the orchestrator. **Not production; not an alternative inference engine.**

## What exists

- Version: Langflow **1.13.3** (pinned, image `docker.io/langflowai/langflow:1.13.3`).
- Host: existing AI-GEN VPS, dedicated unprivileged Linux user `lf01lab`, rootless Podman, port bound to **127.0.0.1:17860 only**.
- Credentials: local owner-only `/home/lf01lab/lf01-config/.env`, **never committed**; log in as `lf01lab`. Access via an SSH tunnel; do not expose the port to the internet.
- Persistence: `/home/lf01lab/lf01-data`; **no** C2Pro database mounts, production tokens, contract PDFs or Railway credentials.
- Controls: login required; custom components and Python interpreter disabled; local-file restriction enabled; `DO_NOT_TRACK=true`; external LangSmith tracing disabled; no model/provider API key.
- Source: `langflow_flow_builder.py` obtains *Langflow's own* Basic Prompting schema and creates two local flows with 12 nodes (two executable ChatInput/ChatOutput nodes + ten explanatory **notes**). **Notes are not executed graph nodes.** The single functional edge echoes the passed snapshot. This is NOT an execution of N1–N12.
- Cases: `REAL_OFFLINE_AGGREGATED` (prior SEC N4 recovery; redacted aggregates) and `SYNTHETIC_DESIGNED` (invented partial failure). They MUST remain visually distinct.
- C2Pro connection: offline aggregate snapshot only. The authenticated, owner-scoped GET in **draft** PR #1276 is not equivalent to an approved, deployed read-only integration. No Railway or production runtime connection was attempted.

## Actual C2Pro evidence and limitations

Read privately on the VPS (original artifacts **not exported**): `/home/aigenadmin/c2pro-recovery-evidence-20261117/private-output/n4_offline_audit_metrics.json`, `n4_t05_metrics_20261120.json`, and `n4_t05_packet_20261120.json`.

| Item | Observed |
|---|---|
| Historical N4 | `PARTIAL`; 142 candidate findings across 24 windows |
| N2 literals | 50 verified in N2 source, 92 unverified in N2 source (NOT original-PDF attestation) |
| Receipts | 24 distinct provider receipt identifiers in offline reconciliation |
| Historical window state | Cannot be reconstructed from current evidence |
| N12 | `NOT_STARTED` |
| HITL | 0 approved, 142 pending review; an offline packet is not an approved HITL review |
| ProjectGraph | `NOT_PROMOTED` |
| Coherence | No verified score change |
| User UI | Not verified from offline evidence |
| N3 and budget/schedule/spec cross-document correlations | Not verifiable in current offline evidence |

**Crucial:** real prior N4 execution and an actual Langflow snapshot-echo execution are two different events. No live contract analysis was run by LF-01. No claim that 142 candidates are accurate contractual risks.

## Verification

The runtime smoke test is `verify_lab.py`. It logs in to a **local** lab account, creates one lab-only API key when necessary (stored in `/home/lf01lab/lf01-config/.lf01_test_api_key`, chmod 0600), runs both flows through the official API, and records only HTTP/marker evidence; no credentials in stdout.

To inspect: `curl -I http://127.0.0.1:17860/` and `curl -I http://127.0.0.1:17860/api/v1/flows/` without authentication (should be forbidden). For the graphical editor, use local SSH forwarding `ssh -N -L 17860:127.0.0.1:17860 aigenadmin@<authorised-private-VPS-host>`; browse to `http://127.0.0.1:17860`. Never use public port forwarding.

To start on an authorized VPS: `sudo bash experiments/lf01/install_vps.sh`. It only installs Podman/uidmap and operates a dedicated `lf01lab` account; no Docker daemon, no C2Pro changes. Existing lab credentials must never be regenerated inadvertently.

## What LF-01 can and cannot prove

- **Can:** show the N4 discontinuity using existing summary evidence, reproduce a synthetic partial failure display, visibly isolate unverified N2 literals and downstream NOT_STARTED/NOT_PROMOTED markers, and compare approaches without inference spend.
- **Cannot:** find the root cause of real N4 or N12 model errors from summaries alone; replay a LangGraph run, inspect internal window-by-window causal traces, or verify prompt quality unless C2Pro exports an authenticated, sanitized observation event stream.
- **Recommended next diagnostic (separate change request, not authorized by LF-01):** a C2Pro read-only evidence adapter serving stable per-window state changes, trace IDs, source-reference verification status, and edge handoff receipts; no raw contract/prompt in remote tracers. Evaluate whether LangSmith/LangGraph Studio already provide equivalent observability before implementing an adapter.

## Comparison / decision

| Capability | Langflow lab | LangGraph Studio | LangSmith |
|---|---|---|---|
| Draw/design arbitrary visual flows | Strong | Graph from registered LangGraph | Trace tree, not flow editor |
| Native view of actual C2Pro LangGraph execution | **No** | Potentially yes with configured dev server | Yes *only* if properly instrumented |
| Trace which input/output was passed | Only for its **own** flow | Graph state/debugger | Run/span inputs/outputs (privacy-sensitive) |
| Cross-doc reason/cause evidence | Needs C2Pro adapter | Needs state instrumentation | Needs safe tags/metadata |
| Inference cost | Zero when simple echo | Not needed for replay | Potential telemetry/storage billing |
| Security | Isolated local port and owner account | Must isolate dev service | External transmission requires prior privacy review |

**Preliminary recommendation:** keep Langflow only as a **time-bounded sandbox**, not as a production integration or duplicated N4/N12. It adds explanatory display but so far cannot trace the true C2Pro execution. Do not introduce Langfuse unless a measurable diagnostic need remains unmet.
