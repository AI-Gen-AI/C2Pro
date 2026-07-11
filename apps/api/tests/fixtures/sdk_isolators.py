"""
TASK-QA-206: Autouse SDK-isolator fixtures extracted from conftest.py.

These fixtures prevent external SDK HTTP calls from leaking during tests and
ensure Prometheus metrics are clean between test functions. They are loaded
by conftest.py via pytest_plugins and apply to the entire test session.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# LangSmith / LangChain SDK isolation (autouse — every test)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_langsmith_and_langchain_sdks(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """TS-AI-LANGSMITH-VALIDATION-FIXTURE: Prevent external SDK HTTP leakage during tests."""
    import langsmith
    import langsmith.run_helpers
    import langsmith.run_trees
    import langsmith.utils
    import langsmith.schemas
    try:
        import langchain
    except ImportError:
        langchain = None

    sdk_client = mock.MagicMock(name="langsmith_client")
    isolated_tracing_context = {"parent": None, "project_name": None, "enabled": False, "metadata": {}, "tags": []}

    # Patch precise attributes on the real langsmith package/submodules directly
    monkeypatch.setattr(langsmith, "Client", mock.MagicMock(return_value=sdk_client), raising=False)
    monkeypatch.setattr(langsmith, "RunTree", mock.MagicMock, raising=False)
    monkeypatch.setattr(langsmith, "get_tracing_context", mock.MagicMock(return_value=isolated_tracing_context), raising=False)

    monkeypatch.setattr(langsmith.run_helpers, "get_tracing_context", mock.MagicMock(return_value=isolated_tracing_context), raising=False)
    monkeypatch.setattr(langsmith.run_helpers, "tracing_context", mock.MagicMock(), raising=False)
    monkeypatch.setattr(langsmith.run_helpers, "get_current_run_tree", mock.MagicMock(), raising=False)

    monkeypatch.setattr(langsmith.run_trees, "RunTree", mock.MagicMock, raising=False)

    monkeypatch.setattr(langsmith.utils, "get_tracer_project", mock.MagicMock(return_value="test"), raising=False)
    monkeypatch.setattr(langsmith.utils, "tracing_is_enabled", mock.MagicMock(return_value=False), raising=False)

    monkeypatch.setattr(langsmith.schemas, "Run", mock.MagicMock, raising=False)

    langchain_hub = mock.MagicMock(name="langchain_hub")
    if langchain is not None:
        monkeypatch.setattr(langchain, "hub", langchain_hub, raising=False)

    # Neutralize any langchain_core / langgraph tracer context parent KeyError or flakiness
    monkeypatch.setattr(
        "langchain_core.tracers.context._get_tracer_project",
        lambda *_args, **_kwargs: "c2pro-test",
        raising=False,
    )
    monkeypatch.setattr(
        "langchain_core.tracers.context._tracing_v2_is_enabled",
        lambda *_args, **_kwargs: False,
        raising=False,
    )
    monkeypatch.setattr(
        "langchain_core.callbacks.manager._get_tracer_project",
        lambda *_args, **_kwargs: "c2pro-test",
        raising=False,
    )

    return SimpleNamespace(langsmith_client=sdk_client, langchain_hub=langchain_hub)


# ---------------------------------------------------------------------------
# Tenant-isolation middleware mock (autouse — prevents DB access in middleware)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_lookup_tenant_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the tenant lookup in the middleware to prevent db access."""
    with mock.patch(
        "src.core.middleware.tenant_isolation.lookup_tenant_by_id",
        new_callable=mock.AsyncMock,
    ) as mocked:
        mocked.return_value = SimpleNamespace(is_active=True)
        yield


# ---------------------------------------------------------------------------
# Prometheus registry cleanup (autouse — avoids duplicate metric errors)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function", autouse=True)
def clear_prometheus_registry() -> None:
    """Clear the Prometheus registry before each test to avoid duplicate metrics."""
    from prometheus_client import REGISTRY, gc_collector, platform_collector, process_collector

    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        REGISTRY.unregister(collector)

    process_collector.ProcessCollector(registry=REGISTRY)
    platform_collector.PlatformCollector(registry=REGISTRY)
    gc_collector.GCCollector(registry=REGISTRY)


# ---------------------------------------------------------------------------
# Celery stub — prevent Celery imports from failing in test environments
# ---------------------------------------------------------------------------


def _install_celery_stub() -> None:
    """Patch sys.modules with a minimal Celery stub before any import."""
    if "celery" in sys.modules:
        return

    class _DummyConf(dict):
        def __getattr__(self, name: str):  # noqa: ANN001
            return self.get(name)

        def __setattr__(self, name: str, value: object) -> None:
            self[name] = value

    class _DummyCelery:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.conf = _DummyConf()

        def task(self, *args: object, **kwargs: object):  # noqa: ANN201
            def decorator(fn):  # noqa: ANN001, ANN202
                fn.delay = lambda *a, **k: SimpleNamespace(id="test-task")
                return fn

            return decorator

        def start(self) -> None:
            return None

    sys.modules["celery"] = SimpleNamespace(Celery=_DummyCelery)  # type: ignore[assignment]


_install_celery_stub()
