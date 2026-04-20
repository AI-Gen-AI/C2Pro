"""TS-AI-LANGSMITH-002: Decorator for standardized LLM tracing metadata."""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, ParamSpec, Protocol, TypeVar
from uuid import uuid4

from src.core.ai.langsmith_client import LangSmithClient

P = ParamSpec("P")
R = TypeVar("R")


class _SpanClient(Protocol):
    """TS-AI-LANGSMITH-002: Minimal span client contract used by tracing wrapper."""

    def start_span(
        self,
        name: str,
        input: dict[str, Any] | None = None,
        run_type: str = "llm",
        **kwargs: Any,
    ) -> Any: ...

    def end_span(self, span: Any, outputs: dict[str, Any] | None = None) -> None: ...


def _extract_span_client(call_args: tuple[Any, ...], call_kwargs: dict[str, Any]) -> _SpanClient | None:
    explicit = call_kwargs.get("langsmith_client")
    if explicit is not None:
        return explicit

    if call_args:
        owner = call_args[0]
        owner_client = getattr(owner, "langsmith_client", None)
        if owner_client is not None:
            return owner_client

    return None


def _extract_tenant_id(call_kwargs: dict[str, Any]) -> str | None:
    tenant = call_kwargs.get("tenant_id")
    if tenant is None:
        return None
    return str(tenant)


def traced_llm_call(
    *,
    task_type: str,
    span_name: str | None = None,
    run_type: str = "llm",
    extra_tags: list[str] | None = None,
    client: LangSmithClient | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """TS-AI-LANGSMITH-002: Trace LLM calls with canonical tags and metadata payloads."""

    resolved_client = client or LangSmithClient()

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        name = span_name or func.__name__

        async def _run_async(*args: P.args, **kwargs: P.kwargs) -> Any:
            span_client = _extract_span_client(args, kwargs)
            request_id = str(kwargs.get("request_id") or uuid4())
            tenant_id = _extract_tenant_id(kwargs)
            span = None

            if resolved_client.enabled and span_client is not None:
                tags = resolved_client.build_tags(
                    task_type=task_type,
                    tenant_id=tenant_id,
                    extra_tags=extra_tags,
                )
                metadata = resolved_client.build_metadata(
                    request_id=request_id,
                    tenant_id=tenant_id,
                    task_type=task_type,
                    extra={"span_name": name, "function_name": func.__name__},
                )
                span = span_client.start_span(
                    name=name,
                    input={"args_count": len(args), "kwargs": list(kwargs.keys())},
                    run_type=run_type,
                    tags=tags,
                    metadata=metadata,
                )

            try:
                result = await func(*args, **kwargs)
            except Exception as exc:
                if span_client is not None and span is not None:
                    span_client.end_span(span, outputs={"status": "error", "error": str(exc)})
                raise

            if span_client is not None and span is not None:
                span_client.end_span(span, outputs={"status": "success"})

            return result

        def _run_sync(*args: P.args, **kwargs: P.kwargs) -> Any:
            span_client = _extract_span_client(args, kwargs)
            request_id = str(kwargs.get("request_id") or uuid4())
            tenant_id = _extract_tenant_id(kwargs)
            span = None

            if resolved_client.enabled and span_client is not None:
                tags = resolved_client.build_tags(
                    task_type=task_type,
                    tenant_id=tenant_id,
                    extra_tags=extra_tags,
                )
                metadata = resolved_client.build_metadata(
                    request_id=request_id,
                    tenant_id=tenant_id,
                    task_type=task_type,
                    extra={"span_name": name, "function_name": func.__name__},
                )
                span = span_client.start_span(
                    name=name,
                    input={"args_count": len(args), "kwargs": list(kwargs.keys())},
                    run_type=run_type,
                    tags=tags,
                    metadata=metadata,
                )

            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                if span_client is not None and span is not None:
                    span_client.end_span(span, outputs={"status": "error", "error": str(exc)})
                raise

            if span_client is not None and span is not None:
                span_client.end_span(span, outputs={"status": "success"})

            return result

        runner = _run_async if inspect.iscoroutinefunction(func) else _run_sync
        wrapped = functools.wraps(func)(runner)
        return wrapped  # type: ignore[return-value]

    return decorator
