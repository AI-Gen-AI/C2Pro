"""Pre-labeler for the clause-reader precision gate (#1136).

Reads candidate clauses (JSONL: id, text, lang, source, family), proposes a daily rate and a cumulative cap
for each, and writes the labelled corpus (SCHEMA.md) after a human confirms or corrects every line.

* A third of the clauses, picked by a hash of the id, is the **holdout**: it is labelled blind (no proposal
  is shown), so the measurement is not anchored on the reader being measured. The rest shows the proposal.
* The proposal comes from the reader of ``--reader-tree`` (a checkout containing ``apps/api``).
* Nothing is auto-accepted: every line needs a keystroke. The output is appended line by line, so the
  session can be interrupted and resumed.

Answers: Enter = confirm the proposal (not allowed on blind lines); ``d=0.1% c=10%`` or ``d=0.001 c=-``
(``-`` = none, ``%`` = percent, no ``%`` = a fraction); ``s`` = skip the clause; ``q`` = quit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

HOLDOUT_MODULUS = 3

CHILD = """
import json, sys
sys.path.insert(0, sys.argv[1])
from src.documents.domain.contract_clause_reader import penalty_rate_and_cap
rows = json.load(open(sys.argv[2], encoding="utf-8"))
json.dump({r["id"]: list(penalty_rate_and_cap(r["text"])) for r in rows}, sys.stdout)
"""


def split_of(clause_id: str) -> str:
    """``holdout`` for a stable third of the ids, ``proposal`` for the rest."""
    digest = hashlib.sha256(clause_id.encode("utf-8")).digest()
    return "holdout" if int.from_bytes(digest[:4], "big") % HOLDOUT_MODULUS == 0 else "proposal"


def parse_value(token: str) -> float | None:
    token = token.strip().lower()
    if token in {"-", "none", "null", ""}:
        return None
    if token.endswith("%"):
        return round(float(token[:-1].replace(",", ".")) / 100, 12)
    return float(token.replace(",", "."))


def parse_answer(answer: str) -> tuple[float | None, float | None]:
    """``d=<value> c=<value>`` (both required) -> (daily, cap)."""
    fields = {}
    for part in answer.split():
        key, sep, value = part.partition("=")
        if not sep or key not in {"d", "c"}:
            raise ValueError(f"unreadable answer part: {part!r}")
        fields[key] = parse_value(value)
    if set(fields) != {"d", "c"}:
        raise ValueError("answer needs both d=... and c=...")
    return fields["d"], fields["c"]


def read_candidates(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate ids in candidates")
    return rows


def propose(
    reader_tree: Path, rows: list[dict[str, Any]], scratch: Path
) -> dict[str, list[float | None]]:
    scratch.write_text(
        json.dumps([{"id": r["id"], "text": r["text"]} for r in rows]), encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", CHILD, str(reader_tree / "apps" / "api"), str(scratch)],
        capture_output=True,
        text=True,
        check=True,
    )
    readings: dict[str, list[float | None]] = json.loads(result.stdout)
    return readings


def fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:g} ({value * 100:g}%)"


def label_one(
    row: dict[str, Any], proposal: list[float | None], ask: Callable[[str], str]
) -> dict[str, Any] | None:
    """Return the labelled row, ``None`` to skip, raise ``EOFError`` to quit."""
    blind = split_of(row["id"]) == "holdout"
    print(f"\n--- {row['id']} [{row['lang']}] {'BLIND' if blind else ''}\n{row['text']}\n")
    if not blind:
        print(f"proposal: daily={fmt(proposal[0])}  cap={fmt(proposal[1])}")
    while True:
        answer = ask("> ").strip()
        if answer == "q":
            raise EOFError
        if answer == "s":
            return None
        try:
            if answer == "" and not blind:
                daily, cap, confirmed = proposal[0], proposal[1], True
            else:
                daily, cap = parse_answer(answer)
                confirmed = not blind and [daily, cap] == proposal
        except ValueError as error:
            print(f"  {error}")
            continue
        labelled: dict[str, Any] = {
            k: row[k] for k in ("id", "text", "lang", "source", "family") if k in row
        }
        labelled.setdefault("family", "unclassified")
        labelled.update({"daily": daily, "cap": cap, "split": "holdout" if blind else "proposal"})
        if not blind:
            labelled["confirmed_proposal"] = confirmed
        return labelled


def main(argv: list[str] | None = None, ask: Callable[[str], str] = input) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("candidates", type=Path)
    parser.add_argument(
        "--out", type=Path, required=True, help="labelled corpus JSONL (outside the repository)"
    )
    parser.add_argument("--reader-tree", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = read_candidates(args.candidates)
    done = set()
    if args.out.exists():
        done = {
            json.loads(line)["id"]
            for line in args.out.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    todo = [row for row in rows if row["id"] not in done]
    proposals = propose(args.reader_tree, todo, args.out.with_suffix(".proposal.tmp"))
    args.out.with_suffix(".proposal.tmp").unlink(missing_ok=True)
    with args.out.open("a", encoding="utf-8") as out:
        for row in todo:
            try:
                labelled = label_one(row, proposals[row["id"]], ask)
            except EOFError:
                break
            if labelled is not None:
                out.write(json.dumps(labelled, ensure_ascii=False) + "\n")
                out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
