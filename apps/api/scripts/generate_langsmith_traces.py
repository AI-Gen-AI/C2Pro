#!/usr/bin/env python
"""
Generate real LangSmith traces for C2Pro workflow.

This script executes a simple workflow to generate traces that appear in LangSmith.
Run with: python scripts/generate_langsmith_traces.py

Requires:
- LANGCHAIN_TRACING_V2=true
- LANGSMITH_API_KEY set in environment or .env
- LANGSMITH_PROJECT=C2Pro (optional, defaults to "default")
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from uuid import uuid4

# Add parent to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.dirname(script_dir)
repo_root = os.path.dirname(os.path.dirname(api_dir))
sys.path.insert(0, api_dir)

from dotenv import load_dotenv  # noqa: E402 - import must follow the script path bootstrap

# Load .env from repo root
env_path = os.path.join(repo_root, ".env")
load_dotenv(env_path)
print(f"[DEBUG] Loading .env from: {env_path}")


async def generate_simple_trace():
    """Generate a simple trace using LangSmith client directly."""
    from langsmith.run_trees import RunTree

    project_name = os.getenv("LANGSMITH_PROJECT", "C2Pro")
    print(f"[INFO] Generating trace in project: {project_name}")

    # Use RunTree for hierarchical trace structure
    parent_run = RunTree(
        name="C2Pro_Workflow_Test",
        run_type="chain",
        inputs={
            "project_id": "test-project-001",
            "document_type": "contract",
            "timestamp": datetime.now().isoformat(),
        },
        tags=["c2pro", "test", "workflow"],
        project_name=project_name,
    )

    print(f"[INFO] Created parent run: {parent_run.id}")

    # Simulate sub-steps as child runs
    steps = [
        ("N1_Document_Ingestion", "tool", {"document_size": 1024}),
        ("N2_PII_Anonymizer", "tool", {"pii_found": 3, "strategy": "REDACT"}),
        ("N3_Router", "tool", {"intent": "contract_analysis", "confidence": 0.95}),
        ("N4_Risk_Extractor", "llm", {"risks_found": 5}),
        ("N8_Coherence_Scorer", "llm", {"score": 85.5}),
        ("N16_Final_Assembler", "tool", {"output_size": 2048}),
    ]

    for step_name, run_type, outputs in steps:
        child_run = parent_run.create_child(
            name=step_name,
            run_type=run_type,
            inputs={"step": step_name},
        )
        print(f"[INFO]   Created child run: {step_name}")
        child_run.end(outputs=outputs)

    # End parent run
    parent_run.end(
        outputs={
            "status": "completed",
            "coherence_score": 85.5,
            "risks_extracted": 5,
            "execution_time_ms": 1234,
        }
    )

    # Post the trace to LangSmith
    parent_run.post()

    print(f"[SUCCESS] Trace completed: {parent_run.id}")
    print("[INFO] View at: https://smith.langchain.com/")

    return parent_run.id


async def generate_orchestration_trace():
    """Generate a trace by invoking a simple LangGraph workflow."""
    from typing import TypedDict

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, StateGraph

    # Simple state for demonstration
    class SimpleState(TypedDict, total=False):
        input: str
        processed: bool
        output: str

    # Define simple nodes
    def process_input(state: SimpleState) -> SimpleState:
        state["processed"] = True
        state["output"] = f"Processed: {state.get('input', 'no input')}"
        return state

    # Build simple graph
    workflow = StateGraph(SimpleState)
    workflow.add_node("process", process_input)
    workflow.set_entry_point("process")
    workflow.add_edge("process", END)

    app = workflow.compile(checkpointer=MemorySaver())

    # Run with tracing config
    thread_id = f"trace-test-{uuid4().hex[:8]}"
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "C2Pro_Simple_Test",
        "tags": ["c2pro", "test", "simple"],
        "metadata": {
            "test_type": "trace_generation",
            "timestamp": datetime.now().isoformat(),
        },
    }

    result = await app.ainvoke(
        {"input": "Test document for LangSmith trace generation"},
        config,
    )

    print("[SUCCESS] LangGraph trace generated")
    print(f"[INFO] Result: {result}")

    return thread_id


async def main():
    """Main entry point."""
    print("=" * 60)
    print("C2Pro LangSmith Trace Generator")
    print("=" * 60)

    # Check environment
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
    api_key = os.getenv("LANGSMITH_API_KEY", "")
    project = os.getenv("LANGSMITH_PROJECT", "default")

    print(f"\n[CONFIG] LANGCHAIN_TRACING_V2: {tracing_enabled}")
    print(f"[CONFIG] LANGSMITH_PROJECT: {project}")
    print(f"[CONFIG] LANGSMITH_API_KEY: {'***' + api_key[-8:] if len(api_key) > 8 else '(not set)'}")

    if not tracing_enabled:
        print("\n[WARNING] LANGCHAIN_TRACING_V2 is not set to 'true'")
        print("[WARNING] Traces may not be sent to LangSmith")

    if not api_key:
        print("\n[ERROR] LANGSMITH_API_KEY is not set")
        print("[ERROR] Cannot generate traces without API key")
        sys.exit(1)

    print("\n" + "-" * 60)
    print("Generating traces...")
    print("-" * 60 + "\n")

    # Method 1: Direct LangSmith client
    print("[1/2] Generating direct LangSmith trace...")
    try:
        run_id = await generate_simple_trace()
        print(f"[1/2] Direct trace completed: {run_id}\n")
    except Exception as e:
        print(f"[1/2] Direct trace failed: {e}\n")

    # Method 2: LangGraph workflow
    print("[2/2] Generating LangGraph workflow trace...")
    try:
        thread_id = await generate_orchestration_trace()
        print(f"[2/2] LangGraph trace completed: {thread_id}\n")
    except Exception as e:
        print(f"[2/2] LangGraph trace failed: {e}\n")

    print("=" * 60)
    print("Trace generation complete!")
    print("View traces at: https://smith.langchain.com/")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
