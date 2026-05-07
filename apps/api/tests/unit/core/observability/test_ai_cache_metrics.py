"""TS-AI-FLASH-003: Tests for AI cache metrics."""

from unittest.mock import MagicMock, patch


from src.core.observability import monitoring


class TestAICacheMetrics:
    """Tests for AI cache metrics functions."""

    def test_record_ai_cache_hit(self):
        """record_ai_cache_hit should increment counter."""
        if monitoring.METRICS_AVAILABLE:
            with patch.object(monitoring.AI_CACHE_HITS, "labels") as mock_labels:
                mock_counter = MagicMock()
                mock_labels.return_value = mock_counter

                monitoring.record_ai_cache_hit("tenant-1", "claude-sonnet-4-20250514")

                mock_labels.assert_called_once_with(
                    tenant_id="tenant-1", model="claude-sonnet-4-20250514"
                )
                mock_counter.inc.assert_called_once()

    def test_record_ai_cache_miss(self):
        """record_ai_cache_miss should increment counter."""
        if monitoring.METRICS_AVAILABLE:
            with patch.object(monitoring.AI_CACHE_MISSES, "labels") as mock_labels:
                mock_counter = MagicMock()
                mock_labels.return_value = mock_counter

                monitoring.record_ai_cache_miss("tenant-1", "claude-sonnet-4-20250514")

                mock_labels.assert_called_once_with(
                    tenant_id="tenant-1", model="claude-sonnet-4-20250514"
                )
                mock_counter.inc.assert_called_once()

    def test_record_ai_cache_size(self):
        """record_ai_cache_size should set gauge."""
        if monitoring.METRICS_AVAILABLE:
            with patch.object(monitoring.AI_CACHE_SIZE, "set") as mock_set:
                monitoring.record_ai_cache_size(42)

                mock_set.assert_called_once_with(42)

    def test_record_ai_cache_eviction(self):
        """record_ai_cache_eviction should increment counter."""
        if monitoring.METRICS_AVAILABLE:
            with patch.object(monitoring.AI_CACHE_EVICTIONS, "labels") as mock_labels:
                mock_counter = MagicMock()
                mock_labels.return_value = mock_counter

                monitoring.record_ai_cache_eviction("ttl_expiry")

                mock_labels.assert_called_once_with(reason="ttl_expiry")
                mock_counter.inc.assert_called_once()

    def test_empty_tenant_id(self):
        """Should handle empty tenant_id gracefully."""
        if monitoring.METRICS_AVAILABLE:
            with patch.object(monitoring.AI_CACHE_HITS, "labels") as mock_labels:
                mock_counter = MagicMock()
                mock_labels.return_value = mock_counter

                monitoring.record_ai_cache_hit("", "claude-sonnet-4-20250514")

                mock_labels.assert_called_once_with(
                    tenant_id="", model="claude-sonnet-4-20250514"
                )

    def test_metrics_not_available(self):
        """Should be no-op when metrics not available."""
        with patch.object(monitoring, "METRICS_AVAILABLE", False):
            # Should not raise
            monitoring.record_ai_cache_hit("tenant-1", "claude-sonnet-4-20250514")
            monitoring.record_ai_cache_miss("tenant-1", "claude-sonnet-4-20250514")
            monitoring.record_ai_cache_size(42)
            monitoring.record_ai_cache_eviction("ttl_expiry")


class TestAICacheMetricsExist:
    """Tests that AI cache metrics are properly defined."""

    def test_ai_cache_hits_metric_exists(self):
        """AI_CACHE_HITS metric should exist."""
        if monitoring.METRICS_AVAILABLE:
            assert hasattr(monitoring, "AI_CACHE_HITS")

    def test_ai_cache_misses_metric_exists(self):
        """AI_CACHE_MISSES metric should exist."""
        if monitoring.METRICS_AVAILABLE:
            assert hasattr(monitoring, "AI_CACHE_MISSES")

    def test_ai_cache_size_metric_exists(self):
        """AI_CACHE_SIZE metric should exist."""
        if monitoring.METRICS_AVAILABLE:
            assert hasattr(monitoring, "AI_CACHE_SIZE")

    def test_ai_cache_evictions_metric_exists(self):
        """AI_CACHE_EVICTIONS metric should exist."""
        if monitoring.METRICS_AVAILABLE:
            assert hasattr(monitoring, "AI_CACHE_EVICTIONS")


class TestObservableExports:
    """Test that AI cache observability functions are exported."""

    def test_record_ai_cache_hit_exported(self):
        """record_ai_cache_hit should be in __all__."""
        from src.core.observability import __all__ as exports
        assert "record_ai_cache_hit" in exports

    def test_record_ai_cache_miss_exported(self):
        """record_ai_cache_miss should be in __all__."""
        from src.core.observability import __all__ as exports
        assert "record_ai_cache_miss" in exports

    def test_record_ai_cache_size_exported(self):
        """record_ai_cache_size should be in __all__."""
        from src.core.observability import __all__ as exports
        assert "record_ai_cache_size" in exports

    def test_record_ai_cache_eviction_exported(self):
        """record_ai_cache_eviction should be in __all__."""
        from src.core.observability import __all__ as exports
        assert "record_ai_cache_eviction" in exports
