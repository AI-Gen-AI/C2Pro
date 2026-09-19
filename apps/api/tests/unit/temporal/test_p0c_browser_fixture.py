"""PJ-01: deterministic fixture contract for the P0c browser journey."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e_seed.p0c_temporal import build_p0c_browser_fixture


def test_fixture_exposes_immutable_temporal_journey_for_browser_consumers() -> None:
    """A broken projection/cause/evidence contract must fail PJ-01 before browser runtime."""
    fixture = build_p0c_browser_fixture()

    assert fixture.business_change.event_type == "revision.changed"
    assert fixture.business_change.payload["change_cause"] == "BUSINESS_STATE_CHANGED"
    assert fixture.newly_discovered.event_type == "revision.reinterpreted"
    assert fixture.newly_discovered.payload["change_cause"] == "NEWLY_DISCOVERED"
    assert fixture.no_change.event_type == "revision.changed"
    assert fixture.no_change.payload["change_cause"] is None
    assert fixture.business_change.payload["changeset"]["changes"][0]["before"]["full_text"] == (
        "Completion is due on 30 June 2026."
    )
    assert fixture.business_change.payload["changeset"]["changes"][0]["after"]["full_text"] == (
        "Completion is due on 31 July 2026."
    )
    assert fixture.newly_discovered.payload["provenance"]["reinterpretation_of_event_id"] == str(
        fixture.business_change.event_id
    )
    assert fixture.newly_discovered.evidence_refs == fixture.business_change.evidence_refs
    assert fixture.timeline == [fixture.business_change, fixture.newly_discovered, fixture.no_change]


# test_fixture_persists_only_append_only_events_and_returns_browser_manifest moved to
# tests/integration/temporal/test_p0c_browser_fixture_persistence.py -- it needs a real
# `db` (live PostgreSQL) and the Unit Tests CI job runs with no database service, only
# `-m "not integration"` over tests/unit/. It belongs on the CI surface that has one.


def test_browser_manifest_writer_keeps_ids_and_evidence_json_serializable(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    """A provisioner that loses revision/event identity would make browser evidence unverifiable."""
    from scripts.seed_p0c_browser_journey import write_manifest

    # write_manifest resolves --output against the invocation directory and refuses one
    # that escapes it (CWE-22); exercise it the way the CLI actually runs, in its cwd.
    monkeypatch.chdir(tmp_path)
    path = Path("pj01.json")
    write_manifest(path, {"project_id": "project", "events": {"C": {"change_cause": "NEWLY_DISCOVERED"}}})

    assert (tmp_path / "pj01.json").read_text(encoding="utf-8") == (
        '{\n  "events": {\n    "C": {\n      "change_cause": "NEWLY_DISCOVERED"\n    }\n  },\n'
        '  "project_id": "project"\n}\n'
    )


def test_browser_manifest_writer_rejects_output_path_that_escapes_its_own_base(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    """CWE-22 regression guard: --output must not resolve outside the invocation directory."""
    from scripts.seed_p0c_browser_journey import write_manifest

    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="must resolve inside"):
        write_manifest(Path("../escaped.json"), {})
