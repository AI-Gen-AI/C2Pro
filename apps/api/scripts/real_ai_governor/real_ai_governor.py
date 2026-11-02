"""Call governor for the real-AI functional pilot: a HARD cap on provider calls and spend, at the SDK boundary.

Why here and not a flag: ``C2PRO_AI_MOCK=0`` switches EVERY AI-capable node of the product to the real provider (extraction,
critique, classifiers, coherence gates, ...), and each of them reaches Anthropic through a different wrapper. The one place all
of them share is ``anthropic``'s ``Messages.create``. This module wraps it, in every process that has the governor on its
``PYTHONPATH`` (API and Celery worker), and enforces, across processes, through one append-only ledger file:

* a maximum NUMBER of provider calls (``C2PRO_AI_GOVERNOR_MAX_CALLS``);
* a maximum SPEND in USD (``C2PRO_AI_GOVERNOR_MAX_USD``), checked BEFORE each call against actual spend + calls in flight +
  this call's worst case (input estimated pessimistically, output = the requested ``max_tokens``);
* no SDK-level retries (``max_retries`` is forced to 0: a retry is another billed request the ledger could not see);
* no streaming and no embeddings provider (both refused: neither is part of the experiment).

Fail closed: if the governor is active but a limit is missing or malformed, EVERY call is refused. Nothing is stored but
counts, tokens, model names, the provider's message id and cost: no prompt, no completion.

The ledger is the "registro del consumo": one JSON object per line, ``reserve`` -> ``done``/``fail`` (or ``refused``).
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ENV_LEDGER = "C2PRO_AI_GOVERNOR_LEDGER"
ENV_MAX_CALLS = "C2PRO_AI_GOVERNOR_MAX_CALLS"
ENV_MAX_USD = "C2PRO_AI_GOVERNOR_MAX_USD"

# USD per million tokens (input, output). An unknown model is priced as the most expensive known one.
PRICES: tuple[tuple[str, float, float], ...] = (
    ("haiku", 1.0, 5.0),
    ("sonnet", 3.0, 15.0),
    ("opus", 5.0, 25.0),
)
_UNKNOWN_PRICE = (5.0, 25.0)


class GovernorRefusal(RuntimeError):
    """The call was refused BEFORE reaching the provider (nothing was sent, nothing was billed)."""


def price_of(model: str) -> tuple[float, float]:
    lowered = (model or "").lower()
    for needle, price_in, price_out in PRICES:
        if needle in lowered:
            return price_in, price_out
    return _UNKNOWN_PRICE


def usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = price_of(model)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def _allowed_roots() -> list[Path]:
    roots = [os.environ.get("RUNNER_TEMP", ""), os.environ.get("GITHUB_WORKSPACE", ""), tempfile.gettempdir()]
    return [Path(r).resolve() for r in roots if r]


def _checked_ledger(raw: str) -> Path:
    """The ledger is a ``.jsonl`` file inside the runner's workspace or temp directory: an environment value never names an arbitrary file."""
    path = Path(raw).resolve()
    if path.suffix != ".jsonl" or not any(path.is_relative_to(root) for root in _allowed_roots()):
        raise GovernorRefusal("GOVERNOR_LEDGER_PATH_NOT_ALLOWED: a .jsonl file under the workspace or the temp directory is required")
    return path


def _limits() -> tuple[Path, int, float]:
    raw_ledger = os.environ.get(ENV_LEDGER, "")
    try:
        calls = int(os.environ[ENV_MAX_CALLS])
        budget = float(os.environ[ENV_MAX_USD])
    except (KeyError, ValueError) as exc:
        raise GovernorRefusal(f"GOVERNOR_LIMITS_MISSING_OR_MALFORMED: set {ENV_MAX_CALLS} and {ENV_MAX_USD}") from exc
    if not raw_ledger or calls < 1 or budget <= 0:
        raise GovernorRefusal("GOVERNOR_LIMITS_INVALID: ledger, calls >= 1 and budget > 0 are required")
    return _checked_ledger(raw_ledger), calls, budget


@contextmanager
def _locked(ledger: Path):
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger.with_suffix(ledger.suffix + ".lock"), "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def read_events(ledger: Path) -> list[dict[str, Any]]:
    if not ledger.exists():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append(ledger: Path, event: dict[str, Any]) -> None:
    with open(ledger, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    reserves = {e["id"]: e for e in events if e["ev"] == "reserve"}
    done = {e["id"]: e for e in events if e["ev"] == "done"}
    failed = {e["id"] for e in events if e["ev"] == "fail"}
    open_ids = [i for i in reserves if i not in done and i not in failed]
    return {
        "calls": len(reserves),
        "completed": len(done),
        "failed": len(failed),
        "in_flight": len(open_ids),
        "spent_usd": round(sum(float(e["usd"]) for e in done.values()), 6),
        "reserved_open_usd": round(sum(float(reserves[i]["est_usd"]) for i in open_ids), 6),
        "refused": [e["reason"] for e in events if e["ev"] == "refused"],
        "models": sorted({str(e["model"]) for e in done.values()}),
        "input_tokens": sum(int(e["in"]) for e in done.values()),
        "output_tokens": sum(int(e["out"]) for e in done.values()),
        "message_ids": [str(e["message_id"]) for e in done.values()],
    }


def reserve(model: str, estimated_input_tokens: int, max_output_tokens: int) -> str:
    """Admit one call or refuse it. Returns the reservation id."""
    try:
        ledger, max_calls, budget = _limits()
    except GovernorRefusal as exc:
        try:  # best effort: record the refusal where the ledger is valid; the call is refused either way
            ledger = _checked_ledger(os.environ.get(ENV_LEDGER, ""))
            with _locked(ledger):
                _append(ledger, {"ev": "refused", "t": time.time(), "reason": str(exc)})
        except GovernorRefusal:
            pass
        raise
    estimate = usd(model, estimated_input_tokens, max_output_tokens)
    with _locked(ledger):
        state = summarize(read_events(ledger))
        reason = None
        if state["calls"] >= max_calls:
            reason = f"GOVERNOR_CALL_CAP: {state['calls']} call(s) already admitted, cap {max_calls}"
        elif state["spent_usd"] + state["reserved_open_usd"] + estimate > budget:
            reason = (
                f"GOVERNOR_BUDGET_CAP: spent {state['spent_usd']:.4f} + in flight {state['reserved_open_usd']:.4f} "
                f"+ this call's worst case {estimate:.4f} would exceed {budget:.2f} USD"
            )
        if reason:
            _append(ledger, {"ev": "refused", "t": time.time(), "reason": reason, "model": model})
            raise GovernorRefusal(reason)
        call_id = uuid.uuid4().hex
        _append(ledger, {"ev": "reserve", "id": call_id, "t": time.time(), "model": model, "est_usd": round(estimate, 6), "pid": os.getpid()})
    return call_id


def settle(call_id: str, response: Any, model: str) -> None:
    ledger, _, _ = _limits()
    usage = getattr(response, "usage", None)
    tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
    tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
    with _locked(ledger):
        _append(
            ledger,
            {
                "ev": "done", "id": call_id, "t": time.time(), "model": getattr(response, "model", None) or model,
                "message_id": getattr(response, "id", None), "stop_reason": getattr(response, "stop_reason", None),
                "in": tokens_in, "out": tokens_out, "usd": round(usd(getattr(response, "model", None) or model, tokens_in, tokens_out), 6),
            },
        )


def fail(call_id: str, error: BaseException) -> None:
    ledger, _, _ = _limits()
    with _locked(ledger):
        _append(ledger, {"ev": "fail", "id": call_id, "t": time.time(), "error": type(error).__name__})


def _estimate_input_tokens(kwargs: dict[str, Any]) -> int:
    body = json.dumps({"system": kwargs.get("system"), "messages": kwargs.get("messages"), "tools": kwargs.get("tools")}, default=str)
    return max(1, len(body) // 3)  # pessimistic: real text averages ~4 characters per token


def _max_tokens(kwargs: dict[str, Any]) -> int:
    value = kwargs.get("max_tokens")
    return int(value) if isinstance(value, int) and value > 0 else 8192


def install() -> bool:
    """Wrap the provider boundary in THIS process. Idempotent. Returns True when the governor is active."""
    if not os.environ.get(ENV_LEDGER):
        return False
    try:
        import anthropic
        from anthropic.resources.messages import AsyncMessages, Messages
    except ImportError:  # no SDK in this interpreter: nothing to govern
        return False
    if getattr(Messages.create, "_c2pro_governed", False):
        return True

    original_sync, original_async = Messages.create, AsyncMessages.create

    def governed_sync(self: Any, *args: Any, **kwargs: Any) -> Any:
        model = str(kwargs.get("model", ""))
        call_id = reserve(model, _estimate_input_tokens(kwargs), _max_tokens(kwargs))
        try:
            response = original_sync(self, *args, **kwargs)
        except BaseException as exc:
            fail(call_id, exc)
            raise
        settle(call_id, response, model)
        return response

    async def governed_async(self: Any, *args: Any, **kwargs: Any) -> Any:
        model = str(kwargs.get("model", ""))
        call_id = reserve(model, _estimate_input_tokens(kwargs), _max_tokens(kwargs))
        try:
            response = await original_async(self, *args, **kwargs)
        except BaseException as exc:
            fail(call_id, exc)
            raise
        settle(call_id, response, model)
        return response

    governed_sync._c2pro_governed = True  # type: ignore[attr-defined]
    governed_async._c2pro_governed = True  # type: ignore[attr-defined]
    Messages.create = governed_sync  # type: ignore[method-assign]
    AsyncMessages.create = governed_async  # type: ignore[method-assign]

    def refuse_stream(*_args: Any, **_kwargs: Any) -> Any:
        raise GovernorRefusal("GOVERNOR_STREAMING_NOT_PART_OF_THE_EXPERIMENT")

    Messages.stream = refuse_stream  # type: ignore[method-assign]
    AsyncMessages.stream = refuse_stream  # type: ignore[method-assign]

    for client_class in (anthropic.Anthropic, anthropic.AsyncAnthropic):
        original_init = client_class.__init__

        def init_without_retries(self: Any, *args: Any, __orig: Any = original_init, **kwargs: Any) -> None:
            kwargs["max_retries"] = 0  # a retry is another billed request the ledger would not see
            __orig(self, *args, **kwargs)

        client_class.__init__ = init_without_retries  # type: ignore[method-assign]

    try:  # the experiment keeps embeddings mocked; make a real embeddings provider impossible, not just unconfigured
        from openai.resources.embeddings import AsyncEmbeddings, Embeddings

        def refuse_embeddings(*_args: Any, **_kwargs: Any) -> Any:
            raise GovernorRefusal("GOVERNOR_EMBEDDINGS_PROVIDER_NOT_PART_OF_THE_EXPERIMENT")

        Embeddings.create = refuse_embeddings  # type: ignore[method-assign]
        AsyncEmbeddings.create = refuse_embeddings  # type: ignore[method-assign]
    except ImportError:
        pass
    return True
