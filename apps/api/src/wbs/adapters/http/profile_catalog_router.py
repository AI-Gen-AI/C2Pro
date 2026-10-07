"""Read-only WBS Domain Profile catalog (PC-2b.1 #920, ADR-030).

Lists the locked, versioned profiles and the exact pin each one contributes to a change set.
There is no write method: profiles are reviewed repository content, never runtime records.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.wbs.intelligence.profiles.catalog import default_catalog
from src.wbs.intelligence.profiles.schema import SCHEMA_VERSION

router = APIRouter(prefix="/wbs/profiles", tags=["WBS domain profiles"])


class WBSDomainProfileSummary(BaseModel):
    profile_id: str
    profile_version: str
    namespace: str
    profile_digest: str
    title: str
    status: str
    advisory: bool = True  # profiles never create, submit or approve WBS
    applicable_project_types: list[str]
    decomposition_kinds: list[str]
    decomposition_patterns: list[str]
    includes: list[dict[str, Any]]
    pin: dict[str, str]


class WBSDomainProfileCatalogResponse(BaseModel):
    schema_version: str
    profiles: list[WBSDomainProfileSummary]


@router.get("", response_model=WBSDomainProfileCatalogResponse)
async def list_wbs_domain_profiles(
    _user: Annotated[User, Depends(get_current_user)],
) -> WBSDomainProfileCatalogResponse:
    """The locked Domain Profile catalog (advisory profiles and their exact pins)."""
    summaries = []
    for profile in default_catalog().profiles():
        model = profile.model
        summaries.append(WBSDomainProfileSummary(
            profile_id=profile.profile_id, profile_version=profile.version, namespace=profile.namespace,
            profile_digest=profile.digest, title=model.title, status=model.status,
            applicable_project_types=sorted({t for a in model.applicable_archetypes for t in a.project_types}),
            decomposition_kinds=[f"{profile.namespace}:{kind.term}" for kind in model.decomposition_kinds],
            decomposition_patterns=[pattern.pattern_id for pattern in model.decomposition_patterns],
            includes=[pin.model_dump(exclude_none=True) for pin in model.composition.includes],
            pin=profile.pin(),
        ))
    return WBSDomainProfileCatalogResponse(schema_version=SCHEMA_VERSION, profiles=summaries)


__all__ = ["router"]
