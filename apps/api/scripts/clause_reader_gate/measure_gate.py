"""Measure precision and recall of the contract penalty reader on a labelled corpus (outside the repo).

Usage:
    python measure_gate.py CORPUS.jsonl --main-tree PATH_TO_MAIN_WORKTREE --branch-tree PATH [--only holdout|proposal]

Each tree is a git worktree (or checkout) containing ``apps/api``. The reader is imported from each in a fresh
subprocess so that both versions are measured with their own code. Only ids are printed for wrong readings,
so that the output can be shared without exposing the clauses.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

CHILD = """
import json, sys
sys.path.insert(0, sys.argv[1])
from src.documents.domain.contract_clause_reader import penalty_rate_and_cap
rows = [json.loads(line) for line in open(sys.argv[2], encoding="utf-8") if line.strip()]
json.dump({r["id"]: list(penalty_rate_and_cap(r["text"])) for r in rows}, sys.stdout)
"""


def read_corpus(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    required = {"id", "text", "lang", "daily", "cap", "source", "family"}
    for row in rows:
        missing = required - row.keys()
        if missing:
            raise SystemExit(f"{row.get('id', '?')}: missing fields {sorted(missing)}")
        if row["lang"] not in {"es", "en", "mixed"}:
            raise SystemExit(f"{row['id']}: lang must be es, en or mixed")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate ids")
    return rows


def run_reader(tree: Path, corpus: Path) -> dict[str, list[float | None]]:
    result = subprocess.run(
        [sys.executable, "-I", "-c", CHILD, str(tree / "apps" / "api"), str(corpus)],
        capture_output=True,
        text=True,
        check=True,
    )
    readings: dict[str, list[float | None]] = json.loads(result.stdout)
    return readings


def same(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def classify(label: float | None, got: float | None) -> str:
    if same(label, got):
        return "exact"
    if got is None:
        return "missed"
    return "wrong"  # a number where the label is null, or a different number


def measure(rows: list[dict[str, Any]], readings: dict[str, list[float | None]]) -> dict[str, Any]:
    totals: dict[str, collections.Counter[str]] = {"all": collections.Counter()}
    wrong_ids: list[str] = []
    for row in rows:
        got = readings[row["id"]]
        for slot, label in enumerate((row["daily"], row["cap"])):
            kind = classify(label, got[slot])
            if label is None and kind == "exact":
                kind = "exact_null"
            for bucket in ("all", f"lang:{row['lang']}", f"family:{row['family']}"):
                totals.setdefault(bucket, collections.Counter())[kind] += 1
            if kind == "wrong":
                wrong_ids.append(f"{row['id']}:{'daily' if slot == 0 else 'cap'}")
    return {"totals": totals, "wrong": sorted(wrong_ids)}


def summarise(name: str, outcome: dict[str, Any]) -> None:
    print(f"== {name}")
    for bucket, counter in sorted(outcome["totals"].items()):
        exact, null_ok = counter["exact"], counter["exact_null"]
        wrong, missed = counter["wrong"], counter["missed"]
        precision = (
            (exact + null_ok) / (exact + null_ok + wrong) if exact + null_ok + wrong else 1.0
        )
        recall = exact / (exact + missed + wrong) if exact + missed + wrong else 1.0
        print(
            f"{bucket:28s} exact_number={exact:4d} exact_null={null_ok:4d} wrong={wrong:3d} "
            f"missed={missed:3d}  precision={precision:.3f} recall={recall:.3f}"
        )
    print("wrong readings (ids only):", ", ".join(outcome["wrong"]) or "none")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--main-tree", type=Path, required=True)
    parser.add_argument("--branch-tree", type=Path, required=True)
    parser.add_argument(
        "--only", choices=("holdout", "proposal"), help="measure one split (see prelabel.py)"
    )
    args = parser.parse_args()
    rows = read_corpus(args.corpus)
    if args.only:
        rows = [row for row in rows if row.get("split") == args.only]
        if not rows:
            raise SystemExit(f"no clause with split={args.only}")
    main_outcome = measure(rows, run_reader(args.main_tree, args.corpus))
    branch_outcome = measure(rows, run_reader(args.branch_tree, args.corpus))
    summarise("main", main_outcome)
    summarise("branch", branch_outcome)
    branch_all, main_all = branch_outcome["totals"]["all"], main_outcome["totals"]["all"]
    lost = main_all["exact"] - branch_all["exact"]
    print(
        f"\nclauses={len(rows)}  branch wrong={branch_all['wrong']}  exact numbers lost vs main={lost}"
    )
    gate = branch_all["wrong"] == 0 and lost <= 0
    print(
        "GATE:",
        "PASS" if gate else "FAIL (entry criterion: zero wrong numbers, no exact number lost)",
    )
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
