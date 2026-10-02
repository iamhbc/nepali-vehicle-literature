"""Admin authentication: a single researcher account configured by environment, JWT sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .services.ratelimit import client_key, limiter

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()


def verify_credentials(username: str, password: str) -> bool:
    s = get_settings()
    if not s.admin_enabled or username != s.admin_username:
        # Still run bcrypt so timing does not reveal which part failed.
        bcrypt.checkpw(b"x", bcrypt.hashpw(b"y", bcrypt.gensalt(4)))
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), s.admin_password_hash.encode())
    except ValueError:
        return False


def create_token(username: str) -> tuple[str, datetime]:
    s = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(hours=s.jwt_ttl_hours)
    token = jwt.encode({"sub": username, "role": "admin", "exp": expires}, s.jwt_secret, algorithm="HS256")
    return token, expires


def login_guard(request: Request) -> None:
    if not get_settings().admin_enabled:
        raise HTTPException(503, "The researcher area is not configured on this server.")
    limiter.check(f"login:{client_key(request)}", limit=10, window_seconds=900)


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    s = get_settings()
    if not s.admin_enabled:
        raise HTTPException(503, "The researcher area is not configured on this server.")
    if not creds:
        raise HTTPException(401, "Sign in to the researcher area.", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = jwt.decode(creds.credentials, s.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Your session expired. Please sign in again.") from None
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid session.") from None
    if claims.get("role") != "admin":
        raise HTTPException(403, "Not allowed.")
    return claims["sub"]
