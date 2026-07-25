"""
Branch coverage tests for _extract_parsed_text priority fallbacks.

Test Suite: TS-DOC-PARSE-001
"""

from __future__ import annotations

from src.documents.application.parse_document_use_case import _extract_parsed_text


class TestExtractParsedTextClauses:
    def test_extract_text_from_clauses_with_title_and_content(self) -> None:
        payload = {
            "clauses": [
                {"title": "Scope", "content": "Build parking lot"},
                {"title": "Budget", "content": "$100k"},
            ],
        }
        result = _extract_parsed_text(payload)
        assert "Scope: Build parking lot" in result
        assert "Budget: $100k" in result

    def test_extract_text_from_clauses_content_only(self) -> None:
        payload = {
            "clauses": [
                {"content": "Clause without title"},
                {"text": "Using text key"},
            ],
        }
        result = _extract_parsed_text(payload)
        assert "Clause without title" in result
        assert "Using text key" in result

    def test_extract_text_from_clauses_skips_non_dict(self) -> None:
        payload = {
            "clauses": [
                "not a dict",
                {"title": "Valid", "content": "valid content"},
            ],
        }
        result = _extract_parsed_text(payload)
        assert "Valid: valid content" in result


class TestExtractParsedTextSchedule:
    def test_extract_text_from_schedule_format(self) -> None:
        payload = {
            "schedule": [
                {
                    "description": "Foundation work",
                    "start_date": "2026-01-01",
                    "end_date": "2026-02-01",
                },
                {
                    "activity": "Framing",
                    "start": "2026-02-02",
                    "end": "2026-03-01",
                },
            ],
        }
        result = _extract_parsed_text(payload)
        assert "Foundation work" in result
        assert "start: 2026-01-01" in result
        assert "Framing" in result
        assert "start: 2026-02-02" in result

    def test_extract_text_from_schedule_task_key(self) -> None:
        payload = {
            "schedule": [
                {"task": "Inspection"},
            ],
        }
        result = _extract_parsed_text(payload)
        assert "Inspection" in result

    def test_extract_text_from_schedule_skips_non_dict(self) -> None:
        payload = {
            "schedule": [
                "bad row",
                {"description": "Good row"},
            ],
        }
        result = _extract_parsed_text(payload)
        assert "Good row" in result


class TestExtractParsedTextBudget:
    def test_extract_text_from_budget_chapters(self) -> None:
        payload = {
            "budget": {
                "header": {"project_name": "Parking Lot"},
                "chapters": [
                    {"code": "01", "description": "Earthwork", "amount": 50000},
                    {"chapter_code": "02", "name": "Concrete", "total": 75000},
                ],
            },
        }
        result = _extract_parsed_text(payload)
        assert "Parking Lot" in result
        assert "01 Earthwork" in result
        assert "50000" in result
        assert "02 Concrete" in result

    def test_extract_text_from_budget_no_chapters_skips(self) -> None:
        payload = {
            "budget": {
                "header": {"project_name": "Minimal"},
            },
        }
        result = _extract_parsed_text(payload)
        assert result == ""


class TestExtractParsedTextGeneric:
    def test_extract_text_from_full_text_key(self) -> None:
        payload = {"full_text": "Complete document text here."}
        result = _extract_parsed_text(payload)
        assert result == "Complete document text here."

    def test_extract_text_from_text_key(self) -> None:
        payload = {"text": "Simple text content."}
        result = _extract_parsed_text(payload)
        assert result == "Simple text content."

    def test_extract_text_from_raw_text_key(self) -> None:
        payload = {"raw_text": "Raw extraction output."}
        result = _extract_parsed_text(payload)
        assert result == "Raw extraction output."

    def test_extract_text_from_content_key(self) -> None:
        payload = {"content": "Document body content."}
        result = _extract_parsed_text(payload)
        assert result == "Document body content."

    def test_extract_text_empty_payload_returns_empty(self) -> None:
        result = _extract_parsed_text({})
        assert result == ""


class TestExtractParsedTextTextBlocks:
    def test_extract_text_from_text_blocks(self) -> None:
        payload = {
            "text_blocks": [
                {"text": "Block one content."},
                {"text": "Block two content."},
            ],
        }
        result = _extract_parsed_text(payload)
        assert "Block one content." in result
        assert "Block two content." in result
