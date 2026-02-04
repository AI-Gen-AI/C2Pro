"""
TS-UC-SEC-ANO-003: Tenant anonymization configuration service.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.anonymizer.application.anonymization_service import AnonymizationStrategy
from src.anonymizer.domain.pii_detector_service import PiiType


@dataclass(frozen=True)
class TenantAnonymizationConfig:
    """Refers to Suite ID: TS-UC-SEC-ANO-003."""

    default_strategy: AnonymizationStrategy = AnonymizationStrategy.REDACT
    per_type: dict[PiiType, AnonymizationStrategy] = field(default_factory=dict)

    def strategy_for(self, pii_type: PiiType) -> AnonymizationStrategy:
        return self.per_type.get(pii_type, self.default_strategy)


class TenantAnonymizationConfigService:
    """Refers to Suite ID: TS-UC-SEC-ANO-003."""

    def __init__(self, config_by_tenant: dict[str, TenantAnonymizationConfig] | None = None) -> None:
        self._default_config = TenantAnonymizationConfig()
        self._config_by_tenant = dict(config_by_tenant or {})

    def get_config(self, tenant_id: str) -> TenantAnonymizationConfig:
        if not tenant_id:
            raise ValueError("tenant_id cannot be empty")
        return self._config_by_tenant.get(tenant_id, self._default_config)

    def set_config(self, tenant_id: str, config: TenantAnonymizationConfig) -> None:
        if not tenant_id:
            raise ValueError("tenant_id cannot be empty")
        self._config_by_tenant[tenant_id] = config

    def remove_config(self, tenant_id: str) -> None:
        if not tenant_id:
            raise ValueError("tenant_id cannot be empty")
        self._config_by_tenant.pop(tenant_id, None)
