"""PJ-01: deterministic fixture contract for the P0c browser journey."""

from __future__ import annotations

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


@pytest.mark.asyncio
async def test_fixture_persists_only_append_only_events_and_returns_browser_manifest(db) -> None:  # noqa: ANN001
    """Removing a real repository append or exposing mutable evidence must fail fixture setup."""
    from tests.e2e_seed.p0c_temporal import seed_p0c_browser_fixture

    manifest = await seed_p0c_browser_fixture(db)

    assert manifest["project_id"]
    assert manifest["document_id"]
    assert manifest["revisions"]["A"]["blob_hash"] != manifest["revisions"]["B"]["blob_hash"]
    assert manifest["events"]["B"]["change_cause"] == "BUSINESS_STATE_CHANGED"
    assert manifest["events"]["C"]["change_cause"] == "NEWLY_DISCOVERED"
    assert manifest["events"]["D"]["change_cause"] is None


def test_browser_manifest_writer_keeps_ids_and_evidence_json_serializable(tmp_path) -> None:  # noqa: ANN001
    """A provisioner that loses revision/event identity would make browser evidence unverifiable."""
    from scripts.seed_p0c_browser_journey import write_manifest

    path = tmp_path / "pj01.json"
    write_manifest(path, {"project_id": "project", "events": {"C": {"change_cause": "NEWLY_DISCOVERED"}}})

    assert path.read_text(encoding="utf-8") == (
        '{\n  "events": {\n    "C": {\n      "change_cause": "NEWLY_DISCOVERED"\n    }\n  },\n'
        '  "project_id": "project"\n}\n'
    )
