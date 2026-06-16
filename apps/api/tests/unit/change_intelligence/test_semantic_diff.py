"""L2 semantic diff tests (ADR-016 / TASK-V3-016-05).

TS-UT-CI-SEM-001
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange


def _change(
    change_type: str,
    anchor: str,
    *,
    before_text: str | None = None,
    after_text: str | None = None,
) -> SemanticChange:
    return SemanticChange(
        object_type="clause",
        change_type=change_type,
        anchor=anchor,
        before={"clause_code": anchor, "full_text": before_text}
        if before_text is not None
        else None,
        after={"clause_code": anchor, "full_text": after_text} if after_text is not None else None,
        semantic_summary=f"clause {anchor} {change_type}",
        match_confidence=1.0,
    )


def _changeset(changes: list[SemanticChange]) -> ChangeSet:
    return ChangeSet(
        changeset_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        from_revision_id=uuid4(),
        to_revision_id=uuid4(),
        changes=changes,
        created_at=datetime(2026, 6, 16, 12, 0, 0),
    )


class _FakeLlm:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.requests = []
        self._fail_first = fail_first

    async def generate_structured(self, request, schema):
        self.requests.append(request)
        if self._fail_first and len(self.requests) == 1:
            raise RuntimeError("llm unavailable")
        return schema(
            semantic_summary="penalty cap changed from 5 percent to 10 percent",
            severity="high",
            confidence=0.82,
        )


class _RecordingAnonymizer:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    async def anonymize(self, text: str, _config) -> str:
        self.inputs.append(text)
        return text.replace("john@example.com", "[REDACTED_EMAIL]")


async def _flag_enabled(_tenant_id) -> bool:
    return True


async def _flag_disabled(_tenant_id) -> bool:
    return False


@pytest.mark.asyncio
async def test_flag_off_returns_unchanged_and_never_calls_llm(monkeypatch) -> None:
    from src.change_intelligence.application import semantic_diff

    monkeypatch.setattr(
        semantic_diff,
        "is_change_semantic_llm_enabled",
        _flag_disabled,
    )
    llm = _FakeLlm()
    changeset = _changeset([_change("modified", "5.2", before_text="old", after_text="new")])

    enriched = await semantic_diff.enrich_modified_changes(
        changeset,
        changeset.tenant_id,
        llm=llm,
        anonymizer=_RecordingAnonymizer(),
    )

    assert enriched is changeset
    assert llm.requests == []
    assert enriched.changes[0].severity is None
    assert enriched.changes[0].confidence is None


@pytest.mark.asyncio
async def test_flag_on_enriches_modified_changes_only(monkeypatch) -> None:
    from src.change_intelligence.application import semantic_diff

    monkeypatch.setattr(
        semantic_diff,
        "is_change_semantic_llm_enabled",
        _flag_enabled,
    )
    llm = _FakeLlm()
    changeset = _changeset(
        [
            _change("modified", "5.2", before_text="old", after_text="new"),
            _change("added", "7.1", after_text="added"),
            _change("removed", "9.1", before_text="removed"),
        ]
    )

    enriched = await semantic_diff.enrich_modified_changes(
        changeset,
        changeset.tenant_id,
        llm=llm,
        anonymizer=_RecordingAnonymizer(),
    )

    assert len(llm.requests) == 1
    assert enriched is not changeset
    assert enriched.changes[0].severity == "high"
    assert enriched.changes[0].confidence == 0.82
    assert enriched.changes[1] == changeset.changes[1]
    assert enriched.changes[2] == changeset.changes[2]


@pytest.mark.asyncio
async def test_anonymizer_runs_before_llm_request_is_built(monkeypatch) -> None:
    from src.change_intelligence.application import semantic_diff

    monkeypatch.setattr(
        semantic_diff,
        "is_change_semantic_llm_enabled",
        _flag_enabled,
    )
    llm = _FakeLlm()
    anonymizer = _RecordingAnonymizer()
    changeset = _changeset(
        [
            _change(
                "modified",
                "5.2",
                before_text="Contact john@example.com before notice.",
                after_text="Contact john@example.com after notice.",
            )
        ]
    )

    await semantic_diff.enrich_modified_changes(
        changeset,
        changeset.tenant_id,
        llm=llm,
        anonymizer=anonymizer,
    )

    assert anonymizer.inputs == [
        "Contact john@example.com before notice.",
        "Contact john@example.com after notice.",
    ]
    prompt = llm.requests[0].prompt
    assert "john@example.com" not in prompt
    assert "[REDACTED_EMAIL]" in prompt


@pytest.mark.asyncio
async def test_per_change_llm_error_keeps_l1_null_and_continues(monkeypatch) -> None:
    from src.change_intelligence.application import semantic_diff

    monkeypatch.setattr(
        semantic_diff,
        "is_change_semantic_llm_enabled",
        _flag_enabled,
    )
    changeset = _changeset(
        [
            _change("modified", "5.2", before_text="old one", after_text="new one"),
            _change("modified", "6.1", before_text="old two", after_text="new two"),
        ]
    )

    enriched = await semantic_diff.enrich_modified_changes(
        changeset,
        changeset.tenant_id,
        llm=_FakeLlm(fail_first=True),
        anonymizer=_RecordingAnonymizer(),
    )

    assert enriched.changes[0].severity is None
    assert enriched.changes[0].confidence is None
    assert enriched.changes[1].severity == "high"
    assert enriched.changes[1].confidence == 0.82


def test_semantic_classification_is_frozen_and_forbids_extra() -> None:
    from src.change_intelligence.domain.semantic_classification import (
        SemanticClassification,
    )

    classification = SemanticClassification(
        semantic_summary="penalty cap increased",
        severity="medium",
        confidence=0.7,
    )

    with pytest.raises(ValidationError):
        classification.severity = "high"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SemanticClassification(
            semantic_summary="x",
            severity="low",
            confidence=0.5,
            unexpected=True,
        )
