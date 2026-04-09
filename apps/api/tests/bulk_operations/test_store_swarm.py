"""
C2Pro - Bulk Operations Job Store Unit Tests (Swarm)

Refers to Suite ID: TS-E2E-FLW-BLK-001

Tests for the shared in-memory bulk operation job store in
src/bulk_operations/store.py.

Coverage:
- register_job: default field population via setdefault
- register_job: caller-supplied values are preserved (setdefault semantics)
- register_job: timestamps are set as non-empty ISO strings
- register_job: input dict is not mutated
- register_job: second call with same job_id overwrites the first
- get_job: unknown job_id returns None
- get_job: returns the stored payload after register_job
"""

from __future__ import annotations

import pytest

import src.bulk_operations.store as store_module
from src.bulk_operations.store import get_job, register_job

# ---------------------------------------------------------------------------
# State-isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_jobs():
    """Clear the module-level _jobs dict before and after every test."""
    store_module._jobs.clear()
    yield
    store_module._jobs.clear()


# ===========================================================================
# TestRegisterJob
# ===========================================================================


class TestRegisterJob:
    """Unit tests for register_job."""

    @pytest.mark.red_phase
    def test_minimal_data_sets_default_status_queued(self):
        """register_job with no 'status' key → status defaults to 'queued'."""
        register_job("job-1", {})
        assert store_module._jobs["job-1"]["status"] == "queued"

    @pytest.mark.red_phase
    def test_minimal_data_sets_default_percentage_zero(self):
        """register_job with no 'percentage' key → percentage defaults to 0."""
        register_job("job-1", {})
        assert store_module._jobs["job-1"]["percentage"] == 0

    @pytest.mark.red_phase
    def test_minimal_data_sets_default_processed_items_zero(self):
        """register_job with no 'processed_items' key → processed_items defaults to 0."""
        register_job("job-1", {})
        assert store_module._jobs["job-1"]["processed_items"] == 0

    @pytest.mark.red_phase
    def test_minimal_data_sets_default_total_items_zero(self):
        """register_job with no 'total_items' key → total_items defaults to 0."""
        register_job("job-1", {})
        assert store_module._jobs["job-1"]["total_items"] == 0

    @pytest.mark.red_phase
    def test_minimal_data_sets_default_eta_seconds_zero(self):
        """register_job with no 'eta_seconds' key → eta_seconds defaults to 0."""
        register_job("job-1", {})
        assert store_module._jobs["job-1"]["eta_seconds"] == 0

    @pytest.mark.red_phase
    def test_minimal_data_sets_started_at_non_empty_string(self):
        """register_job with no 'started_at' key → started_at is a non-empty string."""
        register_job("job-1", {})
        started_at = store_module._jobs["job-1"]["started_at"]
        assert isinstance(started_at, str)
        assert len(started_at) > 0

    @pytest.mark.red_phase
    def test_minimal_data_sets_updated_at_non_empty_string(self):
        """register_job with no 'updated_at' key → updated_at is a non-empty string."""
        register_job("job-1", {})
        updated_at = store_module._jobs["job-1"]["updated_at"]
        assert isinstance(updated_at, str)
        assert len(updated_at) > 0

    @pytest.mark.red_phase
    def test_custom_status_is_preserved(self):
        """register_job with explicit 'status' → setdefault does not overwrite it."""
        register_job("job-2", {"status": "running"})
        assert store_module._jobs["job-2"]["status"] == "running"

    @pytest.mark.red_phase
    def test_custom_percentage_is_preserved(self):
        """register_job with explicit 'percentage' → value is kept as provided."""
        register_job("job-2", {"percentage": 42})
        assert store_module._jobs["job-2"]["percentage"] == 42

    @pytest.mark.red_phase
    def test_custom_total_items_is_preserved(self):
        """register_job with explicit 'total_items' → value is kept as provided."""
        register_job("job-2", {"total_items": 100})
        assert store_module._jobs["job-2"]["total_items"] == 100

    @pytest.mark.red_phase
    def test_custom_processed_items_is_preserved(self):
        """register_job with explicit 'processed_items' → value is kept as provided."""
        register_job("job-2", {"processed_items": 50})
        assert store_module._jobs["job-2"]["processed_items"] == 50

    @pytest.mark.red_phase
    def test_custom_eta_seconds_is_preserved(self):
        """register_job with explicit 'eta_seconds' → value is kept as provided."""
        register_job("job-2", {"eta_seconds": 30})
        assert store_module._jobs["job-2"]["eta_seconds"] == 30

    @pytest.mark.red_phase
    def test_custom_started_at_is_preserved(self):
        """register_job with explicit 'started_at' → setdefault does not overwrite it."""
        register_job("job-2", {"started_at": "2024-01-01T00:00:00+00:00"})
        assert store_module._jobs["job-2"]["started_at"] == "2024-01-01T00:00:00+00:00"

    @pytest.mark.red_phase
    def test_custom_updated_at_is_preserved(self):
        """register_job with explicit 'updated_at' → setdefault does not overwrite it."""
        register_job("job-2", {"updated_at": "2024-06-15T12:00:00+00:00"})
        assert store_module._jobs["job-2"]["updated_at"] == "2024-06-15T12:00:00+00:00"

    @pytest.mark.red_phase
    def test_input_dict_is_not_mutated(self):
        """register_job copies job_data before modifying it; caller's dict is unchanged."""
        original = {"status": "pending"}
        original_copy = dict(original)
        register_job("job-3", original)
        assert original == original_copy

    @pytest.mark.red_phase
    def test_second_call_with_same_job_id_overwrites_first(self):
        """A second register_job call for the same job_id replaces the previous entry."""
        register_job("job-4", {"status": "queued", "total_items": 10})
        register_job("job-4", {"status": "running", "total_items": 20})
        stored = store_module._jobs["job-4"]
        assert stored["status"] == "running"
        assert stored["total_items"] == 20

    @pytest.mark.red_phase
    def test_job_is_stored_in_jobs_dict(self):
        """After register_job, the job_id key is present in the module _jobs dict."""
        register_job("job-5", {})
        assert "job-5" in store_module._jobs

    @pytest.mark.red_phase
    def test_extra_custom_fields_are_passed_through(self):
        """Arbitrary extra keys in job_data are preserved in the stored payload."""
        register_job("job-6", {"my_custom_field": "hello"})
        assert store_module._jobs["job-6"]["my_custom_field"] == "hello"


# ===========================================================================
# TestGetJob
# ===========================================================================


class TestGetJob:
    """Unit tests for get_job."""

    @pytest.mark.red_phase
    def test_unknown_job_id_returns_none(self):
        """get_job with a job_id that was never registered returns None."""
        result = get_job("does-not-exist")
        assert result is None

    @pytest.mark.red_phase
    def test_returns_stored_dict_after_register(self):
        """get_job returns the same payload that was stored by register_job."""
        register_job("job-A", {"status": "done", "percentage": 100})
        result = get_job("job-A")
        assert result is not None
        assert result["status"] == "done"
        assert result["percentage"] == 100

    @pytest.mark.red_phase
    def test_returns_none_for_different_job_id(self):
        """get_job with a different job_id returns None even when other jobs exist."""
        register_job("job-B", {})
        result = get_job("job-C")
        assert result is None

    @pytest.mark.red_phase
    def test_get_job_returns_defaults_populated_by_register(self):
        """get_job result includes all default fields set by register_job."""
        register_job("job-D", {})
        result = get_job("job-D")
        assert result is not None
        assert result["status"] == "queued"
        assert result["percentage"] == 0
        assert result["processed_items"] == 0
        assert result["total_items"] == 0
        assert result["eta_seconds"] == 0

    @pytest.mark.red_phase
    def test_get_job_after_overwrite_returns_latest_data(self):
        """get_job reflects the most recent register_job call when job_id is reused."""
        register_job("job-E", {"status": "queued"})
        register_job("job-E", {"status": "completed", "percentage": 100})
        result = get_job("job-E")
        assert result is not None
        assert result["status"] == "completed"
        assert result["percentage"] == 100

    @pytest.mark.red_phase
    def test_get_job_result_is_identity_of_stored_object(self):
        """get_job returns the exact object stored in _jobs (identity, not a copy)."""
        register_job("job-F", {})
        result = get_job("job-F")
        assert result is store_module._jobs["job-F"]
