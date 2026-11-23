# JV1 / A3+A5 — isolated integration evidence

**SHAs pinned:** A3 49870fdb6567c9b53ed8886d1d006509a0861e33; A5 6dd63bb9aae540432e0d592025f82785f6769c07.

**Execution:** A3 detached local clone with only six A5 source/test files copied byte-identically from its pinned checkout; no product PR modified, no merge/deploy. PG 16.15 isolated 127.0.0.1:55513; Alembic 20261118_0001. All tests synthetic and LLM call disabled by a fake wrapper.

**Reproduce:** Create a fresh PostgreSQL16 cluster, scratch main and aux *_test databases, and migrate both to head using Alembic. Use ENVIRONMENT=test, JWT_SECRET_KEY=synthetic-dummy, TEST_DATABASE_URL and DATABASE_URL set to each isolated PG DSN; set C2PRO_N4_SCRATCH_DSN to postgresql:// scratch test DB. Run pytest on tests/integration/analysis/test_n4_*_pg.py EXCLUDING test_n4_partial_ledger_sql_pg.py, plus tests/integration/analysis/test_jv1_a3a5_synthetic_compat.py and five unit modules for N4/A3. Run test_n4_partial_ledger_sql_pg.py separately on the AUX database. Use -q -rs -o addopts='' -p no:randomly -p no:cacheprovider --junitxml=PATH.

**Reason for splitting:** The DB fixture in test_n4_partial_ledger_sql_pg.py resets public schema; in a single shared database this invalidates migrated N4 tables for subsequent tests. 23 prior failures in our OWN trial were due to this reproducible collision, NOT a demonstrated defect in L1. Do not project cause to a different autonomous A3 LV without examining its traceback/DSN.

**Final results:** Main 153/153 PASS; auxiliary 1/1 PASS; cross citation-strengthened replay 3/3 PASS (already included in main 153, therefore not added to the distinct count). Total distinct tests 154 PASS / 0 FAIL / 0 SKIP. The 3 cross tests include malformed tool→retry w/distinct receipts, live PG source quote span/PROPOSED, fencing during in-flight, and truncation fail-closed.

**Caution:** Author-executed synthetic integration is NOT an independent LV, semantic PDF proof, permission to merge, or permission to deploy. A5_MERGE_HOLD, A6_HOLD, JV1_GLOBAL=NO_GO.
