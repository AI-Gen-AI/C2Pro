"""TS-OBS-COH-001: Regression coverage for coherence tracing state metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.coherence.domain.v2_constants import SCORE_VERSION_V1
from src.coherence.graph.state import CoherenceGraphState, EvaluationConfig
from src.core.observability.coherence_tracing import traced_coherence_node


@dataclass
class _FakeLangSmithClient:
    """TS-OBS-COH-001: Minimal enabled tracing client used for regression checks."""

    spans: list[dict[str, Any]] = field(default_factory=list)
    ended_spans: list[tuple[dict[str, Any], Exception | None]] = field(
        default_factory=list
    )
    is_enabled: bool = True

    def start_span(
        self,
        *,
        name: str,
        run_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """TS-OBS-COH-001: Capture span metadata without external I/O."""
        span = {"name": name, "run_type": run_type, "metadata": metadata}
        self.spans.append(span)
        return span

    def end_span(
        self,
        span: dict[str, Any],
        error: Exception | None = None,
    ) -> None:
        """TS-OBS-COH-001: Capture completed spans."""
        self.ended_spans.append((span, error))

    def update_span_metadata(
        self,
        span: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        """TS-OBS-COH-001: Merge post-node metadata into the captured span."""
        span["metadata"].update(metadata)


@dataclass
class _FailingLangSmithClient(_FakeLangSmithClient):
    """TS-OBS-COH-001: Tracing client that simulates observability failure."""

    def start_span(
        self,
        *,
        name: str,
        run_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """TS-OBS-COH-001: Simulate an upstream telemetry outage."""
        raise RuntimeError("langsmith unavailable")


@dataclass
class _FailingEndSpanLangSmithClient(_FakeLangSmithClient):
    """TS-OBS-COH-001: Client that fails during telemetry finalization."""

    def end_span(
        self,
        span: dict[str, Any],
        error: Exception | None = None,
    ) -> None:
        """TS-OBS-COH-001: Simulate telemetry shutdown failure."""
        raise RuntimeError("langsmith finalize unavailable")


def test_traced_coherence_node_reads_tenant_from_runtime_state_config(
    monkeypatch: Any,
) -> None:
    """TS-OBS-COH-001: Runtime coherence states expose tenant metadata to tracing."""
    fake_client = _FakeLangSmithClient()
    monkeypatch.setattr(
        "src.core.observability.coherence_tracing.get_client",
        lambda: fake_client,
    )

    @traced_coherence_node("prepare_context")
    def _prepare_context(state: CoherenceGraphState) -> dict[str, Any]:
        return {"all_signals": []}

    state = CoherenceGraphState(
        project_id="project-123",
        config=EvaluationConfig(tenant_id="tenant-456"),
    )

    result = _prepare_context(state)

    assert result == {"all_signals": []}
    assert fake_client.spans == [
        {
            "name": "coherence_node:prepare_context",
            "run_type": "chain",
            "metadata": {
                "coherence.node_name": "prepare_context",
                "coherence.score_version": SCORE_VERSION_V1,
                "coherence.tenant_id": "tenant-456",
                "coherence.project_id": "project-123",
                "coherence.findings_count": 0,
                "coherence.rule_ids": [],
            },
        }
    ]
    assert fake_client.ended_spans == [(fake_client.spans[0], None)]


def test_traced_coherence_node_fails_open_when_telemetry_start_fails(
    monkeypatch: Any,
) -> None:
    """TS-OBS-COH-001: Telemetry failures must not block coherence evaluation."""
    monkeypatch.setattr(
        "src.core.observability.coherence_tracing.get_client",
        lambda: _FailingLangSmithClient(),
    )

    @traced_coherence_node("prepare_context")
    def _prepare_context(state: CoherenceGraphState) -> dict[str, Any]:
        return {"all_signals": []}

    state = CoherenceGraphState(
        project_id="project-123",
        config=EvaluationConfig(tenant_id="tenant-456"),
    )

    assert _prepare_context(state) == {"all_signals": []}


def test_traced_coherence_node_fails_open_when_telemetry_end_fails(
    monkeypatch: Any,
) -> None:
    """TS-OBS-COH-001: Span finalization failures must not block graph output."""
    monkeypatch.setattr(
        "src.core.observability.coherence_tracing.get_client",
        lambda: _FailingEndSpanLangSmithClient(),
    )

    @traced_coherence_node("prepare_context")
    def _prepare_context(state: CoherenceGraphState) -> dict[str, Any]:
        return {"all_signals": []}

    state = CoherenceGraphState(
        project_id="project-123",
        config=EvaluationConfig(tenant_id="tenant-456"),
    )

    assert _prepare_context(state) == {"all_signals": []}
