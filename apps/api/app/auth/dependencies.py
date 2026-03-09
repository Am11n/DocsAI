from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt

from app.core.settings import settings
from app.schemas.common import ErrorCode

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user_id: str
    tenant_id: str
    raw_claims: dict


async def _decode_with_jwks(token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        jwks = (await client.get(settings.supabase_jwks_url)).json()
    header = jwt.get_unverified_header(token)
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": ErrorCode.UNAUTHORIZED, "message": "Signing key not found"},
        )
    return jwt.decode(token, key, algorithms=[header["alg"]], options={"verify_aud": False})


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": ErrorCode.UNAUTHORIZED, "message": "Missing bearer token"},
        )

    claims = await _decode_with_jwks(credentials.credentials)
    user_id = claims.get("sub")
    tenant_id = claims.get("tenant_id") or claims.get("app_metadata", {}).get("tenant_id")
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": ErrorCode.FORBIDDEN, "message": "Missing user or tenant scope"},
        )

    return AuthContext(user_id=user_id, tenant_id=tenant_id, raw_claims=claims)
