"""Tests for core.sync_backlog_to_blackboard module.

UNIFY-007: Automated sync script tests
"""
import json
import pytest
from pathlib import Path
from datetime import datetime, timezone
import sys
import os

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.sync_backlog_to_blackboard import (
    extraer_tareas_de_backlog,
    inferir_tipo_y_rol,
    pull_tasks_from_backlog,
    push_completed_tasks_to_backlog,
    _mark_tasks_complete_in_file,
    TASK_ROW_PATTERN,
)


@pytest.fixture
def sample_backlog_content():
    """Sample backlog markdown content for testing."""
    return """# Sample Backlog

## Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
|--------|----------|---------|------------|-------------|--------|
| [ ] | P0 | `TASK-BCK-001` | None | Implement user authentication | `docs/auth.md` |
| [x] | P1 | `TASK-BCK-002` | None | Create database schema | `docs/schema.md` |
| [ ] | P1 | `TASK-FRT-001` | `TASK-BCK-001` | Build login UI | `docs/frontend.md` |
| [ ] | P2 | `TASK-AI-001` | None | Add LLM prompt template | `docs/ai.md` |
"""


@pytest.fixture
def temp_backlog_file(tmp_path, sample_backlog_content):
    """Create a temporary backlog file."""
    backlog_file = tmp_path / "TEST_BACKLOG.md"
    backlog_file.write_text(sample_backlog_content, encoding="utf-8")
    return backlog_file


@pytest.fixture
def temp_blackboard_file(tmp_path):
    """Create a temporary blackboard.json file."""
    blackboard_file = tmp_path / "blackboard.json"
    blackboard_data = {
        "session_id": "test_session",
        "objetivo_global": "Test sync",
        "estado_actual": "ejecucion",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "role_assignment": {
            "planner": None,
            "backend": None,
            "frontend": None,
            "ai": None,
            "infra": None,
            "qa": None,
            "reviewer": None,
            "security": None,
            "devops": None,
        },
        "tareas": [],
        "contexto_paso_anterior": "",
        "trazas_de_error": [],
        "reintentos": 0,
        "max_reintentos": 3,
        "backlog_sync": {
            "last_sync": None,
            "backlog_file": "TEST_BACKLOG.md",
            "task_ids_en_sesion": [],
        },
    }
    blackboard_file.write_text(json.dumps(blackboard_data, indent=2), encoding="utf-8")
    return blackboard_file


class TestTaskExtraction:
    """Test task extraction from backlog markdown."""

    def test_task_row_pattern_matches_valid_row(self):
        """Test regex pattern matches valid task rows."""
        valid_row = "| [ ] | P0 | `TASK-BCK-001` | None | Description | Source |"
        match = TASK_ROW_PATTERN.match(valid_row)
        assert match is not None
        assert match.group(1).strip() == ""  # Empty checkbox
        assert match.group(2).strip() == "P0"  # Priority
        assert match.group(3).strip() == "TASK-BCK-001"  # Task ID
        assert match.group(4).strip() == "None"  # Depends on
        assert match.group(5).strip() == "Description"  # Description
        assert match.group(6).strip() == "Source"  # Source

    def test_task_row_pattern_matches_completed_row(self):
        """Test regex pattern matches completed task rows."""
        completed_row = "| [x] | P1 | `TASK-FRT-002` | TASK-BCK-001 | Build UI | docs/ui.md |"
        match = TASK_ROW_PATTERN.match(completed_row)
        assert match is not None
        assert match.group(1).strip().lower() == "x"  # Completed checkbox

    def test_extraer_tareas_de_backlog(self, temp_backlog_file):
        """Test extracting pending tasks from backlog file."""
        tasks = extraer_tareas_de_backlog(temp_backlog_file)

        # Should extract only pending tasks (not completed ones)
        assert len(tasks) == 3  # BCK-001, FRT-001, AI-001 (not BCK-002 which is completed)

        # Verify first task
        assert tasks[0]["backlog_id"] == "TASK-BCK-001"
        assert tasks[0]["priority"] == "P0"
        assert tasks[0]["status"] == "pendiente"
        assert tasks[0]["description"] == "Implement user authentication"
        assert tasks[0]["source"] == "`docs/auth.md`"

    def test_extraer_tareas_de_backlog_nonexistent_file(self, tmp_path):
        """Test extracting tasks from non-existent file returns empty list."""
        nonexistent = tmp_path / "nonexistent.md"
        tasks = extraer_tareas_de_backlog(nonexistent)
        assert tasks == []


class TestTypeAndRoleInference:
    """Test inferring task type and role from task ID and description."""

    def test_inferir_tipo_from_task_id_backend(self):
        """Test backend tasks are correctly identified."""
        tipo, rol = inferir_tipo_y_rol("TASK-BCK-001", "Create API endpoint")
        assert tipo == "backend"
        assert rol == "backend"

    def test_inferir_tipo_from_task_id_frontend(self):
        """Test frontend tasks are correctly identified."""
        tipo, rol = inferir_tipo_y_rol("TASK-FRT-001", "Build login page")
        assert tipo == "frontend"
        assert rol == "frontend"

    def test_inferir_tipo_from_task_id_ai(self):
        """Test AI tasks are correctly identified."""
        tipo, rol = inferir_tipo_y_rol("TASK-AI-001", "Add prompt template")
        assert tipo == "ai"
        assert rol == "ai"

    def test_inferir_tipo_from_task_id_qa(self):
        """Test QA tasks are correctly identified."""
        tipo, rol = inferir_tipo_y_rol("TASK-QA-001", "Write integration tests")
        assert tipo == "qa"
        assert rol == "qa"

    def test_inferir_tipo_from_task_id_infra(self):
        """Test infrastructure tasks are correctly identified."""
        tipo, rol = inferir_tipo_y_rol("TASK-INF-001", "Setup monitoring")
        assert tipo == "infra"
        assert rol == "infra"

    def test_inferir_tipo_from_task_id_devops(self):
        """Test devops tasks are correctly identified."""
        tipo, rol = inferir_tipo_y_rol("TASK-DEV-001", "Setup CI pipeline")
        assert tipo == "devops"
        assert rol == "devops"

    def test_inferir_tipo_from_description_fallback(self):
        """Test type inference falls back to description keywords."""
        # Unknown task ID prefix, should use description
        tipo, rol = inferir_tipo_y_rol("TASK-XXX-001", "Create database schema")
        assert tipo == "backend"
        assert rol == "backend"

    def test_inferir_tipo_default_fallback(self):
        """Test default fallback when no match found."""
        tipo, rol = inferir_tipo_y_rol("TASK-XXX-001", "Unknown task type")
        assert tipo == "infra"  # Default fallback
        assert rol == "infra"


class TestMarkTasksComplete:
    """Test marking tasks as complete in backlog files."""

    def test_mark_single_task_complete(self, temp_backlog_file):
        """Test marking a single task as complete."""
        completed_task = {
            "backlog_id": "TASK-BCK-001",
            "estado": "completado"
        }

        count = _mark_tasks_complete_in_file(temp_backlog_file, [completed_task])
        assert count == 1

        # Verify file was updated
        content = temp_backlog_file.read_text(encoding="utf-8")
        assert "| [x] |" in content
        assert "`TASK-BCK-001`" in content

    def test_mark_multiple_tasks_complete(self, temp_backlog_file):
        """Test marking multiple tasks as complete."""
        completed_tasks = [
            {"backlog_id": "TASK-BCK-001", "estado": "completado"},
            {"backlog_id": "TASK-FRT-001", "estado": "completado"},
        ]

        count = _mark_tasks_complete_in_file(temp_backlog_file, completed_tasks)
        assert count == 2

        content = temp_backlog_file.read_text(encoding="utf-8")

        # Both tasks should be marked complete
        lines = content.splitlines()
        bck_line = next(l for l in lines if "TASK-BCK-001" in l)
        frt_line = next(l for l in lines if "TASK-FRT-001" in l)

        assert "| [x] |" in bck_line
        assert "| [x] |" in frt_line

    def test_mark_already_completed_task_idempotent(self, temp_backlog_file):
        """Test marking an already completed task is idempotent."""
        # TASK-BCK-002 is already marked [x] in sample content
        completed_task = {
            "backlog_id": "TASK-BCK-002",
            "estado": "completado"
        }

        original_content = temp_backlog_file.read_text(encoding="utf-8")
        count = _mark_tasks_complete_in_file(temp_backlog_file, [completed_task])

        # Should not update already completed task
        assert count == 0

        # Content should remain unchanged
        new_content = temp_backlog_file.read_text(encoding="utf-8")
        assert new_content == original_content

    def test_mark_nonexistent_task_no_change(self, temp_backlog_file):
        """Test marking a non-existent task doesn't modify file."""
        completed_task = {
            "backlog_id": "TASK-XXX-999",
            "estado": "completado"
        }

        original_content = temp_backlog_file.read_text(encoding="utf-8")
        count = _mark_tasks_complete_in_file(temp_backlog_file, [completed_task])

        assert count == 0

        # Content should remain unchanged
        new_content = temp_backlog_file.read_text(encoding="utf-8")
        assert new_content == original_content


class TestValidation:
    """Test validation and error handling."""

    def test_task_row_pattern_rejects_invalid_rows(self):
        """Test regex pattern rejects invalid task rows."""
        invalid_rows = [
            "Not a task row at all",
            "| Missing | Some | Columns |",
            "| [x] | P0 | TASK-001 |",  # Missing backticks around task ID
        ]

        for row in invalid_rows:
            match = TASK_ROW_PATTERN.match(row)
            assert match is None, f"Pattern should not match: {row}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
