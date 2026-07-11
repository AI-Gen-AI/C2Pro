"""TS-INF-PERF-056-002: Perf benchmark tracing isolation helpers."""

from __future__ import annotations

import asyncio
import contextvars
import os
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from typing import TypeVar

import pytest

os.environ.setdefault("LANGCHAIN_CALLBACKS_BACKGROUND", "false")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("C2PRO_AI_MOCK", "1")

T = TypeVar("T")


def run_async_benchmark_round(factory: Callable[[], Awaitable[T]]) -> T:
    """
    TS-INF-PERF-056-002: Run one async benchmark round in a fresh loop and context.

    pytest-benchmark invokes the measured callable repeatedly inside one pytest
    item. LangChain/LangSmith tracing stores parent-run state in contextvars, so
    each benchmark round gets a clean context boundary.
    """
    loop = asyncio.new_event_loop()
    try:
        return contextvars.copy_context().run(loop.run_until_complete, factory())
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def disable_langchain_tracing_for_perf(monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-INF-PERF-056-002: Disable LangChain/LangSmith callbacks for perf tests."""
    monkeypatch.setenv("LANGCHAIN_CALLBACKS_BACKGROUND", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("C2PRO_AI_MOCK", "1")

    try:
        from langsmith import run_helpers as langsmith_run_helpers
        from langsmith import utils as langsmith_utils

        monkeypatch.setattr(
            langsmith_run_helpers,
            "get_tracing_context",
            lambda: {"parent": None, "project_name": None, "enabled": False, "metadata": {}, "tags": []},
            raising=False,
        )
        monkeypatch.setattr(langsmith_utils, "tracing_is_enabled", lambda: False, raising=False)
    except Exception:
        pass

    try:
        from langchain_core.tracers import context as langchain_tracing_context

        @contextmanager
        def _disabled_tracing_v2(*args: object, **kwargs: object):
            yield None

        monkeypatch.setattr(
            langchain_tracing_context,
            "_tracing_v2_is_enabled",
            lambda: False,
            raising=False,
        )
        monkeypatch.setattr(
            langchain_tracing_context,
            "tracing_v2_enabled",
            _disabled_tracing_v2,
            raising=False,
        )
    except Exception:
        pass

    try:
        from src.core.ai.langsmith_client import get_client

        get_client.cache_clear()
    except Exception:
        pass
