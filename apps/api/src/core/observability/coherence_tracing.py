"""
Decorator and context manager for creating LangSmith spans for Coherence graph nodes,
with strict validation against an allowlisted schema to prevent data leakage.
"""
from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from src.core.ai.langsmith_client import get_client
from src.core.observability.coherence_span_schema import COHERENCE_SPAN_ATTRIBUTE_ALLOWLIST


def _validate_attributes(attributes: dict[str, Any]) -> None:
    """Raises ValueError if any attribute key is not in the allowlist."""
    for key in attributes:
        if key not in COHERENCE_SPAN_ATTRIBUTE_ALLOWLIST:
            raise ValueError(f"Attribute '{key}' is not in the allowlisted schema.")


def traced_coherence_node(
    node_name: str,
) -> Callable:
    """
    A decorator that wraps a Coherence graph node function to create a LangSmith span.

    It captures the node execution, validates all metadata against a strict allowlist,
    and records the span. This decorator works for both sync and async functions.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            langsmith_client = get_client()
            if not langsmith_client.is_enabled:
                return func(*args, **kwargs)

            # Assumes the state object is the first argument
            state = args[0]
            span_attributes = {
                "coherence.node_name": node_name,
                "coherence.score_version": "v1",  # Per task, hardcode to v1
                "coherence.tenant_id": str(state.tenant_id),
                "coherence.project_id": str(state.project_id),
            }

            span = None
            caught_error: Exception | None = None
            try:
                _validate_attributes(span_attributes)
                try:
                    span = langsmith_client.start_span(
                        name=f"coherence_node:{node_name}",
                        run_type="chain",
                        metadata=span_attributes,
                    )
                except Exception:
                    # TS-OBS-COH-001: Observability must never block core evaluation.
                    return func(*args, **kwargs)

                result = func(*args, **kwargs)

                # In format_output, also create alert events
                if node_name == "format_output" and "alerts" in result:
                    for alert in result.get("alerts", []):
                        if alert.severity in ("high", "critical"):
                            create_alert_span(alert.rule_id, alert.severity, state)

                # Extract post-execution attributes from the result if available
                if "all_signals" in result and result["all_signals"] is not None:
                    findings_count = len(result["all_signals"])
                    rule_ids = sorted({s.rule_id for s in result["all_signals"]})
                    output_attributes = {
                        "coherence.findings_count": findings_count,
                        "coherence.rule_ids": rule_ids,
                    }
                    _validate_attributes(output_attributes)
                    if span:
                        try:
                            langsmith_client.update_span_metadata(
                                span,
                                output_attributes,
                            )
                        except Exception:
                            # TS-OBS-COH-001: Metadata enrichment is best-effort only.
                            pass

                return result
            except Exception as e:
                caught_error = e
                raise
            finally:
                if span:
                    try:
                        langsmith_client.end_span(span, error=caught_error)
                    except Exception:
                        # TS-OBS-COH-001: Telemetry finalization is best-effort only.
                        pass

        return wrapper
    return decorator

def create_alert_span(rule_id: str, severity: str, state: Any) -> None:
    """Creates a discrete event span for a generated alert."""
    langsmith_client = get_client()
    if not langsmith_client.is_enabled:
        return

    attributes = {
        "coherence.alert.rule_id": rule_id,
        "coherence.alert.severity": severity,
        "coherence.tenant_id": str(state.tenant_id),
        "coherence.project_id": str(state.project_id),
    }

    try:
        # We don't need to validate tenant/project_id as they are not part of the alert schema itself.
        _validate_attributes({k: v for k, v in attributes.items() if k.startswith("coherence.alert")})
        langsmith_client.create_event(
            name=f"Coherence Alert: {rule_id}",
            metadata=attributes,
            event_type="alert",
        )
    except Exception:
        # Fail silently; telemetry should not block execution.
        pass

