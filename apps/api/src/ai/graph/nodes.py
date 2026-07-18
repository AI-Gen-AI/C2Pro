"""Re-export nodes from analysis.adapters.graph.

Provides a critique_node wrapper that resolves _critique_extraction
from this module's namespace so that monkeypatching works in tests.
"""

import os
import sys
from typing import Any

from langchain_core.messages import AIMessage

from src.analysis.adapters.graph.nodes import (
    _critique_extraction,  # noqa: F401
    budget_parser_node,  # noqa: F401
    human_interrupt_node,  # noqa: F401
    risk_extractor_node,  # noqa: F401
    router_node,  # noqa: F401
    save_to_db_node,  # noqa: F401
    wbs_extractor_node,  # noqa: F401
)
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService

_critique_evaluator = CritiqueEvaluationService()


async def critique_node(state: dict[str, Any]) -> dict[str, Any]:
    """Critique node that resolves _critique_extraction via module lookup.

    This allows tests to monkeypatch ``nodes._critique_extraction`` and
    have the replacement called when the graph executes this node.
    """
    _this = sys.modules[__name__]

    items = state["extracted_risks"] if state["extracted_risks"] else state["extracted_wbs"]
    confidence = _critique_evaluator.calculate_confidence(items)
    state["confidence_score"] = confidence

    critique = await _this._critique_extraction(
        items=items,
        doc_type=state.get("doc_type") or "unknown",
        tenant_id=state.get("tenant_id"),
    )

    skip_hitl = os.getenv("C2PRO_AI_MOCK", "0") == "1"
    result = _critique_evaluator.evaluate_critique(
        critique_status=critique["status"],
        critique_notes=critique["notes"],
        confidence=confidence,
        retry_count=state["retry_count"],
        skip_hitl=skip_hitl,
    )

    state["retry_count"] = result.retry_count
    state["critique_notes"] = result.critique_notes
    state["human_approval_required"] = result.human_approval_required
    state["messages"].append(
        AIMessage(
            content=(
                f"Critique status={critique['status']} confidence={confidence:.2f} "
                f"retry_count={result.retry_count}"
            )
        )
    )
    return state


__all__ = [
    "budget_parser_node",
    "critique_node",
    "human_interrupt_node",
    "risk_extractor_node",
    "router_node",
    "save_to_db_node",
    "wbs_extractor_node",
]
