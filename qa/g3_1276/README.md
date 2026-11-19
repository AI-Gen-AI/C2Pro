# G3 N4-only — executed offline harness (#1274 / #1259)

**Owner D, code under test:** PR #1276 at `8a84f9ebcd54928347171cef0cc80f34ca3fb949`. This PR contains ONLY test/harness files. It does not change B's source branch, production, Railway, UAT, N4 runtime, or #1275.

## Reproduction on authorized AI-GEN QA VPS

The runner is pinned to the detached checkout:
`/home/aigenadmin/qa_workspaces/c2pro-g3-1276-20261119`, expected clean HEAD `8a84f9ebcd...`.

- Source script: `qa/g3_1276/g3_integrated_sql_celery.py`.
- Bootstrap script: `qa/g3_1276/run_g3_ephemeral.sh`.
- The executed copies remain in `/home/aigenadmin/qa_evidence/g3-1276/`, with exact SHA-256 hashes below.
- **Never execute outside `pg_virtualenv`.** The bootstrap asserts a /tmp/pg_virtualenv PostgreSQL cluster, creates only the `c2pro_g3_1276_test` database, uses synthetic fixture credentials, runs Alembic to head, executes the local Python harness, and destroys the entire cluster on exit.

Command for the already executed local copies:

```bash
sudo -u aigenadmin pg_virtualenv -v 16 bash \
  /home/aigenadmin/qa_evidence/g3-1276/run_g3_ephemeral.sh
```

The scripts in this PR match the executed copies but have host-specific QA paths. Before using a **different** isolated environment, adapt paths safely and verify PG destruction, exact SHA and no network/provider access. Do not run against an existing DB.

## Executed result — 19 November 2026

- `G3_INTEGRATED_PYTHON_EXIT=0`; Alembic complete; source SHA pinned.
- `POST` handler with **mocked Clerk-derived owner/tenant** → **real ORM & CAS** generation 2→3, predecessor fence8→new fence9. Second ordinary POST denied HTTP 409.
- Celery `process_document_async.apply()` plus `process_document_n4_only_pilot_async.apply()` **real decorated task handlers in-process**. Enqueue was an in-memory test stub; broker, remote worker and complete parser are NOT exercised.
- N1/N2 graph nodes are test doubles producing deterministic N2 text. Real N4-only graph topology/END, N4 scope checks, real `N4IncrementalRunner`, real ledger on same migrated PostgreSQL. 23 model-stub invocations, 23 settled receipts, 23 findings, synthetic 5 USD cap, zero paid calls.
- GET handler uses the same database, read-only SQL transaction; 23 findings in COMPLETE, pagination last ordinal22; wrong user/tenant denied.
- N12/HITL/TRUSTED/Score not present among executed graph nodes; return state N12 UNASSESSED, no human approval, trust PROPOSED, score null. Negative spies over all real remote code paths are not yet certified.
- RLS check uses the **actual Alembic policies** under `SET ROLE c2pro_g3_rls_reader` (NOLOGIN, NOSUPERUSER, NOBYPASSRLS). Unscoped document query returns zero, tenant-scoped query returns its document and 23 N4 reservations; other tenant hidden. Schema metadata: documents, n4_extraction_runs and n4_usage_reservations ENABLE+FORCE RLS; tenants ENABLE RLS (not FORCE). **JWT→tenant GUC mapping is mocked and not proven.**

Hashes from terminal run:
- Runner Python `e0d847ca8e98f426f33c4849684fb8369fb8f1afe621e5988c4f840eb7e9c702`.
- Runner shell `ec234d616833f4b7854a0d1b1d5812c1227924a34b3f0f163c6dd6e5fae526c8`.
- Alembic log `c140dd352d206b33e6fe7525b9c4dcbe0420e51623fb6bfea50fcba9bf0eef46`.
- G3 completed log `edacfbd3567a93ef1847d9b751c13d75d7e86993fa3812776e471c16b9114c41`.
- Logs retained only on authorized QA VPS, no Clerk secrets and no PDF contractual content.

## Independently blocking issues

1. **G3-LIVENESS-01 FAIL**: exact-SHA POST commits generation before queue; simulated enqueue failure leaves new gen unqueued, ordinary second POST 409 and generic recovery deliberately skips N4-only. CORE's original 1/1 failure-injection test was independently rerun by D: PASS expected failure. B owns outbox/reconciler or governed recover (no generic N12, no replay if UNKNOWN).
2. Real Clerk/JWT, broker/worker process, real N1/N2 parser, worker-persisted marker, R1/PDF source, crash windows, and complete N12/HITL/TRUSTED/Score fail-fast coverage **NOT VERIFIED**.
3. Full negative races against workers/UNKNOWN/retry/lease and concurrent reservations need review against the **same** real integration path, beyond E's accepted G2 synthetic regression. Real UAT and paid N4 remain NO_GO.

**Verdict: G3 component-integrated `PASS_LIMITED`, operational `NO_GO` due G3-LIVENESS-01.**
