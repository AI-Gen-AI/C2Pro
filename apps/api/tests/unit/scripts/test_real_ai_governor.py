"""The real-AI call governor: the hard cap on provider calls and spend. No network, no key: the SDK transport is faked.

Every case runs in a SUBPROCESS: ``install()`` rewrites SDK classes for the whole interpreter, which must never leak into the
rest of the test session. an explicit PYTHONPATH reproduces what the API and the worker see.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

GOVERNOR_DIR = Path(__file__).resolve().parents[3] / "scripts" / "real_ai_governor"

PRELUDE = r"""
import json, os, sys
from types import SimpleNamespace
import anthropic
from anthropic.resources.messages import AsyncMessages, Messages
SENT = []
def fake_create(self, *a, **kw):
    if os.environ.get("TEST_PROVIDER_DOWN"):
        raise TimeoutError("provider down")
    SENT.append(kw)
    return SimpleNamespace(id=f"msg_fake_{len(SENT)}", model=kw["model"], stop_reason="end_turn",
                           usage=SimpleNamespace(input_tokens=1000, output_tokens=500), content=[])
Messages.create = fake_create
async def fake_acreate(self, *a, **kw):
    return fake_create(self, *a, **kw)
AsyncMessages.create = fake_acreate
import real_ai_governor as g
assert g.install() is True
c = anthropic.Anthropic(api_key="not-a-key")
def call(model="claude-haiku-4-5-20251001", max_tokens=1000):
    return c.messages.create(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": "x"}])
out = {}
"""


def run(body: str, tmp_path: Path, **env: str) -> dict:
    environment = {
        "PATH": os.environ["PATH"], "HOME": str(tmp_path), "PYTHONPATH": str(GOVERNOR_DIR),
        "C2PRO_AI_GOVERNOR_LEDGER": str(tmp_path / "ledger.jsonl"), "RUNNER_TEMP": str(tmp_path),
    }
    environment.update(env)
    code = PRELUDE + body + "\nprint('RESULT=' + json.dumps(out))\n"
    done = subprocess.run([sys.executable, "-s", "-c", code], capture_output=True, text=True, env=environment, timeout=120, check=False)
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout.split("RESULT=")[-1])


LIMITS = {"C2PRO_AI_GOVERNOR_MAX_CALLS": "3", "C2PRO_AI_GOVERNOR_MAX_USD": "1.00"}


def test_calls_within_the_cap_are_recorded_with_the_provider_message_id_and_cost(tmp_path: Path) -> None:
    out = run("call(); call(); out['summary'] = g.summarize(g.read_events(g._limits()[0])); out['sent'] = len(SENT)", tmp_path, **LIMITS)
    assert out["sent"] == 2 and out["summary"]["calls"] == 2 and out["summary"]["completed"] == 2
    assert out["summary"]["message_ids"] == ["msg_fake_1", "msg_fake_2"]
    assert out["summary"]["input_tokens"] == 2000 and out["summary"]["output_tokens"] == 1000
    assert out["summary"]["spent_usd"] == round(2 * (1000 * 1.0 + 500 * 5.0) / 1_000_000, 6)


def test_the_call_cap_refuses_the_next_call_before_it_reaches_the_provider(tmp_path: Path) -> None:
    out = run(
        "call(); call(); call()\n"
        "try:\n    call()\nexcept g.GovernorRefusal as e:\n    out['refusal'] = str(e)\n"
        "out['sent'] = len(SENT)",
        tmp_path, **LIMITS,
    )
    assert out["sent"] == 3, "the fourth call never reached the transport"
    assert out["refusal"].startswith("GOVERNOR_CALL_CAP")


def test_the_budget_cap_uses_the_worst_case_of_the_call_not_only_what_was_already_spent(tmp_path: Path) -> None:
    # An Opus call asking for 8192 output tokens is worth ~$0.20 in the worst case: refused under a $0.05 budget BEFORE any spend.
    out = run(
        "try:\n    call(model='claude-opus-4-7', max_tokens=8192)\nexcept g.GovernorRefusal as e:\n    out['refusal'] = str(e)\n"
        "out['sent'] = len(SENT)",
        tmp_path, C2PRO_AI_GOVERNOR_MAX_CALLS="10", C2PRO_AI_GOVERNOR_MAX_USD="0.05",
    )
    assert out["sent"] == 0 and out["refusal"].startswith("GOVERNOR_BUDGET_CAP")


def test_it_fails_closed_when_a_limit_is_missing(tmp_path: Path) -> None:
    out = run(
        "try:\n    call()\nexcept g.GovernorRefusal as e:\n    out['refusal'] = str(e)\nout['sent'] = len(SENT)",
        tmp_path, C2PRO_AI_GOVERNOR_MAX_CALLS="3",  # no budget
    )
    assert out["sent"] == 0 and out["refusal"].startswith("GOVERNOR_LIMITS_MISSING_OR_MALFORMED")


def test_sdk_retries_are_forced_off_and_streaming_is_refused(tmp_path: Path) -> None:
    out = run(
        "k = anthropic.Anthropic(api_key='x', max_retries=5)\nout['retries'] = k.max_retries\n"
        "try:\n    k.messages.stream(model='m', max_tokens=1, messages=[])\nexcept g.GovernorRefusal as e:\n    out['stream'] = str(e)\n",
        tmp_path, **LIMITS,
    )
    assert out["retries"] == 0 and out["stream"].startswith("GOVERNOR_STREAMING")


def test_a_failed_call_is_counted_and_its_reservation_released(tmp_path: Path) -> None:
    out = run(
        "try:\n    call()\nexcept TimeoutError:\n    pass\nout['summary'] = g.summarize(g.read_events(g._limits()[0]))",
        tmp_path, TEST_PROVIDER_DOWN="1", **LIMITS,
    )
    assert out["summary"]["calls"] == 1 and out["summary"]["failed"] == 1 and out["summary"]["in_flight"] == 0
    assert out["summary"]["spent_usd"] == 0


def test_the_governor_is_inert_without_a_ledger_variable(tmp_path: Path) -> None:
    code = "import real_ai_governor as g; print(g.install())"
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "PYTHONPATH": str(GOVERNOR_DIR)}
    done = subprocess.run([sys.executable, "-s", "-c", code], capture_output=True, text=True, env=env, timeout=60, check=False)
    assert done.returncode == 0 and done.stdout.strip() == "False"


def test_sitecustomize_installs_it_in_a_fresh_interpreter_exactly_as_the_api_and_the_worker_get_it(tmp_path: Path) -> None:
    code = "from anthropic.resources.messages import Messages; print(getattr(Messages.create, '_c2pro_governed', False))"
    env = {
        "PATH": os.environ["PATH"], "HOME": str(tmp_path), "PYTHONPATH": str(GOVERNOR_DIR),
        "C2PRO_AI_GOVERNOR_LEDGER": str(tmp_path / "l.jsonl"), "RUNNER_TEMP": str(tmp_path), **LIMITS,
    }
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=60, check=False)
    assert done.returncode == 0, done.stderr[-500:]
    assert done.stdout.strip() == "True"


def test_the_ledger_must_be_a_jsonl_file_inside_the_runner_directories(tmp_path: Path) -> None:
    out = run(
        "try:\n    call()\nexcept g.GovernorRefusal as e:\n    out['refusal'] = str(e)\nout['sent'] = len(SENT)",
        tmp_path, C2PRO_AI_GOVERNOR_LEDGER="/etc/passwd", **LIMITS,
    )
    assert out["sent"] == 0 and out["refusal"].startswith("GOVERNOR_LEDGER_PATH_NOT_ALLOWED")
