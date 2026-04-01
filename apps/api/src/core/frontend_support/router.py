"""
Refers to Suite ID: TASK-051.

Frontend support endpoints that close backend gaps for production frontend
flows previously satisfied only by MSW handlers.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User

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


def _consent_store(request: Request) -> MutableMapping[str, dict]:
    store = getattr(request.app.state, "cookie_consent_store", None)
    if store is None:
        store = {}
        request.app.state.cookie_consent_store = store
    return store


def _accepted_scopes(request: Request) -> set[str]:
    scopes = getattr(request.app.state, "accepted_disclaimer_scopes", None)
    if scopes is None:
        scopes = set()
        request.app.state.accepted_disclaimer_scopes = scopes
    return scopes


def _consent_key(tenant_id: str, user_id: str, version: str) -> str:
    return f"{tenant_id}:{user_id}:{version}"


def _disclaimer_scope(project_id: str, tenant_id: str, user_id: str) -> str:
    return f"{tenant_id}:{user_id}:{DISCLAIMER_VERSION}:{project_id}"


def _trackers_blocked(categories: ConsentCategories) -> list[str]:
    blocked: list[str] = []
    if not categories.analytics:
        blocked.append("analytics")
    if not categories.marketing:
        blocked.append("marketing")
    return blocked


@router.post("/compliance/cookies/consent")
async def create_cookie_consent(
    payload: CookieConsentCreateRequest,
    request: Request,
    response: Response,
) -> dict:
    if payload.forceError:
        response.status_code = 500
        return {
            "code": "COOKIE_CONSENT_PERSIST_FAILED",
            "showBanner": True,
        }

    categories = payload.categories or ConsentCategories()
    _consent_store(request)[
        _consent_key(payload.tenantId, payload.userId, payload.version)
    ] = {
        "tenantId": payload.tenantId,
        "userId": payload.userId,
        "version": payload.version,
        "categories": categories.model_dump(),
    }
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
    request: Request,
) -> dict:
    record = _consent_store(request).get(_consent_key(tenantId, userId, version))
    return {
        "hasConsent": bool(record),
        "showBanner": not bool(record),
        "requiredVersion": version,
        "categories": None if record is None else record["categories"],
    }


@router.patch("/compliance/cookies/consent")
async def update_cookie_consent(
    payload: CookieConsentUpdateRequest,
    request: Request,
) -> dict:
    _consent_store(request)[
        _consent_key(payload.tenantId, payload.userId, payload.version)
    ] = {
        "tenantId": payload.tenantId,
        "userId": payload.userId,
        "version": payload.version,
        "categories": payload.categories.model_dump(),
    }
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
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {
        "projectId": "proj_sample_001",
        "route": "/dashboard/projects/proj_sample_001",
        "reused": True,
        "duplicateCreated": False,
    }


@router.get("/onboarding/sample-project/ready")
async def get_sample_project_ready(
    current_user: Annotated[User, Depends(get_current_user)],
    projectId: str | None = None,
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
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {
        "sessionId": payload.sessionId or "onb_001",
        "state": "ready",
        "recovered": True,
    }


@router.get("/onboarding/sample-project/telemetry")
async def get_sample_project_telemetry(
    current_user: Annotated[User, Depends(get_current_user)],
    sessionId: str | None = None,
) -> dict:
    return {
        "events": ["start", "ready"],
        "elapsedMs": 180000,
    }
