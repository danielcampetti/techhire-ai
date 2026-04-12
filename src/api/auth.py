"""JWT authentication utilities for ComplianceAgent."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from src.config import settings

_bearer = HTTPBearer(auto_error=True)


class TokenUser(BaseModel):
    user_id: int
    username: str
    role: str  # "analyst" | "manager"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": username,
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> TokenUser:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    return TokenUser(
        user_id=payload["user_id"],
        username=payload["sub"],
        role=payload["role"],
    )


def require_role(*roles: str):
    """Dependency factory: require_role('manager') or require_role('analyst', 'manager')."""
    def _check(user: TokenUser = Depends(get_current_user)) -> TokenUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Acesso negado")
        return user
    return _check
