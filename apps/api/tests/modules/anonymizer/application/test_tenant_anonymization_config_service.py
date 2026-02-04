"""
TS-UC-SEC-ANO-003: Tenant anonymization config tests.
"""

from __future__ import annotations

from src.anonymizer.application.anonymization_service import AnonymizationStrategy
from src.anonymizer.application.tenant_anonymization_config_service import (
    TenantAnonymizationConfig,
    TenantAnonymizationConfigService,
)
from src.anonymizer.domain.pii_detector_service import PiiType


class TestTenantAnonymizationConfigService:
    """Refers to Suite ID: TS-UC-SEC-ANO-003."""

    def test_001_default_config_exists(self) -> None:
        service = TenantAnonymizationConfigService()
        config = service.get_config("tenant-a")
        assert config.default_strategy is AnonymizationStrategy.REDACT

    def test_002_default_pii_strategy_is_redact(self) -> None:
        service = TenantAnonymizationConfigService()
        config = service.get_config("tenant-a")
        assert config.strategy_for(PiiType.DNI) is AnonymizationStrategy.REDACT
        assert config.strategy_for(PiiType.EMAIL) is AnonymizationStrategy.REDACT

    def test_003_tenant_specific_override(self) -> None:
        service = TenantAnonymizationConfigService(
            {
                "tenant-a": TenantAnonymizationConfig(
                    default_strategy=AnonymizationStrategy.REDACT,
                    per_type={PiiType.EMAIL: AnonymizationStrategy.HASH},
                )
            }
        )
        config = service.get_config("tenant-a")
        assert config.strategy_for(PiiType.EMAIL) is AnonymizationStrategy.HASH

    def test_004_tenant_missing_falls_back_to_default(self) -> None:
        service = TenantAnonymizationConfigService(
            {
                "tenant-a": TenantAnonymizationConfig(
                    default_strategy=AnonymizationStrategy.HASH,
                    per_type={},
                )
            }
        )
        config = service.get_config("unknown-tenant")
        assert config.default_strategy is AnonymizationStrategy.REDACT

    def test_005_mixed_strategy_per_type(self) -> None:
        service = TenantAnonymizationConfigService(
            {
                "tenant-a": TenantAnonymizationConfig(
                    default_strategy=AnonymizationStrategy.REDACT,
                    per_type={
                        PiiType.DNI: AnonymizationStrategy.HASH,
                        PiiType.PHONE: AnonymizationStrategy.NONE,
                    },
                )
            }
        )
        config = service.get_config("tenant-a")
        assert config.strategy_for(PiiType.DNI) is AnonymizationStrategy.HASH
        assert config.strategy_for(PiiType.PHONE) is AnonymizationStrategy.NONE
        assert config.strategy_for(PiiType.EMAIL) is AnonymizationStrategy.REDACT

    def test_006_update_config_replaces_previous_value(self) -> None:
        service = TenantAnonymizationConfigService()
        service.set_config(
            "tenant-a",
            TenantAnonymizationConfig(
                default_strategy=AnonymizationStrategy.HASH,
                per_type={PiiType.EMAIL: AnonymizationStrategy.PSEUDONYMIZE},
            ),
        )
        config = service.get_config("tenant-a")
        assert config.default_strategy is AnonymizationStrategy.HASH
        assert config.strategy_for(PiiType.EMAIL) is AnonymizationStrategy.PSEUDONYMIZE

    def test_007_remove_config_reverts_to_default(self) -> None:
        service = TenantAnonymizationConfigService(
            {
                "tenant-a": TenantAnonymizationConfig(
                    default_strategy=AnonymizationStrategy.HASH,
                    per_type={},
                )
            }
        )
        service.remove_config("tenant-a")
        config = service.get_config("tenant-a")
        assert config.default_strategy is AnonymizationStrategy.REDACT

    def test_008_invalid_tenant_id_raises(self) -> None:
        service = TenantAnonymizationConfigService()
        try:
            service.get_config("")
            assert False, "Expected ValueError for empty tenant_id"
        except ValueError:
            assert True
