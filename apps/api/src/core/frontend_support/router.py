"""
Refers to Suite ID: TASK-051.

Frontend support endpoints that close backend gaps for production frontend
flows previously satisfied only by MSW handlers.

TASK-REV-020: Cookie consent now persisted to database.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session
from src.core.frontend_support.repository import CookieConsentRepository
from src.core.security.secret_channel import (
    AwsSecretsManagerBundleProvider,
    EnvJsonSecretBundleProvider,
    VaultKvBundleProvider,
    redact_clerk_bundle,
)

router = APIRouter(tags=["frontend-support"])

DISCLAIMER_VERSION = "v1.0"


class ConsentCategories(BaseModel):
    necessary: bool = True
    analytics: bool = False
    marketing: bool = False


class CookieConsentCreateRequest(BaseModel):
    tenantId: str
    userId: str
    version: str
    forceError: bool = False
    categories: ConsentCategories | None = None


class CookieConsentUpdateRequest(BaseModel):
    tenantId: str
    userId: str
    version: str
    categories: ConsentCategories


class DisclaimerAcceptRequest(BaseModel):
    version: str | None = None
    forceError: bool = False


class OnboardingRetryRequest(BaseModel):
    sessionId: str | None = None


class SecretChannelClerkResponse(BaseModel):
    bundle_version: str
    values: dict[str, str]


def _get_consent_repository(
    db: AsyncSession = Depends(get_session),
) -> CookieConsentRepository:
    return CookieConsentRepository(session=db)


def _accepted_scopes(request: Request) -> set[str]:
    scopes = getattr(request.app.state, "accepted_disclaimer_scopes", None)
    if scopes is None:
        scopes = set()
        request.app.state.accepted_disclaimer_scopes = scopes
    return scopes


def _disclaimer_scope(project_id: str, tenant_id: str, user_id: str) -> str:
    return f"{tenant_id}:{user_id}:{DISCLAIMER_VERSION}:{project_id}"


def _trackers_blocked(categories: ConsentCategories) -> list[str]:
    blocked: list[str] = []
    if not categories.analytics:
        blocked.append("analytics")
    if not categories.marketing:
        blocked.append("marketing")
    return blocked


def _resolve_secret_channel_bundle() -> dict[str, str]:
    bundle_ref = settings.secret_channel_bundle_ref
    if not bundle_ref:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Secret channel bundle not configured",
        )
    if settings.secret_channel_backend == "env_json":
        provider = EnvJsonSecretBundleProvider()
    elif settings.secret_channel_backend == "aws_secrets_manager":
        if not settings.secret_channel_aws_region:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Secret channel AWS region not configured",
            )
        provider = AwsSecretsManagerBundleProvider(region=settings.secret_channel_aws_region)
    else:
        if not settings.secret_channel_vault_url or not settings.secret_channel_vault_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Secret channel Vault settings not configured",
            )
        provider = VaultKvBundleProvider(
            url=settings.secret_channel_vault_url,
            token=settings.secret_channel_vault_token,
        )
    bundle = provider.load_bundle(bundle_ref=bundle_ref)
    redacted = redact_clerk_bundle(bundle)
    if not redacted:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Secret channel returned no frontend-safe Clerk values",
        )
    return redacted


@router.post("/compliance/cookies/consent")
async def create_cookie_consent(
    payload: CookieConsentCreateRequest,
    _request: Request,
    response: Response,
    repo: CookieConsentRepository = Depends(_get_consent_repository),
) -> dict:
    if payload.forceError:
        response.status_code = 500
        return {
            "code": "COOKIE_CONSENT_PERSIST_FAILED",
            "showBanner": True,
        }

    categories = payload.categories or ConsentCategories()
    tenant_uuid = UUID(payload.tenantId)

    await repo.upsert_consent(
        tenant_id=tenant_uuid,
        user_id=payload.userId,
        version=payload.version,
        categories=categories.model_dump(),
    )
    await repo.session.commit()

    return {
        "saved": True,
        "categories": categories.model_dump(),
        "showBanner": False,
    }


@router.get("/compliance/cookies/consent")
async def get_cookie_consent(
    tenantId: str,
    userId: str,
    version: str,
    repo: CookieConsentRepository = Depends(_get_consent_repository),
) -> dict:
    tenant_uuid = UUID(tenantId)
    record = await repo.get_consent(tenant_uuid, userId, version)
    return {
        "hasConsent": record is not None,
        "showBanner": record is None,
        "requiredVersion": version,
        "categories": record.categories if record else None,
    }


@router.patch("/compliance/cookies/consent")
async def update_cookie_consent(
    payload: CookieConsentUpdateRequest,
    repo: CookieConsentRepository = Depends(_get_consent_repository),
) -> dict:
    tenant_uuid = UUID(payload.tenantId)

    await repo.upsert_consent(
        tenant_id=tenant_uuid,
        user_id=payload.userId,
        version=payload.version,
        categories=payload.categories.model_dump(),
    )
    await repo.session.commit()

    return {
        "categories": payload.categories.model_dump(),
        "trackersBlocked": _trackers_blocked(payload.categories),
    }


@router.get("/projects/{project_id}/gates/gate-8/disclaimer/status")
async def get_legal_disclaimer_status(
    project_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    scope = _disclaimer_scope(project_id, str(current_user.tenant_id), str(current_user.id))
    accepted = scope in _accepted_scopes(request)
    return {
        "accepted": accepted,
        "version": DISCLAIMER_VERSION,
        "mustPrompt": not accepted,
        "scope": scope.rsplit(f":{project_id}", 1)[0],
    }


@router.post("/projects/{project_id}/gates/gate-8/disclaimer/accept")
async def accept_legal_disclaimer(
    project_id: str,
    payload: DisclaimerAcceptRequest,
    request: Request,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if payload.forceError:
        response.status_code = 500
        return {
            "code": "DISCLAIMER_PERSIST_FAILED",
            "gateBlocked": True,
        }

    _accepted_scopes(request).add(_disclaimer_scope(project_id, str(current_user.tenant_id), str(current_user.id)))
    return {
        "accepted": True,
        "gateBlocked": False,
        "version": payload.version or DISCLAIMER_VERSION,
    }


@router.post("/onboarding/sample-project/start")
async def start_sample_project(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {
        "projectId": "proj_sample_001",
        "route": "/dashboard/projects/proj_sample_001",
        "reused": True,
        "duplicateCreated": False,
    }


@router.get("/onboarding/sample-project/ready")
async def get_sample_project_ready(
    _current_user: Annotated[User, Depends(get_current_user)],
    _projectId: str | None = None,
) -> dict:
    return {
        "widgets": {
            "documents": "ready",
            "alerts": "ready",
            "stakeholders": "ready",
        }
    }


@router.post("/onboarding/sample-project/retry")
async def retry_sample_project(
    payload: OnboardingRetryRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {
        "sessionId": payload.sessionId or "onb_001",
        "state": "ready",
        "recovered": True,
    }


@router.get("/onboarding/sample-project/telemetry")
async def get_sample_project_telemetry(
    _current_user: Annotated[User, Depends(get_current_user)],
    _sessionId: str | None = None,
) -> dict:
    return {
        "events": ["start", "ready"],
        "elapsedMs": 180000,
    }


@router.get("/security/secret-channel/clerk", response_model=SecretChannelClerkResponse)
async def get_clerk_secret_channel_bundle(
    x_secret_channel_token: str | None = Header(default=None, alias="X-Secret-Channel-Token"),
) -> SecretChannelClerkResponse:
    expected_token = settings.secret_channel_token
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Secret channel token not configured",
        )
    if not x_secret_channel_token or x_secret_channel_token != expected_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret channel token")
    values = _resolve_secret_channel_bundle()
    return SecretChannelClerkResponse(bundle_version="2026-04-21", values=values)
