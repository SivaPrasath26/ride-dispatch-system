"""
services/auth_service.py
JWT token generation helpers.
In production, replace with a proper user database lookup.
"""

from flask_jwt_extended import create_access_token


def generate_token(user_id: str, role: str) -> str:
    """Generate a JWT token with user_id and role as additional claims."""
    return create_access_token(
        identity=user_id,
        additional_claims={"role": role}
    )
