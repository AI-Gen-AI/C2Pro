"""
Unit tests for Alert domain model entity normalization.

TS-UD-ALR-ENT-001
"""

from datetime import UTC, datetime
from uuid import uuid4

from alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from alerts.domain.models import Alert


class TestNormalizeAffectedEntities:
    """Tests for normalize_affected_entities static method."""

    def test_normalize_dict_returns_unchanged(self) -> None:
        """Test that dict values are returned unchanged."""
        input_dict = {"items": ["doc-1", "doc-2"], "count": 2}

        result = Alert.normalize_affected_entities(input_dict)

        assert result == input_dict
        assert result is input_dict

    def test_normalize_dict_with_nested_structure(self) -> None:
        """Test that dict with nested structure is returned unchanged."""
        input_dict = {
            "documents": [{"id": "1", "name": "Contract.pdf"}],
            "clauses": ["clause-1", "clause-2"],
        }

        result = Alert.normalize_affected_entities(input_dict)

        assert result == input_dict

    def test_normalize_list_converts_to_items(self) -> None:
        """Test that list is converted to {"items": list}."""
        input_list = ["doc-1", "doc-2", "doc-3"]

        result = Alert.normalize_affected_entities(input_list)

        assert result == {"items": ["doc-1", "doc-2", "doc-3"]}

    def test_normalize_empty_list(self) -> None:
        """Test that empty list converts to {"items": []}."""
        result = Alert.normalize_affected_entities([])

        assert result == {"items": []}

    def test_normalize_none_returns_empty_dict(self) -> None:
        """Test that None returns empty dict."""
        result = Alert.normalize_affected_entities(None)

        assert result == {}

    def test_normalize_string_returns_empty_dict(self) -> None:
        """Test that string returns empty dict."""
        result = Alert.normalize_affected_entities("not a list or dict")

        assert result == {}

    def test_normalize_int_returns_empty_dict(self) -> None:
        """Test that int returns empty dict."""
        result = Alert.normalize_affected_entities(42)

        assert result == {}


class TestNormalizeMetadata:
    """Tests for normalize_metadata static method."""

    def test_normalize_dict_returns_unchanged(self) -> None:
        """Test that dict values are returned unchanged."""
        metadata = {"root_cause": "testing", "status": "investigating"}

        result = Alert.normalize_metadata(metadata)

        assert result == metadata
        assert result is metadata

    def test_normalize_none_returns_empty_dict(self) -> None:
        """Test that None returns empty dict."""
        result = Alert.normalize_metadata(None)

        assert result == {}

    def test_normalize_string_returns_empty_dict(self) -> None:
        """Test that string returns empty dict."""
        result = Alert.normalize_metadata("some string")

        assert result == {}

    def test_normalize_list_returns_empty_dict(self) -> None:
        """Test that list returns empty dict."""
        result = Alert.normalize_metadata(["item1", "item2"])

        assert result == {}


class TestCoerceText:
    """Tests for coerce_text static method."""

    def test_coerce_primary_non_empty(self) -> None:
        """Test that primary non-empty string is returned."""
        result = Alert.coerce_text("primary text", "fallback", "default")

        assert result == "primary text"

    def test_coerce_primary_strips_whitespace(self) -> None:
        """Test that primary whitespace is stripped."""
        result = Alert.coerce_text("  primary  ", "fallback", "default")

        assert result == "primary"

    def test_coerce_fallback_when_primary_empty(self) -> None:
        """Test that fallback is used when primary is empty."""
        result = Alert.coerce_text("   ", "fallback text", "default")

        assert result == "fallback text"

    def test_coerce_default_when_both_empty(self) -> None:
        """Test that default is used when both are empty."""
        result = Alert.coerce_text("  ", "   ", "default value")

        assert result == "default value"

    def test_coerce_default_when_none(self) -> None:
        """Test that default is used when primary is None."""
        result = Alert.coerce_text(None, None, "default value")

        assert result == "default value"

    def test_coerce_uses_first_non_empty(self) -> None:
        """Test that first non-empty is used."""
        result = Alert.coerce_text("", "second", "default")

        assert result == "second"


class TestCoerceCategory:
    """Tests for coerce_category static method."""

    def test_coerce_non_empty_string(self) -> None:
        """Test that non-empty string is returned."""
        result = Alert.coerce_category("SCOPE")

        assert result == "SCOPE"

    def test_coerce_strips_whitespace(self) -> None:
        """Test that whitespace is stripped."""
        result = Alert.coerce_category("  BUDGET  ")

        assert result == "BUDGET"

    def test_coerce_empty_string_returns_risk(self) -> None:
        """Test that empty string returns default 'risk'."""
        result = Alert.coerce_category("   ")

        assert result == "risk"

    def test_coerce_none_returns_risk(self) -> None:
        """Test that None returns default 'risk'."""
        result = Alert.coerce_category(None)

        assert result == "risk"

    def test_coerce_int_returns_risk(self) -> None:
        """Test that non-string returns default 'risk'."""
        result = Alert.coerce_category(123)

        assert result == "risk"


class TestCoerceState:
    """Tests for coerce_state static method."""

    def test_coerce_lowercase_conversion(self) -> None:
        """Test that uppercase is converted to lowercase."""
        result = Alert.coerce_state("OPEN", "default")

        assert result == "open"

    def test_coerce_preserves_lowercase(self) -> None:
        """Test that lowercase is preserved."""
        result = Alert.coerce_state("resolved", "default")

        assert result == "resolved"

    def test_coerce_strips_whitespace(self) -> None:
        """Test that whitespace is stripped."""
        result = Alert.coerce_state("  CLOSED  ", "default")

        assert result == "closed"

    def test_coerce_empty_returns_default(self) -> None:
        """Test that empty string returns default."""
        result = Alert.coerce_state("   ", "pending")

        assert result == "pending"

    def test_coerce_none_returns_default(self) -> None:
        """Test that None returns default."""
        result = Alert.coerce_state(None, "active")

        assert result == "active"


class TestCoerceDatetime:
    """Tests for coerce_datetime static method."""

    def test_coerce_datetime_returns_unchanged(self) -> None:
        """Test that datetime is returned unchanged."""
        dt = datetime(2026, 4, 8, 10, 30, 0, tzinfo=UTC)

        result = Alert.coerce_datetime(dt)

        assert result == dt
        assert result is dt

    def test_coerce_datetime_without_tz(self) -> None:
        """Test that naive datetime is returned unchanged."""
        dt = datetime(2026, 4, 8, 10, 30, 0)

        result = Alert.coerce_datetime(dt)

        assert result == dt

    def test_coerce_none_returns_now(self) -> None:
        """Test that None returns current datetime."""
        result = Alert.coerce_datetime(None)

        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    def test_coerce_string_returns_now(self) -> None:
        """Test that string returns current datetime."""
        result = Alert.coerce_datetime("not a datetime")

        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    def test_coerce_int_returns_now(self) -> None:
        """Test that int returns current datetime."""
        result = Alert.coerce_datetime(12345)

        assert isinstance(result, datetime)
        assert result.tzinfo == UTC


class TestAlertEntityIntegration:
    """Integration tests for Alert entity with normalization methods."""

    def test_create_alert_with_list_entities(self) -> None:
        """Test creating alert with list entities and normalizing."""
        alert = Alert(
            id=uuid4(),
            project_id=uuid4(),
            severity=AlertSeverity.HIGH,
            category="BUDGET",
            status=AlertStatus.OPEN,
            approval_status=ApprovalStatus.PENDING,
            rule_id="BUD-001",
            title="Budget Alert",
            description="Test alert",
            affected_entities=["doc-1", "doc-2"],
            created_at=datetime.now(UTC),
        )

        normalized = Alert.normalize_affected_entities(alert.affected_entities)

        assert normalized == {"items": ["doc-1", "doc-2"]}

    def test_create_alert_with_dict_entities(self) -> None:
        """Test creating alert with dict entities (no change needed)."""
        entities = {"items": ["doc-1"], "source": "ai"}
        alert = Alert(
            id=uuid4(),
            project_id=uuid4(),
            severity=AlertSeverity.MEDIUM,
            category="SCOPE",
            status=AlertStatus.OPEN,
            approval_status=ApprovalStatus.PENDING,
            rule_id="SCOPE-001",
            title="Scope Alert",
            description="Test alert",
            affected_entities=entities,
            created_at=datetime.now(UTC),
        )

        normalized = Alert.normalize_affected_entities(alert.affected_entities)

        assert normalized == entities
        assert normalized is entities

    def test_normalization_methods_are_static(self) -> None:
        """Test that normalization methods can be called without instance."""
        result = Alert.normalize_affected_entities(["item"])

        assert result == {"items": ["item"]}
