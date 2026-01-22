from __future__ import annotations

from typing import Any

from src.ai.graph.workflow import get_graph_app


async def run_orchestration(initial_state: dict[str, Any], thread_id: str) -> dict[str, Any]:
    app = get_graph_app()
    return await app.ainvoke(
        initial_state,
        config={
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 10,
        },
    )


async def resume_orchestration(
    thread_id: str,
    human_feedback: str | None = None,
) -> dict[str, Any]:
    app = get_graph_app()
    payload = None
    if human_feedback:
        payload = {"human_feedback": human_feedback}
    return await app.ainvoke(
        payload,
        config={
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 10,
        },
    )


def stream_orchestration(
    thread_id: str,
    human_feedback: str | None = None,
):
    app = get_graph_app()
    payload = None
    if human_feedback:
        payload = {"human_feedback": human_feedback}
    return app.astream(
        payload,
        config={
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 10,
        },
    )
