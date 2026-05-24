"""TS-AI-LANGSMITH-002: Decorator for standardized LLM tracing metadata."""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, ParamSpec, Protocol, TypeVar
from uuid import uuid4

from src.core.ai.langsmith_client import LangSmithClient
from src.core.ai.usage_logger import AIUsageLogRecord

P = ParamSpec("P")
R = TypeVar("R")


class _SpanClient(Protocol):
    """TS-AI-LANGSMITH-002: Minimal span client contract used by tracing wrapper."""

    def start_span(
        self,
        name: str,
        inputs: dict[str, Any] | None = None,
        run_type: str = "llm",
        **kwargs: Any,
    ) -> Any: ...

    def end_span(self, span: Any, outputs: dict[str, Any] | None = None) -> None: ...


_TRACE_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar("trace_context", default=None)


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


def _extract_usage_logger(call_args: tuple[Any, ...], call_kwargs: dict[str, Any]) -> Any | None:
    explicit = call_kwargs.get("usage_logger")
    if explicit is not None:
        return explicit
    if call_args:
        owner = call_args[0]
        owner_logger = getattr(owner, "usage_logger", None)
        if owner_logger is not None:
            return owner_logger
    return None


def _get_request_from_args(args: tuple[Any, ...]) -> Any | None:
    if len(args) > 1 and hasattr(args[1], "__class__"):
        # Assuming the request object is the second argument
        return args[1]
    return None


def _extract_tenant_id(call_kwargs: dict[str, Any], request: Any | None = None) -> str | None:
    tenant = call_kwargs.get("tenant_id")
    if tenant is not None:
        return str(tenant)
    if request and hasattr(request, "tenant_id"):
        return str(request.tenant_id)
    return None


def _extract_prompt(call_kwargs: dict[str, Any], request: Any | None = None) -> str | None:
    for key in ("prompt", "rendered_prompt", "input_prompt"):
        value = call_kwargs.get(key)
        if isinstance(value, str):
            return value
    if request and hasattr(request, "system"):
        return request.system
    return None


def _extract_model_name(call_kwargs: dict[str, Any], result: Any | None = None, request: Any | None = None) -> str | None:
    for source in (call_kwargs, result if isinstance(result, dict) else None):
        if source is None:
            continue
        model_name = source.get("model_name")
        if model_name:
            return str(model_name)
    if request and hasattr(request, "model"):
        return request.model
    return None


def _extract_model_params(call_kwargs: dict[str, Any], request: Any | None = None) -> dict[str, Any]:
    model_params = call_kwargs.get("model_params")
    if isinstance(model_params, dict):
        return model_params

    extracted: dict[str, Any] = {}
    if request:
        for key in ("temperature", "max_tokens", "top_p", "top_k"):
            if hasattr(request, key):
                value = getattr(request, key)
                if value is not None:
                    extracted[key] = value

    for key in ("temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty"):
        if key in call_kwargs:
            extracted[key] = call_kwargs[key]
    return extracted


def _extract_request_id(call_kwargs: dict[str, Any], request: Any | None = None) -> str:
    request_id = call_kwargs.get("request_id")
    if request_id:
        return str(request_id)
    if request and hasattr(request, "request_id"):
        return str(request.request_id)
    return str(uuid4())



def _extract_usage_metrics(result: Any) -> dict[str, Any]:
    # Handle LLMResponse dataclass (primary production path)
    if hasattr(result, "input_tokens") and hasattr(result, "output_tokens"):
        return {
            "output": getattr(result, "content", None),
            "tokens_input": int(getattr(result, "input_tokens", 0)),
            "tokens_output": int(getattr(result, "output_tokens", 0)),
            "tokens_total": int(getattr(result, "input_tokens", 0)) + int(getattr(result, "output_tokens", 0)),
            "cost_usd": float(getattr(result, "cost_usd", 0.0)),
            "operation": None,
            "cached": bool(getattr(result, "cached", False)),
        }

    if not isinstance(result, dict):
        return {}

    usage = result.get("usage")
    if not isinstance(usage, dict):
        usage = {}

    return {
        "output": result.get("output") or result.get("completion") or result.get("text"),
        "tokens_input": usage.get("prompt_tokens", 0),
        "tokens_output": usage.get("completion_tokens", 0),
        "tokens_total": usage.get("total_tokens", 0),
        "cost_usd": result.get("cost_usd", 0.0),
        "operation": result.get("operation_type") or result.get("task_type"),
        "cached": bool(result.get("cached", False)),
    }


def _extract_trace_identifiers(span: Any, run_id: str | None = None) -> tuple[str | None, str | None]:
    trace_id = run_id
    trace_url = None
    if isinstance(span, dict):
        trace_id = trace_id or span.get("id") or span.get("run_id") or span.get("trace_id")
        trace_url = span.get("url") or span.get("trace_url")
    else:
        trace_id = trace_id or getattr(span, "id", None) or getattr(span, "run_id", None)
        trace_url = getattr(span, "url", None) or getattr(span, "trace_url", None)
    return (str(trace_id) if trace_id else None, str(trace_url) if trace_url else None)


def get_current_trace_context() -> dict[str, Any] | None:
    """TS-AI-LANGSMITH-013: Returns the current trace context for in-flight LLM call."""
    return _TRACE_CONTEXT.get()


def traced_llm_call(  # NOSONAR - legacy decorator intentionally wraps sync and async tracing paths.
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
            request_obj = _get_request_from_args(args)
            span_client = _extract_span_client(args, kwargs)
            usage_logger = _extract_usage_logger(args, kwargs)
            request_id = _extract_request_id(kwargs, request=request_obj)
            tenant_id = _extract_tenant_id(kwargs, request=request_obj)
            prompt = _extract_prompt(kwargs, request=request_obj)
            model_name = _extract_model_name(kwargs, request=request_obj)
            model_params = _extract_model_params(kwargs, request=request_obj)
            span = None
            run_id = None
            started_at = time.perf_counter()
            token = _TRACE_CONTEXT.set(None)

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
                    inputs={
                        "args_count": len(args),
                        "kwargs": list(kwargs.keys()),
                        "prompt": prompt,
                        "model_name": model_name,
                        "model_params": model_params,
                    },
                    run_type=run_type,
                    tags=tags,
                    metadata=metadata,
                )
                run_id = metadata.get("run_id")

            try:
                try:
                    result = await func(*args, **kwargs)
                except Exception as exc:
                    if span_client is not None and span is not None:
                        latency_ms = int((time.perf_counter() - started_at) * 1000)
                        span_client.end_span(
                            span,
                            outputs={
                                "status": "error",
                                "error": str(exc),
                                "latency_ms": latency_ms,
                            },
                        )
                    raise

                if span_client is not None and span is not None:
                    usage_metrics = _extract_usage_metrics(result)
                    usage_metrics["model_name"] = _extract_model_name(kwargs, result, request=request_obj)
                    usage_metrics["latency_ms"] = int((time.perf_counter() - started_at) * 1000)
                    span_client.end_span(span, outputs={"status": "success", **usage_metrics})
                    trace_id, trace_url = _extract_trace_identifiers(span, run_id=run_id)
                    _TRACE_CONTEXT.set({"trace_id": trace_id, "trace_url": trace_url, "latency_ms": usage_metrics["latency_ms"]})

                    tenant_uuid = getattr(request_obj, "tenant_id", None) or kwargs.get("tenant_id")
                    project_id = getattr(request_obj, "project_id", None) or kwargs.get("project_id")
                    prompt_version = getattr(request_obj, "prompt_version", None) or kwargs.get("prompt_version")

                    if usage_logger is not None and tenant_uuid is not None and trace_id:
                        await usage_logger.log_success(
                            AIUsageLogRecord(
                                tenant_id=tenant_uuid,
                                project_id=project_id,
                                model=usage_metrics.get("model_name") or "unknown",
                                operation=usage_metrics.get("operation") or task_type,
                                input_tokens=int(usage_metrics.get("tokens_input", 0)),
                                output_tokens=int(usage_metrics.get("tokens_output", 0)),
                                cost_usd=float(usage_metrics.get("cost_usd", 0.0)),
                                latency_ms=float(usage_metrics["latency_ms"]),
                                cached=bool(usage_metrics.get("cached", False)),
                                trace_id=trace_id,
                                trace_url=trace_url,
                                prompt_version=prompt_version,
                                metadata={"request_id": request_id},
                            )
                        )
                return result
            finally:
                _TRACE_CONTEXT.reset(token)

        def _run_sync(*args: P.args, **kwargs: P.kwargs) -> Any:
            request_obj = _get_request_from_args(args)
            span_client = _extract_span_client(args, kwargs)
            request_id = _extract_request_id(kwargs, request=request_obj)
            tenant_id = _extract_tenant_id(kwargs, request=request_obj)
            prompt = _extract_prompt(kwargs, request=request_obj)
            model_name = _extract_model_name(kwargs, request=request_obj)
            model_params = _extract_model_params(kwargs, request=request_obj)
            span = None
            started_at = time.perf_counter()
            token = _TRACE_CONTEXT.set(None)

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
                    inputs={
                        "args_count": len(args),
                        "kwargs": list(kwargs.keys()),
                        "prompt": prompt,
                        "model_name": model_name,
                        "model_params": model_params,
                    },
                    run_type=run_type,
                    tags=tags,
                    metadata=metadata,
                )

            try:
                try:
                    result = func(*args, **kwargs)
                except Exception as exc:
                    if span_client is not None and span is not None:
                        latency_ms = int((time.perf_counter() - started_at) * 1000)
                        span_client.end_span(
                            span,
                            outputs={
                                "status": "error",
                                "error": str(exc),
                                "latency_ms": latency_ms,
                            },
                        )
                    raise

                if span_client is not None and span is not None:
                    usage_metrics = _extract_usage_metrics(result)
                    usage_metrics["model_name"] = _extract_model_name(kwargs, result, request=request_obj)
                    usage_metrics["latency_ms"] = int((time.perf_counter() - started_at) * 1000)
                    span_client.end_span(span, outputs={"status": "success", **usage_metrics})
                    trace_id, trace_url = _extract_trace_identifiers(span)
                    _TRACE_CONTEXT.set({"trace_id": trace_id, "trace_url": trace_url, "latency_ms": usage_metrics["latency_ms"]})

                return result
            finally:
                _TRACE_CONTEXT.reset(token)

        runner = _run_async if inspect.iscoroutinefunction(func) else _run_sync
        wrapped = functools.wraps(func)(runner)
        return wrapped  # type: ignore[return-value]

    return decorator
