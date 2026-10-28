"""Tests for scripts/clause_reader_gate (precision gate of the contract penalty reader, #1136).

Synthetic clauses only: the real corpus never enters the repository.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

GATE_DIR = Path(__file__).resolve().parents[3] / "scripts" / "clause_reader_gate"
sys.path.insert(0, str(GATE_DIR))

import extract_clauses  # noqa: E402
import measure_gate as measure  # noqa: E402
import prelabel  # noqa: E402

REPO_ROOT = GATE_DIR.parents[3]
DELAY = "Por cada día natural de retraso el Contratista abonará una penalización del 0,1% del Precio del Contrato, hasta un máximo del 10%."


def test_split_is_stable_and_about_a_third() -> None:
    ids = [f"es-{n:04d}" for n in range(900)]
    assert [prelabel.split_of(i) for i in ids] == [prelabel.split_of(i) for i in ids]
    holdout = sum(prelabel.split_of(i) == "holdout" for i in ids)
    assert 250 < holdout < 350


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("d=0.1% c=10%", (0.001, 0.1)),
        ("d=0,001 c=-", (0.001, None)),
        ("c=5% d=-", (None, 0.05)),
    ],
)
def test_parse_answer(answer: str, expected: tuple[float | None, float | None]) -> None:
    daily, cap = prelabel.parse_answer(answer)
    assert daily == pytest.approx(expected[0]) and cap == pytest.approx(expected[1])


@pytest.mark.parametrize("answer", ["d=0.1%", "x=1 c=2", "hello"])
def test_parse_answer_rejects_incomplete_or_unknown(answer: str) -> None:
    with pytest.raises(ValueError):
        prelabel.parse_answer(answer)


def _row(clause_id: str) -> dict:
    return {
        "id": clause_id,
        "text": DELAY,
        "lang": "es",
        "source": "synthetic/ES/2026",
        "family": "daily",
    }


def _id_with_split(split: str) -> str:
    return next(i for i in (f"x-{n}" for n in range(100)) if prelabel.split_of(i) == split)


def test_proposal_line_can_be_confirmed_with_enter() -> None:
    row = _row(_id_with_split("proposal"))
    labelled = prelabel.label_one(row, [0.001, 0.1], lambda _prompt: "")
    assert labelled is not None
    assert (
        labelled["daily"],
        labelled["cap"],
        labelled["split"],
        labelled["confirmed_proposal"],
    ) == (0.001, 0.1, "proposal", True)


def test_blind_line_never_shows_the_proposal_and_needs_an_explicit_answer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    row = _row(_id_with_split("holdout"))
    answers = iter(["", "d=0.1% c=10%"])  # Enter is refused on a blind line
    labelled = prelabel.label_one(row, [0.5, 0.5], lambda _prompt: next(answers))
    shown = capsys.readouterr().out
    assert "proposal:" not in shown and "0.5" not in shown
    assert (
        labelled is not None
        and labelled["split"] == "holdout"
        and "confirmed_proposal" not in labelled
    )
    assert (labelled["daily"], labelled["cap"]) == pytest.approx((0.001, 0.1))


def test_skip_and_quit() -> None:
    row = _row(_id_with_split("proposal"))
    assert prelabel.label_one(row, [None, None], lambda _prompt: "s") is None
    with pytest.raises(EOFError):
        prelabel.label_one(row, [None, None], lambda _prompt: "q")


def test_extractor_keeps_penalty_clauses_with_a_figure_and_no_file_name(tmp_path: Path) -> None:
    source = tmp_path / "secret-contract-name.txt"
    source.write_text(
        f"{DELAY}\n\nEl contratista ejecutará las obras conforme al proyecto aprobado y a la normativa vigente.\n\n"
        "Se aplicará una penalidad por demora sin cifra alguna en este párrafo de ejemplo del pliego.\n",
        encoding="utf-8",
    )
    out = tmp_path / "cands.jsonl"
    assert (
        extract_clauses.main(
            [str(source), "--out", str(out), "--source", "PCAP/ES/2026", "--prefix", "es-test"]
        )
        == 0
    )
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in rows] == ["es-test-0001"]
    assert rows[0]["lang"] == "es" and rows[0]["source"] == "PCAP/ES/2026"
    assert "secret-contract-name" not in out.read_text(encoding="utf-8")


def test_measure_counts_wrong_missed_and_exact() -> None:
    rows = [
        {"id": "a", "daily": 0.001, "cap": None, "lang": "es", "family": "f"},
        {"id": "b", "daily": 0.001, "cap": 0.1, "lang": "es", "family": "f"},
        {"id": "c", "daily": None, "cap": None, "lang": "en", "family": "g"},
    ]
    readings = {"a": [0.001, None], "b": [None, 0.2], "c": [0.5, None]}
    outcome = measure.measure(rows, readings)
    totals = outcome["totals"]["all"]
    assert (totals["exact"], totals["exact_null"], totals["missed"], totals["wrong"]) == (
        1,
        2,
        1,
        2,
    )
    assert outcome["wrong"] == ["b:cap", "c:daily"]


def test_gate_end_to_end_on_this_tree(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "id": "s-1",
                "text": DELAY,
                "lang": "es",
                "daily": 0.001,
                "cap": 0.1,
                "source": "synthetic/ES/2026",
                "family": "daily",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rows = measure.read_corpus(corpus)
    readings = measure.run_reader(REPO_ROOT, corpus)
    outcome = measure.measure(rows, readings)
    assert outcome["wrong"] == []
