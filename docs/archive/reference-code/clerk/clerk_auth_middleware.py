"""
Clerk JWT Verification Middleware for FastAPI

Location: apps/api/src/middleware/clerk_auth.py

Verifies Clerk JWT tokens and extracts user/organization context
"""

import os
import httpx
import jwt
from functools import lru_cache
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import HTTPException, Request, Depends, status
from jose import JWTError
import logging

logger = logging.getLogger(__name__)

# Clerk configuration
CLERK_SECRET_KEY = os.getenv('CLERK_SECRET_KEY')
CLERK_PUBLISHABLE_KEY = os.getenv('NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY')


class ClerkTokenVerificationError(HTTPException):
    """Custom exception for Clerk token verification failures"""

    def __init__(self, detail: str, status_code: int = 401):
        super().__init__(status_code=status_code, detail=detail)


@lru_cache(maxsize=1)
def get_clerk_jwks():
    """
    Fetch and cache Clerk JWKS (JSON Web Key Set)
    
    Cached for performance to avoid repeated API calls
    """
    try:
        # Construct JWKS URL from publishable key
        # Extract the domain from the publishable key
        if not CLERK_PUBLISHABLE_KEY:
            logger.error("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY not configured")
            return None

        # Typically: pk_test_[domain]...
        # Need to call Clerk API to get JWKS
        clerk_domain = os.getenv('CLERK_DOMAIN', 'clerk.com')
        jwks_url = f'https://{clerk_domain}/.well-known/jwks.json'

        response = httpx.get(jwks_url, timeout=5)
        response.raise_for_status()

        return response.json()

    except Exception as e:
        logger.error(f"Failed to fetch Clerk JWKS: {str(e)}")
        return None


async def verify_clerk_token(token: str) -> Dict[str, Any]:
    """
    Verify Clerk JWT token and extract claims
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        Decoded token claims
        
    Raises:
        ClerkTokenVerificationError: If token is invalid
    """

    if not token:
        raise ClerkTokenVerificationError('No token provided', 401)

    try:
        # Decode header to get 'kid' (key ID)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')

        if not kid:
            raise ClerkTokenVerificationError('Token missing kid header', 401)

        # Get JWKS
        jwks = get_clerk_jwks()
        if not jwks:
            raise ClerkTokenVerificationError(
                'Failed to fetch Clerk JWKS', 500
            )

        # Find the key matching kid
        key = None
        for k in jwks.get('keys', []):
            if k.get('kid') == kid:
                key = k
                break

        if not key:
            raise ClerkTokenVerificationError(f'Key {kid} not found in JWKS', 401)

        # Convert JWKS key to RSA public key
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from jwt.algorithms import RSAAlgorithm

        rsa_key = RSAAlgorithm.from_jwk(key)

        # Verify and decode token
        decoded = jwt.decode(
            token,
            rsa_key,
            algorithms=['RS256'],
            options={'verify_exp': True},
        )

        return decoded

    except jwt.ExpiredSignatureError:
        raise ClerkTokenVerificationError('Token has expired', 401)
    except jwt.InvalidTokenError as e:
        logger.warning(f'Invalid Clerk token: {str(e)}')
        raise ClerkTokenVerificationError(f'Invalid token: {str(e)}', 401)
    except Exception as e:
        logger.error(f'Unexpected error verifying token: {str(e)}')
        raise ClerkTokenVerificationError(
            'Token verification failed', 500
        )


async def extract_clerk_claims(request: Request) -> Dict[str, Any]:
    """
    Extract Clerk JWT from request and verify it
    
    This is a dependency that can be used in route handlers
    """

    auth_header = request.headers.get('Authorization', '')

    if not auth_header.startswith('Bearer '):
        raise ClerkTokenVerificationError('Missing or invalid Authorization header', 401)

    token = auth_header.split(' ')[1]
    return await verify_clerk_token(token)


class ClerkUser:
    """Represents a verified Clerk user with extracted claims"""

    def __init__(self, claims: Dict[str, Any]):
        self.claims = claims
        self.user_id = claims.get('sub')
        self.email = claims.get('email')
        self.first_name = claims.get('first_name')
        self.last_name = claims.get('last_name')
        self.org_id = claims.get('org_id') or claims.get('organization_id')
        self.org_role = claims.get('org_role') or claims.get('organization_role')
        self.email_verified = claims.get('email_verified', False)

    @property
    def is_authenticated(self) -> bool:
        """Check if user is properly authenticated"""
        return bool(self.user_id and self.email_verified)

    @property
    def is_org_admin(self) -> bool:
        """Check if user is admin of their organization"""
        return self.org_role == 'admin'

    def has_org(self) -> bool:
        """Check if user has selected an organization"""
        return bool(self.org_id)


async def get_clerk_user(
    claims: Dict[str, Any] = Depends(extract_clerk_claims),
) -> ClerkUser:
    """
    Dependency to get authenticated Clerk user
    
    Usage:
        @app.get("/api/projects")
        async def list_projects(user: ClerkUser = Depends(get_clerk_user)):
            # user is guaranteed to be authenticated
            return {"user_id": user.user_id, ...}
    """
    user = ClerkUser(claims)

    if not user.is_authenticated:
        raise ClerkTokenVerificationError('User not authenticated', 401)

    return user


async def require_organization(
    user: ClerkUser = Depends(get_clerk_user),
) -> ClerkUser:
    """
    Dependency that requires user to have selected an organization
    """
    if not user.has_org():
        raise HTTPException(
            status_code=400,
            detail='User must select an organization to access this resource',
        )
    return user


async def require_admin(
    user: ClerkUser = Depends(get_clerk_user),
) -> ClerkUser:
    """
    Dependency that requires user to be organization admin
    """
    if not user.is_org_admin:
        raise HTTPException(
            status_code=403,
            detail='This endpoint requires admin role',
        )
    return user


# ============================================
# SQLAlchemy dependency integration
# ============================================

async def get_current_tenant_id(
    user: ClerkUser = Depends(require_organization),
) -> str:
    """
    Get the current tenant_id for the authenticated user
    
    This maps from Clerk org_id to your internal tenant_id
    You'll need to store this mapping in your database
    
    Usage:
        @app.get("/api/projects")
        async def list_projects(
            tenant_id: str = Depends(get_current_tenant_id)
        ):
            # Query projects for this tenant
            return await projects_service.list_by_tenant(tenant_id)
    """

    # TODO: Implement mapping from Clerk org_id to tenant_id
    # This would query your Supabase organizations table
    # For now, return org_id (assuming it's the tenant_id)

    if not user.org_id:
        raise HTTPException(
            status_code=400,
            detail='No organization selected',
        )

    # Map Clerk org_id to tenant_id
    # await supabase.from('organizations').select('tenant_id').eq('clerk_org_id', user.org_id)

    return user.org_id


# ============================================
# Example usage in route handlers
# ============================================

"""
from fastapi import FastAPI, Depends

app = FastAPI()

@app.get("/api/user/profile")
async def get_user_profile(user: ClerkUser = Depends(get_clerk_user)):
    # User is authenticated
    return {
        "user_id": user.user_id,
        "email": user.email,
        "name": f"{user.first_name} {user.last_name}",
        "organization": user.org_id,
    }


@app.get("/api/admin/users")
async def list_all_users(user: ClerkUser = Depends(require_admin)):
    # User is authenticated AND is admin
    # ...
    pass


@app.get("/api/projects")
async def list_projects(tenant_id: str = Depends(get_current_tenant_id)):
    # User is authenticated and tenant_id is extracted
    # Query only projects for this tenant
    # RLS will enforce this at database level
    pass
"""
