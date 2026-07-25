"""
TS-UD-ANL-RACI-001: Unit tests for RACI generation agent and helper functions.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.analysis.adapters.ai.agents.raci_generator import (
    RaciAssignment,
    RaciGenerationResult,
    RaciGeneratorAgent,
    StakeholderInput,
    WBSItemInput,
    _build_user_payload,
    _coerce_assignment,
    _ensure_accountable,
    _parse_assignments,
    _select_accountable_fallback,
    check_raci_rules,
)
from src.shared_kernel.enums import RACIRole


def _make_wbs(name: str = "Tarea 1", description: str | None = None, clause_text: str | None = None) -> WBSItemInput:
    return WBSItemInput(id=uuid4(), name=name, description=description, clause_text=clause_text)


def _make_stakeholder(
    name: str | None = "Contratista",
    role: str | None = "Contratista",
    company: str | None = "Constructora SA",
    stakeholder_type: str | None = "CONTRACTOR",
) -> StakeholderInput:
    return StakeholderInput(id=uuid4(), name=name, role=role, company=company, stakeholder_type=stakeholder_type)


class TestBuildUserPayload:
    def test_builds_json_with_multiple_items(self) -> None:
        wbs = [_make_wbs("Excavacion"), _make_wbs("Cimentacion")]
        stakeholders = [_make_stakeholder("Cliente", "Owner", "Acme Corp")]
        result = _build_user_payload(wbs_items=wbs, stakeholders=stakeholders)
        assert "Excavacion" in result
        assert "Cimentacion" in result
        assert "Acme Corp" in result
        assert '"wbs_items"' in result
        assert '"stakeholders"' in result

    def test_handles_empty_iterables(self) -> None:
        result = _build_user_payload(wbs_items=[], stakeholders=[])
        assert '{"wbs_items": [], "stakeholders": []}' in result

    def test_encodes_none_fields_as_null(self) -> None:
        wbs = [_make_wbs("Tarea", None, None)]
        stakeholders = [_make_stakeholder("Fulano", None, None, None)]
        result = _build_user_payload(wbs_items=wbs, stakeholders=stakeholders)
        assert "null" in result


class TestParseAssignments:
    def test_parses_dict_with_assignments_list(self) -> None:
        sid1, wid1 = uuid4(), uuid4()
        payload = {
            "assignments": [
                {"wbs_item_id": str(wid1), "stakeholder_id": str(sid1), "role": "R"},
            ]
        }
        result = _parse_assignments(payload)
        assert len(result) == 1
        assert result[0].wbs_item_id == wid1
        assert result[0].stakeholder_id == sid1
        assert result[0].role == RACIRole.RESPONSIBLE

    def test_parses_single_assignment_dict(self) -> None:
        sid1, wid1 = uuid4(), uuid4()
        payload = {
            "assignments": {"wbs_item_id": str(wid1), "stakeholder_id": str(sid1), "role": "A"},
        }
        result = _parse_assignments(payload)
        assert len(result) == 1
        assert result[0].role == RACIRole.ACCOUNTABLE

    def test_empty_payload_returns_empty(self) -> None:
        result = _parse_assignments({"assignments": []})
        assert result == []

    def test_missing_assignments_key_returns_empty(self) -> None:
        result = _parse_assignments({"risks": []})
        assert result == []

    def test_parses_list_at_root(self) -> None:
        sid1, wid1 = uuid4(), uuid4()
        result = _parse_assignments(
            [{"wbs_item_id": str(wid1), "stakeholder_id": str(sid1), "role": "I"}]
        )
        assert len(result) == 1

    def test_skips_non_dict_items(self) -> None:
        result = _parse_assignments(["not_a_dict"])
        assert result == []


class TestCoerceAssignment:
    def test_valid_assignment(self) -> None:
        sid1, wid1 = uuid4(), uuid4()
        item = {"wbs_item_id": str(wid1), "stakeholder_id": str(sid1), "role": "C", "evidence_text": "Revisado por X"}
        result = _coerce_assignment(item)
        assert result is not None
        assert result.wbs_item_id == wid1
        assert result.stakeholder_id == sid1
        assert result.role == RACIRole.CONSULTED
        assert result.evidence_text == "Revisado por X"

    def test_invalid_uuid_returns_none(self) -> None:
        result = _coerce_assignment({"wbs_item_id": "not-a-uuid", "stakeholder_id": "also-bad", "role": "R"})
        assert result is None

    def test_invalid_role_returns_none(self) -> None:
        sid1, wid1 = uuid4(), uuid4()
        result = _coerce_assignment({"wbs_item_id": str(wid1), "stakeholder_id": str(sid1), "role": "X"})
        assert result is None

    def test_whitespace_evidence_becomes_none(self) -> None:
        sid1, wid1 = uuid4(), uuid4()
        result = _coerce_assignment(
            {"wbs_item_id": str(wid1), "stakeholder_id": str(sid1), "role": "R", "evidence_text": "   "}
        )
        assert result is not None
        assert result.evidence_text is None

    def test_non_string_evidence_ignored(self) -> None:
        sid1, wid1 = uuid4(), uuid4()
        result = _coerce_assignment(
            {"wbs_item_id": str(wid1), "stakeholder_id": str(sid1), "role": "R", "evidence_text": 123}
        )
        assert result is not None
        assert result.evidence_text is None


class TestSelectAccountableFallback:
    def test_prefers_cliente_role(self) -> None:
        s = _make_stakeholder("Gerente", "Cliente", "A")
        fallback = _select_accountable_fallback([s])
        assert fallback is not None
        assert fallback.id == s.id

    def test_fallback_to_project_manager(self) -> None:
        s = _make_stakeholder("PM", "Project Manager", "B")
        fallback = _select_accountable_fallback([s])
        assert fallback is not None
        assert fallback.id == s.id

    def test_fallback_to_first_stakeholder(self) -> None:
        s1 = _make_stakeholder("Operario", "Worker", "C")
        s2 = _make_stakeholder("Operario 2", "Worker", "D")
        fallback = _select_accountable_fallback([s1, s2])
        assert fallback is not None
        assert fallback.id == s1.id

    def test_no_stakeholders_returns_none(self) -> None:
        assert _select_accountable_fallback([]) is None


class TestEnsureAccountable:
    def test_adds_accountable_when_missing(self) -> None:
        wbs = [_make_wbs("T1")]
        s = _make_stakeholder("Owner", "Cliente", "A")
        result = _ensure_accountable([], wbs_items=wbs, stakeholders=[s])
        assert len(result) == 1
        assert result[0].role == RACIRole.ACCOUNTABLE
        assert result[0].stakeholder_id == s.id

    def test_preserves_existing_accountable(self) -> None:
        wbs = [_make_wbs("T1")]
        s = _make_stakeholder("Owner", "Cliente", "A")
        existing = RaciAssignment(wbs_item_id=wbs[0].id, stakeholder_id=s.id, role=RACIRole.ACCOUNTABLE)
        result = _ensure_accountable([existing], wbs_items=wbs, stakeholders=[s])
        assert len(result) == 1

    def test_no_stakeholders_returns_existing(self) -> None:
        wbs = [_make_wbs("T1")]
        result = _ensure_accountable([], wbs_items=wbs, stakeholders=[])
        assert result == []


class TestCheckRaciRules:
    def test_warns_missing_accountable(self) -> None:
        wbs = [_make_wbs("T1")]
        sid1 = uuid4()
        assignments = [RaciAssignment(wbs_item_id=wbs[0].id, stakeholder_id=sid1, role=RACIRole.RESPONSIBLE)]
        warnings = check_raci_rules(assignments, wbs)
        assert any("sin Accountable" in w for w in warnings)

    def test_warns_missing_responsible(self) -> None:
        wbs = [_make_wbs("T1")]
        sid1 = uuid4()
        assignments = [RaciAssignment(wbs_item_id=wbs[0].id, stakeholder_id=sid1, role=RACIRole.ACCOUNTABLE)]
        warnings = check_raci_rules(assignments, wbs)
        assert any("sin Responsible" in w for w in warnings)

    def test_warns_multiple_accountable(self) -> None:
        wbs = [_make_wbs("T1")]
        sid1, sid2 = uuid4(), uuid4()
        assignments = [
            RaciAssignment(wbs_item_id=wbs[0].id, stakeholder_id=sid1, role=RACIRole.ACCOUNTABLE),
            RaciAssignment(wbs_item_id=wbs[0].id, stakeholder_id=sid2, role=RACIRole.ACCOUNTABLE),
        ]
        warnings = check_raci_rules(assignments, wbs)
        assert any("multiples Accountable" in w for w in warnings)

    def test_no_warnings_when_valid(self) -> None:
        wbs = [_make_wbs("T1")]
        sid1, sid2 = uuid4(), uuid4()
        assignments = [
            RaciAssignment(wbs_item_id=wbs[0].id, stakeholder_id=sid1, role=RACIRole.RESPONSIBLE),
            RaciAssignment(wbs_item_id=wbs[0].id, stakeholder_id=sid2, role=RACIRole.ACCOUNTABLE),
        ]
        warnings = check_raci_rules(assignments, wbs)
        assert len(warnings) == 0


class TestRaciGeneratorAgent:
    @pytest.mark.asyncio
    async def test_generate_assignments_empty_input(self) -> None:
        agent = RaciGeneratorAgent()
        result = await agent.generate_assignments(wbs_items=[], stakeholders=[])
        assert isinstance(result, RaciGenerationResult)
        assert result.assignments == []
        assert result.warnings == []

    @pytest.mark.asyncio
    async def test_generate_assignments_empty_stakeholders(self) -> None:
        wbs = [_make_wbs("T1")]
        agent = RaciGeneratorAgent()
        result = await agent.generate_assignments(wbs_items=wbs, stakeholders=[])
        assert result.assignments == []

    @pytest.mark.asyncio
    async def test_generate_assignments_with_mocked_llm(self) -> None:
        wbs = [_make_wbs("Excavacion", "Excavar terreno")]
        stakeholders = [_make_stakeholder("Contratista", "Contratista"), _make_stakeholder("Cliente", "Owner")]
        sid_r = stakeholders[0].id
        sid_a = stakeholders[1].id
        wid = wbs[0].id

        llm_payload = {
            "assignments": [
                {"wbs_item_id": str(wid), "stakeholder_id": str(sid_r), "role": "R"},
                {"wbs_item_id": str(wid), "stakeholder_id": str(sid_a), "role": "A"},
            ]
        }

        with patch.object(RaciGeneratorAgent, "_run_with_retry", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_payload
            agent = RaciGeneratorAgent()
            result = await agent.generate_assignments(wbs_items=wbs, stakeholders=stakeholders)
            assert len(result.assignments) == 2
            roles = {a.role for a in result.assignments}
            assert RACIRole.RESPONSIBLE in roles
            assert RACIRole.ACCOUNTABLE in roles

    def test_check_raci_rules_warns_on_missing_roles(self) -> None:
        from src.analysis.adapters.ai.agents.raci_generator import (
            WBSItemInput,
            check_raci_rules,
        )

        wbs = [WBSItemInput(id=uuid4(), name="T1")]
        assignment = RaciAssignment(
            wbs_item_id=wbs[0].id,
            stakeholder_id=uuid4(),
            role=RACIRole.RESPONSIBLE,
        )
        warnings = check_raci_rules([assignment], wbs)
        assert any("sin Accountable" in w for w in warnings)

    def test_check_raci_rules_no_warnings_when_complete(self) -> None:
        from src.analysis.adapters.ai.agents.raci_generator import (
            WBSItemInput,
            check_raci_rules,
        )

        wbs = [WBSItemInput(id=uuid4(), name="T1")]
        sid = uuid4()
        assignments = [
            RaciAssignment(wbs_item_id=wbs[0].id, stakeholder_id=sid, role=RACIRole.RESPONSIBLE),
            RaciAssignment(wbs_item_id=wbs[0].id, stakeholder_id=sid, role=RACIRole.ACCOUNTABLE),
        ]
        warnings = check_raci_rules(assignments, wbs)
        assert warnings == []
