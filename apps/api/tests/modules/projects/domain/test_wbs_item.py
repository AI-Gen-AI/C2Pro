"""
WBS Item Entity Tests (TDD - RED Phase)

Refers to Suite ID: TS-UD-PRJ-WBS-001.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.projects.domain.wbs import WBSItem


class TestWBSItemEntity:
    """Refers to Suite ID: TS-UD-PRJ-WBS-001."""

    def test_level_outside_1_to_4_is_invalid(self):
        with pytest.raises(ValueError):
            WBSItem(project_id=uuid4(), code="1", name="Root", level=0)

        with pytest.raises(ValueError):
            WBSItem(project_id=uuid4(), code="1.1.1.1.1", name="Too deep", level=5)

    def test_level_within_1_to_4_is_valid(self):
        item = WBSItem(project_id=uuid4(), code="1.1", name="Package", level=2)
        assert item.level == 2
