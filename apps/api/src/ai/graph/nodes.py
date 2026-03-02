"""Re-export nodes from analysis.adapters.graph.

Provides a critique_node wrapper that resolves _critique_extraction
from this module's namespace so that monkeypatching works in tests.
"""

import sys
from typing import Any

from langchain_core.messages import AIMessage

from src.analysis.adapters.graph.nodes import *  # noqa: F401, F403
from src.analysis.adapters.graph.nodes import (
    _critique_extraction,  # noqa: F401
    _average_confidence,
)


async def critique_node(state: dict[str, Any]) -> dict[str, Any]:
    """Critique node that resolves _critique_extraction via module lookup.

    This allows tests to monkeypatch ``nodes._critique_extraction`` and
    have the replacement called when the graph executes this node.
    """
    _this = sys.modules[__name__]

    items = state["extracted_risks"] if state["extracted_risks"] else state["extracted_wbs"]
    state["confidence_score"] = _average_confidence(items)
    critique = await _this._critique_extraction(
        items=items,
        doc_type=state.get("doc_type") or "unknown",
        tenant_id=state.get("tenant_id"),
    )
    status = critique["status"]
    if status == "RETRY":
        state["critique_notes"] = critique["notes"]
        state["retry_count"] += 1
    else:
        state["critique_notes"] = ""
    state["human_approval_required"] = (
        state["confidence_score"] < 0.8 or (status == "RETRY" and state["retry_count"] >= 2)
    )
    state["messages"].append(
        AIMessage(
            content=(
                f"Critique status={status} confidence={state['confidence_score']:.2f} "
                f"retry_count={state['retry_count']}"
            )
        )
    )
    return state
