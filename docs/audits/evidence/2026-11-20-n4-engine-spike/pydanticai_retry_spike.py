import asyncio, json
from typing import Literal
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart

class Finding(BaseModel):
    kind: Literal["risk","obligation","milestone","guarantee","penalty","payment_term","exclusion"]
    title: str
    source_quote: str = Field(min_length=1)

class WindowOut(BaseModel):
    window_examined: bool
    findings: list[Finding]
    outstanding_references: list[str]

def run(bad: bool, retries: int):
    calls = {"n": 0}
    def model(messages, info: AgentInfo):
        calls["n"] += 1
        tool = info.output_tools[0].name
        args = {"window_examined": True, "findings": [{"kind": "bogus" if bad else "risk", "title": "t", "source_quote": "q"}], "outstanding_references": []}
        return ModelResponse(parts=[ToolCallPart(tool, args)])
    kw = {} if retries is None else {'retries': retries}
    agent = Agent(FunctionModel(model), output_type=WindowOut, **kw)
    try:
        r = agent.run_sync("window text")
        return {"calls": calls["n"], "ok": True, "requests": (r.usage() if callable(r.usage) else r.usage).requests}
    except Exception as e:
        return {"calls": calls["n"], "ok": False, "error": type(e).__name__}

print("valid, retries=1:", run(False, 1))
print("invalid, retries=None (library default):", run(True, None))
print("invalid, retries=1:", run(True, 1))
print("invalid, retries=0:", run(True, 0))
