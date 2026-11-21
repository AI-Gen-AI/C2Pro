# LF02 — C2Pro LangGraph Studio (independent development environment)

## Provenance & separation
- Branch: `experiment/lf02-langgraph-studio-20261121`, derived from `main@299aaf19f5025a2162c6a2c626542f6dd472c3c6`. Changes here **do not affect main** until explicitly merged and deployed.
- C2Pro graphs are **real original code**, imported through `src.analysis.adapters.graph.workflow.compile_workflow` and `src.analysis.adapters.graph.project_graph.build_project_graph`; none of the original node functions are reimplemented.
- `c2pro_n4_g2_diagnostic` is a **separate experiment** using two **byte-identical** domain modules from G2 head `916808c5` (not yet merged to the starting main):
  - `src/analysis/domain/n4_source_windows.py` SHA256 `4a42e916c48aa9a091c4618504bca3ff1c467d0f5bf5bfcfad9affa89fff17df`
  - `src/analysis/domain/n4_compact_window_response.py` SHA256 `ac5b8269b99c47d43cb4ca734187004fe899cf9fdeaa0d347ee97dc6d1be5d91`

## Infrastructure
- VPS worktree: `/home/aigenadmin/qa_workspaces/c2pro-langgraph-studio-20261121`
- Agent Server: `lf02-studio.service` private `http://127.0.0.1:17941`; autostarts with systemd
- Lab PostgreSQL: `lf02-postgresql.service` private `127.0.0.1:55433`, database `lf02`. This is for **C2Pro SQL** and has no connection to production.
- Agent Server `langgraph dev` itself persists threads/checkpoints to a private local dev store, **not** this PostgreSQL instance.
- Python 3.12 and isolated `.venv`; `langgraph-cli[inmem]==0.4.43`, `langgraph-api==0.18.4`.
- Service uses **only** `ENVIRONMENT=test`, isolated DSN, `C2PRO_AI_MOCK=1` for original full graph, no production API keys, `LANGSMITH_TRACING=false`, `LANGCHAIN_TRACING_V2=false`.
- The CLI local server currently has no API authentication. **Do not expose it directly on 0.0.0.0 or through a public tunnel.** It only listens to loopback.

## Studio access
From an SSH-authorized workstation, establish a **private tunnel** to VPS:
```powershell
ssh -N -L 17941:127.0.0.1:17941 aigenadmin@100.74.108.93
```
The IP above is the VPS's observed Tailscale address and requires your own authorized Tailscale/SSH access. Then open:
`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:17941`.
LangSmith Studio is a web client. Do not paste sensitive real contracts until you have separately validated browser/service data transmission and privacy.

## Graphs and capabilities
- `c2pro_main`: 19 LangGraph nodes (including START/END), 27 edges from production source version, no duplicate logic. Runs against *test* settings.
- `c2pro_project_graph`: 11 nodes (including START/END), 10 edges, real implementation; *not yet validated end-to-end against migrated lab SQL*.
- `c2pro_n4_g2_diagnostic`: 5 nodes (including START/END), real G2 source-window planning and original response parser, with optional **local Ollama** inference (`use_local_model`) or exact input replay. Model, system prompt, temperature, max output tokens, max context chars, overlap are exposed as Studio Assistant context.
- Two test Assistants exist: `LF02 N4 Estricto` and `LF02 N4 Contraste`; source configurations in `assistant_presets.json`.
- Manual changes in Studio affect the specific test thread/checkpoints or the selected assistant's versioned configuration; they **do not** rewrite Python or merge to main.

## Evidence (2026-11-21)
- `/ok`, `/docs`, `/openapi.json`, `/assistants/search`: HTTP 200.
- API graph endpoint: 19 / 11 / 5 exact node counts.
- Synthetic state edit on a `c2pro_main` thread persisted and survived a systemd restart.
- **Actual C2Pro main graph** synthetic run with pause before N4: N1 `ok`, N2 `ok`, N3 `ok`; state next `risk_extractor`; N3 received pre-selected doc_type `contract` (this did not validate autonomous LLM classification).
- **G2 N4 diagnostic** replay through real domain planner and parser: one synthetic cited candidate, `EXAMINED_WINDOW_ONLY`, five checkpoints. This is a test of parsing and persistence, not LLM recall.
- Separate local Ollama N4 call submitted; mark it PASS **only when terminal state and evidence confirm it**.
- No full-document N4 semantic recall, N12 critique, HITL approvals, full ProjectGraph SQL integration, original-PDF citation authenticity or E2E journey has been certified.
- No provider API spending, no production database modifications, no main changes.

## Operations
```bash
systemctl status lf02-studio lf02-postgresql
journalctl -u lf02-studio -n 100 --no-pager
curl -fsS http://127.0.0.1:17941/ok
```
Deploy/test changes only from this experimental branch; review and merge to main in a separate controlled process.

## Final lab status (2026-11-21)
See `EVIDENCE_2026-11-21.md` for independently inspectable checks and blockers.
The lab SQL schema has been migrated through `20261022_0001` (63 tables), N1–N3 ran,
ProjectGraph's first two nodes ran, state editing/time-travel rerouted N3 to a different
real node, and exact N4 G2 parser replay passed. The local Qwen N4 provider call timed
out and remains **BLOCKED**, not a successful model-based extraction.
`schemathesis` vs `jsonschema-rs` is an unresolved CLI+QA venv compatibility issue.
The Studio Assistant version-switch API showed inconsistent current context after
`set_latest(1)`; desired strict context was restored by creating version 3.
