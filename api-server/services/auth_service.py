"""
services/auth_service.py
JWT creation and verification using python-jose.

generate_token() - creates a signed JWT for dev/testing
verify_token()   - FastAPI dependency, validates Bearer token on protected routes
"""

import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", 24))

bearer_scheme = HTTPBearer()


def generate_token(user_id: str, role: str) -> str:
    """Create a signed JWT with user_id and role claims."""
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=EXPIRY_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    FastAPI dependency - validates JWT from Authorization: Bearer header.
    Inject with: current_user: dict = Depends(verify_token)
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
