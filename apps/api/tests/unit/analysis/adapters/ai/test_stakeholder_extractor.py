"""
TS-UD-ANL-STK-001: Unit tests for stakeholder extraction helper functions.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.analysis.adapters.ai.agents.stakeholder_extractor import (
    StakeholderExtractorAgent,
    StakeholderType,
    _clean_email,
    _clean_text,
    _coerce_stakeholder,
    _extract_items,
    _normalize_type,
    _select_relevant_text,
    _split_pages,
)


class TestCleanText:
    def test_strips_whitespace(self) -> None:
        assert _clean_text("  Empresa SA  ") == "Empresa SA"

    def test_empty_returns_none(self) -> None:
        assert _clean_text("") is None
        assert _clean_text("   ") is None

    def test_non_string_returns_none(self) -> None:
        assert _clean_text(None) is None
        assert _clean_text(42) is None


class TestCleanEmail:
    def test_valid_email(self) -> None:
        assert _clean_email("user@example.com") == "user@example.com"

    def test_invalid_email_no_at(self) -> None:
        assert _clean_email("invalid-email") is None

    def test_empty_returns_none(self) -> None:
        assert _clean_email("") is None
        assert _clean_email(None) is None


class TestNormalizeType:
    def test_cliente_by_name(self) -> None:
        assert _normalize_type(None, "Cliente", None, "Acme Corp") == StakeholderType.CLIENT

    def test_contratista_by_role(self) -> None:
        assert _normalize_type(None, "Contratista Principal", None, None) == StakeholderType.CONTRACTOR

    def test_subcontratista(self) -> None:
        assert _normalize_type("SUBCONTRACTOR", None, None, None) == StakeholderType.SUBCONTRACTOR

    def test_supervision(self) -> None:
        assert _normalize_type(None, None, None, "Interventor de Obra") == StakeholderType.SUPERVISION

    def test_exact_type_match(self) -> None:
        assert _normalize_type("CONTRACTOR", None, None, None) == StakeholderType.CONTRACTOR
        assert _normalize_type("CLIENT", None, None, None) == StakeholderType.CLIENT

    def test_unknown_returns_none(self) -> None:
        assert _normalize_type(None, "Desconocido", None, None) is None

    def test_dueno_is_client(self) -> None:
        assert _normalize_type(None, "Dueno de la obra", None, None) == StakeholderType.CLIENT

    def test_mandante_is_client(self) -> None:
        assert _normalize_type(None, None, "Mandante S.A.", None) == StakeholderType.CLIENT


class TestExtractItems:
    def test_extracts_list(self) -> None:
        payload = {"stakeholders": [{"name": "A"}, {"name": "B"}]}
        result = _extract_items(payload)
        assert len(result) == 2

    def test_extracts_single_dict(self) -> None:
        payload = {"stakeholders": {"name": "Solo"}}
        result = _extract_items(payload)
        assert len(result) == 1

    def test_empty_payload(self) -> None:
        assert _extract_items({"stakeholders": []}) == []

    def test_list_at_root(self) -> None:
        result = _extract_items([{"name": "A"}])
        assert len(result) == 1

    def test_non_dict_non_list(self) -> None:
        assert _extract_items("text") == []


class TestCoerceStakeholder:
    def test_full_valid_stakeholder(self) -> None:
        item = {
            "name": "Juan Perez",
            "role": "Representante Legal",
            "company": "Acme Corp",
            "type": "CLIENT",
            "contact_email": "juan@acme.com",
        }
        result = _coerce_stakeholder(item)
        assert result is not None
        assert result.name == "Juan Perez"
        assert result.type == StakeholderType.CLIENT
        assert result.contact_email == "juan@acme.com"

    def test_missing_name_returns_none(self) -> None:
        assert _coerce_stakeholder({"role": "Gerente"}) is None

    def test_missing_type_returns_none(self) -> None:
        assert _coerce_stakeholder({"name": "Juan"}) is None

    def test_optional_fields_none(self) -> None:
        result = _coerce_stakeholder({"name": "Juan Perez", "role": "Contratista", "type": None})
        assert result is not None
        assert result.name == "Juan Perez"

    def test_invalid_email(self) -> None:
        result = _coerce_stakeholder({"name": "Juan", "type": "CONTRACTOR", "contact_email": "invalid"})
        assert result is not None
        assert result.contact_email is None


class TestSplitPages:
    def test_splits_on_form_feed(self) -> None:
        text = "page1 content\fpage2 content\fpage3 content"
        pages = _split_pages(text)
        assert len(pages) == 3

    def test_splits_on_page_markers(self) -> None:
        text = "content A\n\nPage 1 of 10\n\nmore A\n\n---\n\ncontent B\n\nPage 2 of 10\n\nmore B"
        pages = _split_pages(text)
        assert len(pages) >= 1

    def test_no_splits_returns_single_page(self) -> None:
        pages = _split_pages("plain text")
        assert len(pages) == 1


class TestSelectRelevantText:
    def test_short_text_returned_fully(self) -> None:
        text = "First page\n\nSecond page"
        result = _select_relevant_text(text, first_pages=10, last_pages=5)
        assert "First page" in result
        assert "Second page" in result

    def test_long_text_trimmed_to_head_tail(self) -> None:
        pages_text = "\f".join(f"page {i} content" for i in range(1, 21))
        result = _select_relevant_text(pages_text, first_pages=3, last_pages=2)
        assert "[INICIO]" in result
        assert "[FIN]" in result
        assert "page 1 content" in result
        assert "page 19 content" in result
        # middle pages should be excluded
        assert "page 10 content" not in result

    def test_empty_input(self) -> None:
        result = _select_relevant_text("")
        assert result == ""


class TestStakeholderExtractorAgent:
    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self) -> None:
        agent = StakeholderExtractorAgent()
        result = await agent.extract("")
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_empty(self) -> None:
        agent = StakeholderExtractorAgent()
        result = await agent.extract("   \n  ")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_with_mocked_llm(self) -> None:
        llm_payload = {
            "stakeholders": [
                {
                    "name": "Constructora ABC",
                    "role": "Contratista General",
                    "company": "Constructora ABC SA",
                    "type": "CONTRACTOR",
                    "contact_email": "contacto@constructoraabc.com",
                },
                {
                    "name": "Municipalidad de Lima",
                    "role": "Dueno de la obra",
                    "company": "Municipalidad",
                    "type": "CLIENT",
                    "contact_email": "obras@munlima.gob.pe",
                },
            ]
        }

        with patch.object(StakeholderExtractorAgent, "_run_with_retry", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_payload
            agent = StakeholderExtractorAgent()
            result = await agent.extract("Contrato entre Municipalidad de Lima y Constructora ABC")
            assert len(result) == 2
            assert result[0].name == "Constructora ABC"
            assert result[0].type == StakeholderType.CONTRACTOR
            assert result[1].name == "Municipalidad de Lima"
            assert result[1].type == StakeholderType.CLIENT

    @pytest.mark.asyncio
    async def test_extract_filters_invalid(self) -> None:
        llm_payload = {
            "stakeholders": [
                {"name": "Valid", "type": "CLIENT", "contact_email": "v@test.com"},
                {"name": "", "type": "CONTRACTOR"},
            ]
        }

        with patch.object(StakeholderExtractorAgent, "_run_with_retry", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_payload
            agent = StakeholderExtractorAgent()
            result = await agent.extract("text")
            assert len(result) == 1
            assert result[0].name == "Valid"

    @pytest.mark.asyncio
    async def test_extract_no_stakeholders_found(self) -> None:
        with patch.object(StakeholderExtractorAgent, "_run_with_retry", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {"stakeholders": []}
            agent = StakeholderExtractorAgent()
            result = await agent.extract("texto irrelevante")
            assert result == []
