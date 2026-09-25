"""Contract-correct test doubles for the HITL resume boundary.

C2PRO P0b true-resume hotfix.

The doubles these replace modelled the OLD, BROKEN contract: a graph app
whose ``ainvoke`` ignored its first argument and simply called
``save_to_db_node`` on whatever ``aupdate_state`` had stashed. That shape
made a non-resuming implementation look perfectly healthy in tests -- it is
precisely why the production defect (approval recorded, workflow never
resumed, N17 never executed) shipped green.

These doubles instead mirror what the real compiled graph actually does,
verified empirically against langgraph 1.2.10 + a real AsyncPostgresSaver:

* resume happens via ``ainvoke(Command(resume=<payload>), config)``;
* the payload is what ``interrupt()`` returns inside the node, so the
  decision must be read FROM it (not from pre-injected state);
* an approval runs downstream (the REAL ``save_to_db_node``) and yields an
  ``analysis_id``; a rejection terminates and must NOT run N17;
* a resume that cannot proceed reports another ``__interrupt__`` rather
  than raising.

Anything that still needs the genuinely real graph should use a real
CompiledStateGraph -- see
tests/modules/integration/test_p0b_true_langgraph_resume_hotfix.py.
"""

from __future__ import annotations

from typing import Any

from src.modules.hitl.adapters.checkpoint_service import CheckpointRestore


def decision_from_resume(resume_signal: Any) -> tuple[str | None, str]:
    """Extract (decision, feedback) from a Command(resume=...) argument."""
    payload = getattr(resume_signal, "resume", resume_signal)
    if isinstance(payload, dict):
        return payload.get("decision"), payload.get("feedback", "") or ""
    if payload is None:
        return None, ""
    return str(payload), ""


class ResumeGraphDouble:
    """Fork/terminal/provenance behaviour shared by the HITL resume doubles.

    C2PRO P0b crash-safe HITL resume V3. The V2-era doubles modelled
    ``aupdate_state`` as "stash the whole state, then replay it", which is
    not what the real graph does and, worse, made three V3 contracts
    invisible to tests:

    * ``aupdate_state`` FORKS. It merges the update into the checkpoint's
      state and RETURNS the new config. V3 forks once per attempt because
      re-resuming a checkpoint re-delivers the FIRST attempt's payload
      (verified against langgraph 1.2.10 + AsyncPostgresSaver).
    * ``aget_state`` reports terminality. `ainvoke` returning is not
      evidence the graph finished, so it is the only thing the use case
      accepts before emitting ``graph.completed``.
    * the resumed node copies ``resume_provenance`` out of the interrupt
      payload into state -- which is what puts N17 on the FENCED path
      instead of the legacy unkeyed one.
    """

    async def aupdate_state(
        self, config: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        merged = self._double_state()
        merged.update(state or {})
        self.last_state = merged
        configurable = dict((config or {}).get("configurable") or {})
        parent = configurable.get("checkpoint_id") or "cp"
        self._fork_seq = getattr(self, "_fork_seq", 0) + 1
        configurable["checkpoint_id"] = f"{parent}-fork-{self._fork_seq}"
        return {**(config or {}), "configurable": configurable}

    async def aget_state(self, config: dict[str, Any]) -> Any:
        from types import SimpleNamespace

        configurable = dict((config or {}).get("configurable") or {})
        if not getattr(self, "_resumed", False):
            # Still sitting at the interrupt: not terminal.
            return SimpleNamespace(
                next=("human_interrupt",), tasks=(), config={"configurable": configurable}
            )
        configurable["checkpoint_id"] = "cp-terminal"
        return SimpleNamespace(next=(), tasks=(), config={"configurable": configurable})

    def _double_state(self) -> dict[str, Any]:
        for attr in ("last_state", "seed_state", "_state"):
            value = getattr(self, attr, None)
            if value:
                return dict(value)
        return {}

    def resumed_state(self, resume_signal: Any) -> dict[str, Any]:
        """State for the resumed node, assembled as human_interrupt_node does."""
        state = self._double_state()
        payload = getattr(resume_signal, "resume", None)
        if isinstance(payload, dict) and payload.get("resume_provenance"):
            state["resume_provenance"] = payload["resume_provenance"]
        self._resumed = True
        return state


class FakeResumeCheckpointService:
    """Checkpoint service double exposing the real restore contract.

    Records every (thread_id, checkpoint_id) it was asked for, so tests can
    assert the EXACT checkpoint was addressed.
    """

    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state
        self.loaded: list[tuple[str, str | None]] = []

    def _checkpoint(self, checkpoint_id: str | None) -> dict[str, Any]:
        return {
            "id": checkpoint_id or "latest",
            "channel_values": {"__root__": dict(self._state)},
        }

    async def load_checkpoint(
        self, thread_id: str, checkpoint_id: str | None = None
    ) -> dict[str, Any]:
        self.loaded.append((thread_id, checkpoint_id))
        return self._checkpoint(checkpoint_id)

    async def restore_checkpoint(
        self, thread_id: str, checkpoint_id: str | None = None
    ) -> CheckpointRestore:
        self.loaded.append((thread_id, checkpoint_id))
        configurable: dict[str, Any] = {"thread_id": thread_id, "checkpoint_ns": ""}
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id
        return CheckpointRestore(
            checkpoint=self._checkpoint(checkpoint_id),
            config={"configurable": configurable},
            metadata={},
        )

    def extract_state(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        return dict(checkpoint["channel_values"]["__root__"])


class FakeResumingGraphApp(ResumeGraphDouble):
    """Graph double that resumes the way the real graph does.

    Runs the REAL ``save_to_db_node`` on approval -- so the persisted
    analysis row, the graph.completed event and the returned analysis_id
    are all genuine -- and terminates without touching N17 on rejection.
    """

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self._state = dict(state or {})
        self.resume_payloads: list[Any] = []
        self.invocations = 0

    async def ainvoke(self, resume_signal: Any, config: dict[str, Any]) -> dict[str, Any]:
        from src.analysis.adapters.graph.nodes import save_to_db_node

        self.invocations += 1
        decision, feedback = decision_from_resume(resume_signal)
        self.resume_payloads.append(decision)

        state = self.resumed_state(resume_signal)
        state["human_decision"] = decision or ""
        state["human_feedback"] = feedback

        if decision == "reject":
            state["human_approval_required"] = False
            state["workflow_terminated"] = True
            state["termination_reason"] = feedback
            return state

        if decision != "approve":
            # Mirrors the real graph: an unusable resume leaves the run
            # still interrupted rather than raising.
            return {**state, "__interrupt__": ({"reason": "approval_required"},)}

        state["human_approval_required"] = False
        return await save_to_db_node(state)  # type: ignore[arg-type]


class FailingGraphApp:
    """Graph double whose resume always fails."""

    def __init__(self, error: str = "checkpointer connection reset") -> None:
        self._error = error

    async def aupdate_state(self, config: dict[str, Any], state: dict[str, Any]) -> None:
        return None

    async def ainvoke(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError(self._error)


def claim_session_factory_for(session: Any) -> Any:
    """Point the exactly-once claim at a test's own session.

    In production the claim opens its own short transaction (so it commits
    independently of the long request transaction); tests route it at the
    test session so claims are visible to the assertions.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory(_tenant_id: Any):
        yield session
        await session.commit()

    return _factory
